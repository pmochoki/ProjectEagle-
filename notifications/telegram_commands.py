"""Telegram bot command handlers and /list catalog."""

from __future__ import annotations

import threading
from typing import Any, Callable

from notifications.telegram import send_command_list, send_daily_summary, send_telegram_message

Handler = Callable[[str, str], None]

# (command_prefix, description, category, handler_key)
# category: essential | apply | scraper | info
COMMAND_CATALOG: list[tuple[str, str, str, str]] = [
    ("/start", "Welcome message and command list.", "essential", "list"),
    ("/help", "Same as /list.", "essential", "list"),
    ("/list", "Show all bot commands (this message).", "essential", "list"),
    ("/ping", "Quick bot connectivity check.", "essential", "ping"),
    ("/status", "Bot, Telegram API, and database health.", "info", "status"),
    ("/summary", "Job stats now (same as daily summary).", "info", "summary"),
    ("/stats", "Alias for /summary.", "info", "summary"),
    ("/jobs", "List recent jobs. Optional: /jobs 5", "info", "jobs"),
    ("/job JOB_ID", "Details for one job (status, outcome, link).", "info", "job"),
    ("/approve JOB_ID", "Submit after review pause (form already filled).", "apply", "approve"),
    ("/pending", "List applications awaiting your approval (with buttons).", "apply", "pending"),
    ("/answer JOB_ID text", "Save ATS question answer and re-queue job.", "apply", "answer"),
    ("/scan eu", "Start EU + Hungary LinkedIn scan (runs in background).", "scraper", "scan_eu"),
    ("/scan scholarships", "Start scholarship keyword scan (background).", "scraper", "scan_scholarships"),
    ("/scan linkedin", "Run default LinkedIn job search (background).", "scraper", "scan_linkedin"),
    ("/scan hungary", "Hungary-only LinkedIn deep scan (background).", "scraper", "scan_hungary"),
    ("/scan profession", "Run profession.hu scraper (background).", "scraper", "scan_profession"),
    ("/canary", "Run DOM canary checks (background).", "scraper", "canary"),
    ("/linkedin_status", "Check saved LinkedIn session after 2FA.", "scraper", "linkedin_status"),
    ("/linkedin_resume", "One-page LinkedIn test scrape after verification.", "scraper", "linkedin_resume"),
    ("/urgency", "Permit countdown + scan/apply schedule.", "info", "urgency"),
    ("/automation", "Automation status and last scan results.", "info", "automation"),
    ("/automation run", "Force one automation cycle now (background).", "scraper", "automation_run"),
]

AUTOMATIC_ALERTS = [
    "New external-apply jobs",
    "Cover letter ready",
    "Review before submit (with /approve hint)",
    "Application submitted",
    "CAPTCHA on apply page",
    "Unknown ATS questions (with /answer hint)",
    "LinkedIn login / verification needed",
    "Scrape complete (found / inserted counts)",
    "DOM canary OK or FAILED",
    "Automation cycle (EU + scholarships + careful apply)",
]


def _cmd_list(_text: str, chat_id: str) -> None:
    send_command_list(chat_id=chat_id)


def _cmd_ping(_text: str, chat_id: str) -> None:
    send_telegram_message("<b>ProjectEagle bot OK</b> — polling and replies are working.", chat_id=chat_id)


def _cmd_status(_text: str, chat_id: str) -> None:
    from database.jobs import get_stats
    from notifications.telegram import telegram_status
    from notifications.telegram_bot import telegram_bot_status

    tg = telegram_status()
    bot = telegram_bot_status()
    stats = get_stats()
    lines = [
        "<b>ProjectEagle — Status</b>",
        f"Bot: @{tg.get('bot_username') or 'unknown'}",
        f"Polling thread: {'alive' if bot.get('bot_thread_alive') else 'stopped'}",
        f"Webhook blocking polling: {tg.get('webhook_blocks_polling')}",
        f"Notify chats: {', '.join(tg.get('notify_chat_ids') or [])}",
        "",
        "<b>Jobs in database</b>",
        f"Total: {stats.get('total', 0)} | Found: {stats.get('found', 0)}",
        f"Applied: {stats.get('applied', 0)} | Success: {stats.get('success', 0)}",
        f"Failed apply: {stats.get('failed_apply', 0)} | Pending: {stats.get('pending', 0)}",
    ]
    send_telegram_message("\n".join(lines), chat_id=chat_id)


