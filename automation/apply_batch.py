from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ats.runner import apply_to_job
from automation.config import AutomationConfig
from automation.state import AutomationState
from database.jobs import list_apply_candidates, update_job_status
from notifications.telegram import send_telegram_message
from scraper.match_score import compute_match_score


def _local_today(tz_name: str) -> str:
    try:
        return datetime.now(ZoneInfo(tz_name)).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


def _minutes_since(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    try:
        then = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - then).total_seconds() / 60
    except ValueError:
        return None


def maybe_apply_one(cfg: AutomationConfig, state: AutomationState) -> str:
    """Apply to at most one eligible job if daily cap and interval allow."""
    if not cfg.apply_enabled:
        state.last_apply_message = "Apply automation disabled (APPLY_ENABLED=false)"
        return state.last_apply_message

    today = _local_today(cfg.timezone)
    if state.apply_count_for_today(today) >= cfg.apply_max_per_day:
        state.last_apply_message = f"Daily apply cap reached ({cfg.apply_max_per_day})"
        return state.last_apply_message

    since = _minutes_since(state.last_apply_at)
    if since is not None and since < cfg.apply_min_interval_minutes:
        wait = int(cfg.apply_min_interval_minutes - since)
        state.last_apply_message = f"Waiting {wait} min before next apply (careful pacing)"
        return state.last_apply_message

    candidates = list_apply_candidates(limit=20)
    if not candidates:
        state.last_apply_message = (
            "No eligible jobs to apply (need status=new, supported ATS, external apply)"
        )
        return state.last_apply_message

    job = candidates[0]
    score = compute_match_score(job)
    send_telegram_message(
        f"<b>ProjectEagle — Auto-apply starting</b>\n"
        f"<b>{job.title}</b> @ {job.company}\n"
        f"Platform: {job.ats_platform}\n"
        f"Match score: {score}/100\n"
        f"Daily count: {state.apply_count_for_today(today) + 1}/{cfg.apply_max_per_day}"
    )

    update_job_status(job.id, "queued")
    result = apply_to_job(job.id, force_submit=False)
    outcome = result.get("outcome", "unknown")
    message = result.get("message", "")

    state.bump_apply_count(today=today)
    msg = f"Applied to {job.title} — outcome: {outcome}. {message}"
    send_telegram_message(
        f"<b>ProjectEagle — Auto-apply result</b>\n"
        f"<b>{job.title}</b> @ {job.company}\n"
        f"Outcome: <code>{outcome}</code>\n{message}"
    )
    state.last_apply_message = msg
    return msg
