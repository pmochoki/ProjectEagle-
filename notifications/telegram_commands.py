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
    ("/answer JOB_ID text", "Save ATS question answer and re-queue job.", "apply", "answer"),
    ("/scan eu", "Start EU + Hungary LinkedIn scan (runs in background).", "scraper", "scan_eu"),
    ("/scan scholarships", "Start scholarship keyword scan (background).", "scraper", "scan_scholarships"),
    ("/scan linkedin", "Run default LinkedIn job search (background).", "scraper", "scan_linkedin"),
    ("/scan profession", "Run profession.hu scraper (background).", "scraper", "scan_profession"),
    ("/canary", "Run DOM canary checks (background).", "scraper", "canary"),
    ("/automation", "Show scrape/apply scheduler status.", "info", "automation"),
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

    job_id = text[len("/approve ") :].strip()
    if not job_id:
        send_telegram_message("Usage: <code>/approve JOB_ID</code>", chat_id=chat_id)
        return
    send_telegram_message(f"Submitting job <code>{job_id}</code>…", chat_id=chat_id)
    result = apply_to_job(job_id, force_submit=True)
    send_telegram_message(
        f"Apply result: <code>{result.get('outcome')}</code> — {result.get('message')}",
        chat_id=chat_id,
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


def _cmd_scan_profession(_text: str, chat_id: str) -> None:
    from scraper.profession_hu import run_profession_scraper_sync

    send_telegram_message("<b>profession.hu scan started</b> (background).", chat_id=chat_id)
    _run_background("profession.hu scan", lambda: run_profession_scraper_sync(_scraper_cfg()), chat_id)


def _cmd_canary(_text: str, chat_id: str) -> None:
    from scraper.canary import run_all_canaries_sync

    send_telegram_message("<b>DOM canary started</b> (background).", chat_id=chat_id)
    _run_background("DOM canary", lambda: run_all_canaries_sync(_scraper_cfg()), chat_id)


def _cmd_automation(text: str, chat_id: str) -> None:
    from automation.scheduler import automation_status

    status = automation_status()
    state = status["state"]
    send_telegram_message(
        "<b>ProjectEagle — Automation</b>\n"
        f"Enabled: {status['enabled']} | Thread: {status['thread_alive']}\n"
        f"Apply: {status['apply_enabled']} (max {status['apply_max_per_day']}/day, "
        f"min {status['apply_min_interval_minutes']} min apart)\n"
        f"Cycles: {state.cycles_completed}\n"
        f"Last EU scan: {state.last_eu_scrape_at or 'never'}\n"
        f"Last scholarships: {state.last_scholarship_scrape_at or 'never'}\n"
        f"Last apply: {state.last_apply_at or 'never'} "
        f"({state.applications_today_count} today)\n"
        f"Last EU: {state.last_eu_message or '—'}\n"
        f"Last scholarships: {state.last_scholarship_message or '—'}\n"
        f"Last apply: {state.last_apply_message or '—'}",
        chat_id=chat_id,
    )


def _cmd_automation_run(_text: str, chat_id: str) -> None:
    from automation.scheduler import run_automation_cycle

    send_telegram_message(
        "<b>Automation cycle started</b> — EU batch, scholarships, profession.hu, apply.",
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
    "scan_eu": _cmd_scan_eu,
    "scan_scholarships": _cmd_scan_scholarships,
    "scan_linkedin": _cmd_scan_linkedin,
    "scan_profession": _cmd_scan_profession,
    "canary": _cmd_canary,
    "automation": _cmd_automation,
    "automation_run": _cmd_automation_run,
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
    if text == "/scan eu":
        return _HANDLERS["scan_eu"]
    if text == "/scan scholarships":
        return _HANDLERS["scan_scholarships"]
    if text == "/scan linkedin":
        return _HANDLERS["scan_linkedin"]
    if text == "/scan profession":
        return _HANDLERS["scan_profession"]
    if text == "/canary":
        return _HANDLERS["canary"]
    if text == "/automation":
        return _HANDLERS["automation"]
    if text == "/automation run":
        return _HANDLERS["automation_run"]
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
        {"command": "answer", "description": "Save ATS question answer"},
        {"command": "scan", "description": "Subcommands: eu, scholarships, linkedin, profession"},
        {"command": "canary", "description": "Run DOM canary checks"},
        {"command": "automation", "description": "Scrape/apply scheduler status"},
    ]

    result = _api("setMyCommands", {"commands": commands})
    return bool(result and result.get("ok"))