def _cmd_summary(_text: str, chat_id: str) -> None:
    from database.jobs import get_stats

    send_daily_summary(get_stats(), chat_id=chat_id)


def _job_outcome(job) -> str:
    meta = job.metadata or {}
    outcome = meta.get("application_outcome")
    if outcome:
        return outcome
    if job.status == "applied":
        return "applied"
    if job.status == "failed":
        return "failed"
    if job.status == "needs_answer":
        return "needs_answer"
    if meta.get("review_pending"):
        return "review_pending"
    return "—"


def _cmd_jobs(text: str, chat_id: str) -> None:
    from database.jobs import list_jobs

    limit = 10
    parts = text.split()
    if len(parts) >= 2:
        try:
            limit = max(1, min(25, int(parts[1])))
        except ValueError:
            send_telegram_message("Usage: <code>/jobs</code> or <code>/jobs 5</code>", chat_id=chat_id)
            return

    jobs = list_jobs(limit=limit)
    if not jobs:
        send_telegram_message(
            "No jobs in database yet. Run a scan from dashboard or <code>/scan eu</code>.",
            chat_id=chat_id,
        )
        return

    lines = [f"<b>Recent jobs</b> (last {len(jobs)})"]
    for job in jobs:
        outcome = _job_outcome(job)
        suffix = f" [{outcome}]" if outcome != "—" else ""
        lines.append(
            f"• <code>{job.id[:8]}…</code> <b>{job.title}</b> @ {job.company}\n"
            f"  {job.status}{suffix}"
        )
    send_telegram_message("\n".join(lines), chat_id=chat_id)


def _cmd_job(text: str, chat_id: str) -> None:
    from database.jobs import get_job

    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        send_telegram_message("Usage: <code>/job JOB_ID</code>", chat_id=chat_id)
        return

    job_id = parts[1].strip()
    job = get_job(job_id)
    if not job:
        # Try prefix match
        from database.jobs import list_jobs

        matches = [j for j in list_jobs(limit=100) if j.id.startswith(job_id)]
        if len(matches) == 1:
            job = matches[0]
        elif len(matches) > 1:
            send_telegram_message(
                f"Multiple jobs match <code>{job_id}</code>. Use full UUID.",
                chat_id=chat_id,
            )
            return
        else:
            send_telegram_message(f"Job not found: <code>{job_id}</code>", chat_id=chat_id)
            return

    meta = job.metadata or {}
    summary = meta.get("summary") or meta.get("listing_summary") or ""
    summary_block = f"\n\n<b>Summary:</b>\n{summary[:800]}…" if len(summary) > 800 else (
        f"\n\n<b>Summary:</b>\n{summary}" if summary else ""
    )
    msg = (
        f"<b>{job.title}</b> @ {job.company}\n"
        f"ID: <code>{job.id}</code>\n"
        f"Status: {job.status}\n"
        f"Location: {job.location or '—'}\n"
        f"Outcome: {_job_outcome(job)}\n"
        f"Apply: {job.external_url or '—'}"
        f"{summary_block}"
    )
    send_telegram_message(msg, chat_id=chat_id)


