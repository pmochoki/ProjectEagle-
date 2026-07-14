from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from automation.apply_batch import maybe_apply_one
from automation.config import AutomationConfig
from automation.state import AutomationState
from notifications.telegram import send_telegram_message
from scraper.config import ScraperConfig

logger = logging.getLogger(__name__)

_thread: threading.Thread | None = None
_stop = threading.Event()


def _hours_since(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    try:
        then = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - then).total_seconds() / 3600
    except ValueError:
        return None


def _rotate(items: list[str], start_index: int, count: int) -> tuple[list[str], int]:
    if not items:
        return [], 0
    picked: list[str] = []
    idx = start_index % len(items)
    for _ in range(min(count, len(items))):
        picked.append(items[idx])
        idx = (idx + 1) % len(items)
    return picked, idx


async def _run_eu_batch(scraper_cfg: ScraperConfig, auto_cfg: AutomationConfig, state: AutomationState) -> str:
    locations = list(scraper_cfg.all_job_search_locations())
    titles = list(scraper_cfg.job_search_titles())
    loc_batch, next_loc = _rotate(locations, state.eu_location_index, auto_cfg.locations_per_cycle)
    title_batch, next_title = _rotate(titles, state.eu_title_index, auto_cfg.titles_per_cycle)

    total_inserted = 0
    auth_blocked = False
    for title in title_batch:
        for location in loc_batch:
            loc_cfg = scraper_cfg.with_overrides(
                job_title=title,
                location=location,
                max_pages=min(scraper_cfg.max_pages, 2),
            )
            from scraper.linkedin_scraper import run_scraper

            result = await run_scraper(loc_cfg, source="linkedin_eu")
            total_inserted += result.inserted
            if result.auth_blocked:
                auth_blocked = True
                break
        if auth_blocked:
            break

    state.eu_location_index = next_loc
    state.eu_title_index = next_title
    state.last_eu_scrape_at = datetime.now(timezone.utc).isoformat()
    msg = (
        f"EU batch: {total_inserted} new jobs "
        f"({', '.join(title_batch)} in {', '.join(loc_batch)})"
    )
    if auth_blocked:
        msg = "EU batch stopped — LinkedIn verification needed on your phone."
    state.last_eu_message = msg
    return msg


async def _run_scholarship_batch(
    scraper_cfg: ScraperConfig, auto_cfg: AutomationConfig, state: AutomationState
) -> str:
    keywords = list(scraper_cfg.scholarship_keywords)
    locations = list(scraper_cfg.scholarship_search_locations())
    kw_batch, next_kw = _rotate(
        keywords, state.scholarship_keyword_index, auto_cfg.scholarship_keywords_per_cycle
    )
    loc_batch, next_loc = _rotate(locations, state.scholarship_location_index, 1)

    total_inserted = 0
    auth_blocked = False
    from scraper.linkedin_scraper import run_scraper

    for keyword in kw_batch:
        for location in loc_batch:
            kw_cfg = scraper_cfg.with_overrides(
                job_title=keyword,
                location=location,
                max_pages=min(scraper_cfg.max_pages, 2),
            )
            result = await run_scraper(
                kw_cfg,
                require_external_apply=False,
                source="linkedin_scholarship",
                opportunity_type="scholarship",
            )
            total_inserted += result.inserted
            if result.auth_blocked:
                auth_blocked = True
                break
        if auth_blocked:
            break

    state.scholarship_keyword_index = next_kw
    state.scholarship_location_index = next_loc
    state.last_scholarship_scrape_at = datetime.now(timezone.utc).isoformat()
    msg = f"Scholarship batch: {total_inserted} new listings ({', '.join(kw_batch)} @ {loc_batch[0] if loc_batch else 'EU'})"
    if auth_blocked:
        msg = "Scholarship batch stopped — LinkedIn verification needed."
    state.last_scholarship_message = msg
    return msg


def run_automation_cycle(*, force_eu: bool = False, force_scholarships: bool = False, force_apply: bool = False) -> dict:
    """Run one automation cycle (EU scrape, scholarships, profession.hu, apply)."""
    import asyncio

    auto_cfg = AutomationConfig.from_env()
    scraper_cfg = ScraperConfig.from_env()
    state = AutomationState.load()
    results: dict[str, str] = {}

    try:
        eu_due = force_eu or _hours_since(state.last_eu_scrape_at) is None or _hours_since(
            state.last_eu_scrape_at
        ) >= auto_cfg.scrape_eu_interval_hours
        if eu_due:
            results["eu"] = asyncio.run(_run_eu_batch(scraper_cfg, auto_cfg, state))

        sch_due = force_scholarships or _hours_since(state.last_scholarship_scrape_at) is None or _hours_since(
            state.last_scholarship_scrape_at
        ) >= auto_cfg.scrape_scholarship_interval_hours
        if sch_due:
            results["scholarships"] = asyncio.run(
                _run_scholarship_batch(scraper_cfg, auto_cfg, state)
            )

        prof_due = _hours_since(state.last_profession_scrape_at) is None or _hours_since(
            state.last_profession_scrape_at
        ) >= auto_cfg.scrape_profession_interval_hours
        if prof_due:
            from scraper.profession_hu import run_profession_scraper_sync

            prof = run_profession_scraper_sync(scraper_cfg)
            state.last_profession_scrape_at = datetime.now(timezone.utc).isoformat()
            results["profession"] = f"profession.hu: {prof.get('inserted', 0)} new jobs"

        if force_apply or auto_cfg.apply_enabled:
            results["apply"] = maybe_apply_one(auto_cfg, state)

        state.cycles_completed += 1
        state.last_error = ""
    except Exception as exc:
        state.last_error = str(exc)
        results["error"] = str(exc)
        logger.exception("Automation cycle failed")
    finally:
        state.save()

    return {"ok": not results.get("error"), "results": results, "state": state}


def automation_status() -> dict:
    auto_cfg = AutomationConfig.from_env()
    state = AutomationState.load()
    return {
        "enabled": auto_cfg.enabled,
        "poll_minutes": auto_cfg.poll_minutes,
        "apply_enabled": auto_cfg.apply_enabled,
        "apply_max_per_day": auto_cfg.apply_max_per_day,
        "apply_min_interval_minutes": auto_cfg.apply_min_interval_minutes,
        "thread_alive": bool(_thread and _thread.is_alive()),
        "state": state,
    }


def _loop() -> None:
    while not _stop.is_set():
        cfg = AutomationConfig.from_env()
        if cfg.enabled:
            summary = run_automation_cycle()
            if summary.get("results"):
                logger.info("Automation cycle: %s", summary["results"])
        _stop.wait(cfg.poll_minutes * 60)


def start_automation_background() -> None:
    global _thread
    cfg = AutomationConfig.from_env()
    if not cfg.enabled:
        return
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="automation-scheduler", daemon=True)
    _thread.start()
    send_telegram_message(
        "<b>ProjectEagle — Automation started</b>\n"
        f"EU+Hungary scan every {cfg.scrape_eu_interval_hours}h, "
        f"scholarships every {cfg.scrape_scholarship_interval_hours}h, "
        f"apply up to {cfg.apply_max_per_day}/day "
        f"(min {cfg.apply_min_interval_minutes} min apart)."
    )


def stop_automation() -> None:
    _stop.set()
