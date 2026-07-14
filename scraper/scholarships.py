from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass

from notifications.telegram import notify_scrape_complete, send_telegram_message
from scraper.config import ScraperConfig
from scraper.linkedin_scraper import run_scraper


@dataclass
class ScholarshipScrapeSummary:
    keywords_searched: int
    total_found: int
    total_inserted: int
    total_skipped: int
    captcha_detected: bool
    auth_blocked: bool
    results: list[dict]
    message: str


async def run_scholarship_scraper(cfg: ScraperConfig) -> ScholarshipScrapeSummary:
    cfg.validate()

    results: list[dict] = []
    total_found = 0
    total_inserted = 0
    total_skipped = 0
    captcha_detected = False
    auth_blocked = False

    send_telegram_message(
        "<b>ProjectEagle — Scholarship scan started</b>\n"
        f"Keywords: {len(cfg.scholarship_keywords)} | "
        f"Locations: Hungary + EU"
    )

    scholarship_locations = ("Hungary", "European Union")
    for keyword in cfg.scholarship_keywords:
        for location in scholarship_locations:
            kw_cfg = cfg.with_overrides(
                job_title=keyword,
                location=location,
                max_pages=min(cfg.max_pages, 2),
            )
            result = await run_scraper(
                kw_cfg,
                require_external_apply=False,
                source="linkedin_scholarship",
                opportunity_type="scholarship",
            )
            results.append(asdict(result))
            total_found += result.found
            total_inserted += result.inserted
            total_skipped += result.skipped_easy_apply
            captcha_detected = captcha_detected or result.captcha_detected
            auth_blocked = auth_blocked or result.auth_blocked

            if result.auth_blocked:
                break
        if auth_blocked:
            break

    msg = f"Scholarship scan finished. {total_inserted} new listings saved."
    if auth_blocked:
        msg = "Scholarship scan stopped — LinkedIn needs manual verification. Check Telegram."
    elif captcha_detected:
        msg = "Scholarship scan partial — CAPTCHA hit. Complete verification, then retry."

    notify_scrape_complete(
        found=total_found,
        inserted=total_inserted,
        skipped_easy_apply=total_skipped,
        captcha=captcha_detected or auth_blocked,
        source="Scholarships",
    )

    return ScholarshipScrapeSummary(
        keywords_searched=len(results),
        total_found=total_found,
        total_inserted=total_inserted,
        total_skipped=total_skipped,
        captcha_detected=captcha_detected,
        auth_blocked=auth_blocked,
        results=results,
        message=msg,
    )


def run_scholarship_scraper_sync(cfg: ScraperConfig) -> dict:
    summary = asyncio.run(run_scholarship_scraper(cfg))
    return asdict(summary)