def _cmd_answer(text: str, chat_id: str) -> None:
    from database.jobs import get_job, update_job_metadata, update_job_status
    from database.qa_memory import store_qa_answer

    payload = text[len("/answer ") :].strip()
    parts = payload.split(" ", 1)
    if len(parts) < 2:
        send_telegram_message("Usage: <code>/answer JOB_ID your answer</code>", chat_id=chat_id)
        return
    job_id, answer = parts[0], parts[1].strip()
    job = get_job(job_id)
    if not job:
        send_telegram_message(f"Job not found: <code>{job_id}</code>", chat_id=chat_id)
        return
    question = (job.metadata or {}).get("pending_question", "Unknown question")
    store_qa_answer(question, answer, job_id_first_asked=job_id)
    update_job_metadata(job_id, pending_question=None, last_answer=answer)
    update_job_status(job_id, "queued")
    send_telegram_message(
        f"Answer saved for job <code>{job_id}</code>.\n"
        f"Retry: <code>/approve {job_id}</code> or dashboard.",
        chat_id=chat_id,
    )


def _cmd_approve(text: str, chat_id: str) -> None:
    from ats.runner import apply_to_job
    from notifications.telegram import job_dashboard_url

    job_id = text[len("/approve ") :].strip()
    if not job_id:
        send_telegram_message("Usage: <code>/approve JOB_ID</code>", chat_id=chat_id)
        return
    send_telegram_message(f"Submitting job <code>{job_id}</code>…", chat_id=chat_id)
    result = apply_to_job(job_id, force_submit=True)
    dashboard = job_dashboard_url(job_id)
    send_telegram_message(
        f"Apply result: <code>{result.get('outcome')}</code> — {result.get('message')}\n"
        f"📋 <a href=\"{dashboard}\">View in dashboard</a>",
        chat_id=chat_id,
    )


def _cmd_pending(_text: str, chat_id: str) -> None:
    import os

    from database.jobs import list_jobs_pending_review
    from notifications.telegram import approval_reply_markup, job_dashboard_url

    user_id = os.environ.get("AUTOMATION_USER_ID") or None
    pending = list_jobs_pending_review(limit=5, user_id=user_id)
    if not pending:
        send_telegram_message(
            "No applications awaiting approval.",
            chat_id=chat_id,
        )
        return

    send_telegram_message(
        f"<b>Awaiting approval</b> ({len(pending)} shown)",
        chat_id=chat_id,
    )
    for job in pending:
        dashboard = job_dashboard_url(job.id)
        send_telegram_message(
            "<b>Review before submit</b>\n"
            f"<b>{job.title}</b> @ {job.company}\n"
            f"🔗 <a href=\"{job.external_url}\">Application form</a>\n"
            f"📋 <a href=\"{dashboard}\">Dashboard</a>",
            chat_id=chat_id,
            reply_markup=approval_reply_markup(job_id=job.id, external_url=job.external_url),
            disable_web_page_preview=True,
        )


def _run_background(label: str, fn: Callable[[], Any], chat_id: str) -> None:
    def worker() -> None:
        try:
            result = fn()
            send_telegram_message(
                f"<b>{label} finished</b>\n<pre>{result}</pre>",
                chat_id=chat_id,
            )
        except Exception as exc:
            send_telegram_message(f"<b>{label} failed</b>\n{exc}", chat_id=chat_id)

    threading.Thread(target=worker, name=f"tg-{label}", daemon=True).start()


def _scraper_cfg():
    from scraper.config import ScraperConfig

    return ScraperConfig.from_env()


def _cmd_scan_eu(_text: str, chat_id: str) -> None:
    from scraper.eu_jobs import run_eu_jobs_scraper_sync

    send_telegram_message(
        "<b>EU + Hungary scan started</b> — background (5–15 min). "
        "You will get a scrape alert when it finishes.",
        chat_id=chat_id,
    )
    _run_background("EU + Hungary scan", lambda: run_eu_jobs_scraper_sync(_scraper_cfg()), chat_id)


def _cmd_scan_scholarships(_text: str, chat_id: str) -> None:
    from scraper.scholarships import run_scholarship_scraper_sync

    send_telegram_message("<b>Scholarship scan started</b> (background).", chat_id=chat_id)
    _run_background("Scholarship scan", lambda: run_scholarship_scraper_sync(_scraper_cfg()), chat_id)


def _cmd_scan_linkedin(_text: str, chat_id: str) -> None:
    from scraper.linkedin_scraper import run_scraper_sync

    send_telegram_message("<b>LinkedIn scan started</b> (background).", chat_id=chat_id)
    _run_background("LinkedIn scan", lambda: run_scraper_sync(_scraper_cfg()), chat_id)


def _cmd_scan_hungary(_text: str, chat_id: str) -> None:
    import asyncio

    from automation.config import AutomationConfig
    from automation.scheduler import _run_hungary_batch
    from automation.state import AutomationState

    send_telegram_message(
        "<b>Hungary LinkedIn scan started</b> — all HU locations × multiple titles (background).",
        chat_id=chat_id,
    )

    def worker() -> str:
        auto_cfg = AutomationConfig.from_env()
        scraper_cfg = _scraper_cfg()
        state = AutomationState.load()
        msg = asyncio.run(_run_hungary_batch(scraper_cfg, auto_cfg, state))
        state.save()
        return msg

    _run_background("Hungary scan", worker, chat_id)


def _cmd_scan_profession(_text: str, chat_id: str) -> None:
    from scraper.profession_hu import run_profession_scraper_sync

    send_telegram_message("<b>profession.hu scan started</b> (background).", chat_id=chat_id)
    _run_background("profession.hu scan", lambda: run_profession_scraper_sync(_scraper_cfg()), chat_id)


def _cmd_canary(_text: str, chat_id: str) -> None:
    from scraper.canary import run_all_canaries_sync

    send_telegram_message("<b>DOM canary started</b> (background).", chat_id=chat_id)
    _run_background(
        "DOM canary",
        lambda: run_all_canaries_sync(_scraper_cfg(), notify_ok=False),
        chat_id,
    )


def _cmd_linkedin_status(_text: str, chat_id: str) -> None:
    from automation.state import AutomationState
    from scraper.linkedin_auth import clear_linkedin_auth_block, probe_linkedin_session_sync

    cfg = _scraper_cfg()
    state = AutomationState.load()
    if getattr(state, "linkedin_account_restricted", False) and not cfg.public_mode:
        send_telegram_message(
            "<b>ProjectEagle — LinkedIn session</b>\n"
            "Status: Account restricted\n"
            "Logged-in scraping is stopped.\n"
            "Appeal via LinkedIn Help, set <code>SCRAPER_PUBLIC_MODE=true</code> "
            "(or <code>LINKEDIN_ENABLED=false</code>), clear credentials from secrets, "
            "then after LinkedIn restores access run this command again to clear the flag.",
            chat_id=chat_id,
        )
        return

    probe = probe_linkedin_session_sync(cfg)
    lines = [
        "<b>ProjectEagle — LinkedIn session</b>",
        f"Status: {'OK' if probe.get('ok') else 'Needs action'}",
        f"Detail: {probe.get('detail', 'unknown')}",
        f"Saved session: {probe.get('session_saved', False)}",
    ]
    if probe.get("reason") == "account_restricted":
        from scraper.linkedin_auth import record_linkedin_account_restricted

        record_linkedin_account_restricted(state)
        state.save()
        lines.append(
            "Restriction recorded — stop credential scrape; use public mode / alt sources."
        )
    elif probe.get("ok") and not probe.get("public_mode"):
        clear_linkedin_auth_block(state)
        state.save()
        lines.append("Auth cooldown cleared — automation can retry LinkedIn.")
    elif probe.get("ok") and probe.get("public_mode"):
        lines.append(
            "Guest mode OK. Restriction flag kept until a logged-in session probe succeeds."
        )
    elif probe.get("reason") in ("captcha", "verification_required"):
        lines.append("Complete verification on your phone, then run this command again.")
    send_telegram_message("\n".join(lines), chat_id=chat_id)


def _cmd_linkedin_resume(_text: str, chat_id: str) -> None:
    from scraper.linkedin_scraper import run_scraper_sync

    cfg = _scraper_cfg().with_overrides(max_pages=1)
    send_telegram_message(
        "<b>LinkedIn resume test started</b> — 1 page, default title/location (background).",
        chat_id=chat_id,
    )
    _run_background("LinkedIn resume test", lambda: run_scraper_sync(cfg), chat_id)


def _cmd_automation(_text: str, chat_id: str) -> None:
    from automation.scheduler import automation_status

    status = automation_status()
    state = status["state"]
    urg = status.get("urgency") or {}
    send_telegram_message(
        "<b>ProjectEagle — Automation</b>\n"
        f"{urg.get('message', '')}\n\n"
        f"Enabled: {status['enabled']} | Thread: {status['thread_alive']}\n"
        f"Check every: {status.get('poll_minutes', '?')} min\n"
        f"LinkedIn Europe: every {status.get('scrape_eu_interval_hours', '?')}h\n"
        f"Scholarships: every {status.get('scrape_scholarship_interval_hours', '?')}h\n"
        f"EURES/Arbeitnow/RemoteOK: every {status.get('scrape_extra_interval_hours', '?')}h\n"
        f"Apply: max {status['apply_max_per_day']}/day, min {status['apply_min_interval_minutes']} min apart\n"
        f"Cycles: {state.cycles_completed}\n"
        f"Last apply: {state.last_apply_at or 'never'} ({state.applications_today_count} today)\n"
        f"Last EU: {state.last_eu_message or '—'}\n"
        f"Last scholarships: {state.last_scholarship_message or '—'}\n"
        f"LinkedIn auth failures: {state.linkedin_auth_failures}\n"
        f"LinkedIn searches today: {state.linkedin_searches_today_count}",
        chat_id=chat_id,
    )


def _cmd_urgency(_text: str, chat_id: str) -> None:
    from automation.config import AutomationConfig
    from automation.urgency import urgency_status
    from scraper.sources.registry import ALL_SOURCES

    u = urgency_status()
    cfg = AutomationConfig.from_env()
    sources = ", ".join(s.name for s in ALL_SOURCES)
    send_telegram_message(
        "<b>ProjectEagle — Urgency & schedule</b>\n"
        f"{u.message}\n"
        f"{u.recommended_action}\n\n"
        f"<b>Frequency (active now):</b>\n"
        f"• Check cycle: every {cfg.poll_minutes} min\n"
        f"• LinkedIn Europe: every {cfg.scrape_eu_interval_hours}h (Hungary in every batch)\n"
        f"• Hungary deep scan: every {cfg.scrape_hungary_interval_hours}h\n"
        f"• Scholarships (Hungary-first): every {cfg.scrape_scholarship_interval_hours}h\n"
        f"• EURES + Arbeitnow + RemoteOK + feeds: every {cfg.scrape_extra_interval_hours}h\n"
        f"• profession.hu: every {cfg.scrape_profession_interval_hours}h\n"
        f"• Auto-apply: up to {cfg.apply_max_per_day}/day, {cfg.apply_min_interval_minutes} min apart\n\n"
        f"<b>Sources:</b> {sources}",
        chat_id=chat_id,
    )


def _cmd_automation_run(_text: str, chat_id: str) -> None:
    from automation.scheduler import run_automation_cycle

    send_telegram_message(
        "<b>Automation cycle started</b> — EU + Hungary, scholarships, profession.hu, apply.",
        chat_id=chat_id,
    )

    def worker() -> dict:
        return run_automation_cycle(force_eu=True, force_scholarships=True, force_apply=True)

    _run_background("Automation cycle", worker, chat_id)


_HANDLERS: dict[str, Handler] = {
    "list": _cmd_list,
    "ping": _cmd_ping,
    "status": _cmd_status,
    "summary": _cmd_summary,
    "jobs": _cmd_jobs,
    "job": _cmd_job,
    "answer": _cmd_answer,
    "approve": _cmd_approve,
    "pending": _cmd_pending,
    "scan_eu": _cmd_scan_eu,
    "scan_scholarships": _cmd_scan_scholarships,
    "scan_linkedin": _cmd_scan_linkedin,
    "scan_hungary": _cmd_scan_hungary,
    "scan_profession": _cmd_scan_profession,
    "canary": _cmd_canary,
    "linkedin_status": _cmd_linkedin_status,
    "linkedin_resume": _cmd_linkedin_resume,
    "automation": _cmd_automation,
    "automation_run": _cmd_automation_run,
    "urgency": _cmd_urgency,
}


def _resolve_handler(text: str) -> Handler | None:
    text = text.strip()
    if text in ("/list", "/help", "/start"):
        return _HANDLERS["list"]
    if text in ("/summary", "/stats"):
        return _HANDLERS["summary"]
    if text == "/ping":
        return _HANDLERS["ping"]
    if text == "/status":
        return _HANDLERS["status"]
    if text == "/jobs" or text.startswith("/jobs "):
        return _HANDLERS["jobs"]
    if text.startswith("/job "):
        return _HANDLERS["job"]
    if text.startswith("/answer "):
        return _HANDLERS["answer"]
    if text.startswith("/approve "):
        return _HANDLERS["approve"]
    if text == "/pending":
        return _HANDLERS["pending"]
    if text == "/scan eu":
        return _HANDLERS["scan_eu"]
    if text == "/scan scholarships":
        return _HANDLERS["scan_scholarships"]
    if text == "/scan linkedin":
        return _HANDLERS["scan_linkedin"]
    if text == "/scan profession":
        return _HANDLERS["scan_profession"]
    if text == "/scan hungary":
        return _HANDLERS["scan_hungary"]
    if text == "/canary":
        return _HANDLERS["canary"]
    if text == "/linkedin_status":
        return _HANDLERS["linkedin_status"]
    if text == "/linkedin_resume":
        return _HANDLERS["linkedin_resume"]
    if text == "/automation":
        return _HANDLERS["automation"]
    if text == "/automation run":
        return _HANDLERS["automation_run"]
    if text == "/urgency":
        return _HANDLERS["urgency"]
    return None


def dispatch_command(text: str, chat_id: str) -> bool:
    """Handle a command. Returns True if handled, False if unknown."""
    handler = _resolve_handler(text)
    if handler is None:
        return False
    handler(text, chat_id)
    return True


def register_bot_commands_with_telegram() -> bool:
    """Sync command menu shown in Telegram client (BotFather-style)."""
    from notifications.telegram import _api

    commands: list[dict[str, str]] = [
        {"command": "list", "description": "Show all bot commands"},
        {"command": "ping", "description": "Quick connectivity check"},
        {"command": "status", "description": "Bot and database health"},
        {"command": "summary", "description": "Job stats now"},
        {"command": "jobs", "description": "List recent jobs (optional count)"},
        {"command": "job", "description": "Details for one job ID"},
        {"command": "approve", "description": "Submit after review pause"},
        {"command": "pending", "description": "Applications awaiting approval"},
        {"command": "answer", "description": "Save ATS question answer"},
        {"command": "scan", "description": "Subcommands: eu, scholarships, linkedin, profession"},
        {"command": "canary", "description": "Run DOM canary checks"},
        {"command": "linkedin_status", "description": "Check LinkedIn session after 2FA"},
        {"command": "automation", "description": "Scrape/apply scheduler status"},
    ]

    result = _api("setMyCommands", {"commands": commands})
    return bool(result and result.get("ok"))
