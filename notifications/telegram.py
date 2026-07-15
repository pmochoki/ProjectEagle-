from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _parse_chat_ids(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def notify_chat_ids() -> list[str]:
    """Destinations for outbound alerts and command replies."""
    ids: list[str] = []
    for env_name in ("TELEGRAM_NOTIFY_CHAT_IDS", "TELEGRAM_CHAT_ID", "TELEGRAM_CHANNEL_ID"):
        raw = os.getenv(env_name, "").strip()
        if raw:
            ids.extend(_parse_chat_ids(raw))
    # Preserve order, drop duplicates.
    return list(dict.fromkeys(ids))


def _api(method: str, payload: dict | None = None) -> dict | None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return None
    url = TELEGRAM_API.format(token=token, method=method)
    try:
        response = httpx.post(url, json=payload or {}, timeout=20.0)
        if response.status_code == 200:
            return response.json()
    except httpx.HTTPError:
        return None
    return None


def telegram_status() -> dict:
    """Diagnostics for API health checks."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chats = notify_chat_ids()
    if not token:
        return {"configured": False, "polling_ready": False, "detail": "Missing TELEGRAM_BOT_TOKEN"}

    me = _api("getMe")
    webhook = _api("getWebhookInfo")
    return {
        "configured": bool(chats),
        "polling_ready": bool(chats),
        "notify_chat_ids": chats,
        "bot_username": (me or {}).get("result", {}).get("username"),
        "webhook_url": (webhook or {}).get("result", {}).get("url") or "",
        "webhook_blocks_polling": bool((webhook or {}).get("result", {}).get("url")),
    }


def ensure_polling_mode() -> bool:
    """Delete webhook so long-polling getUpdates works."""
    result = _api("deleteWebhook", {"drop_pending_updates": False})
    return bool(result and result.get("ok"))


def send_startup_message() -> None:
    send_telegram_message(
        "<b>JantaSearcher is connected.</b>\n"
        "You will get scrape alerts, question escalations, and review prompts here.\n"
        "Send <code>/list</code> for commands."
    )


def dashboard_url() -> str:
    return os.getenv("FRONTEND_URL", "https://project-eagle-six.vercel.app").rstrip("/")


def job_dashboard_url(job_id: str) -> str:
    return f"{dashboard_url()}/jobs?job={job_id}"


def approval_reply_markup(*, job_id: str, external_url: str) -> dict:
    """Inline buttons: approve submit, open ATS form, open dashboard."""
    rows: list[list[dict]] = [
        [{"text": "✅ Approve & submit", "callback_data": f"approve:{job_id}"}],
    ]
    link_row: list[dict] = []
    if external_url:
        link_row.append({"text": "🔗 Application form", "url": external_url})
    link_row.append({"text": "📋 Dashboard", "url": job_dashboard_url(job_id)})
    rows.append(link_row)
    return {"inline_keyboard": rows}


def answer_callback_query(callback_query_id: str, *, text: str = "", alert: bool = False) -> bool:
    result = _api(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_query_id,
            "text": text[:200],
            "show_alert": alert,
        },
    )
    return bool(result and result.get("ok"))


def edit_telegram_message(
    *,
    chat_id: str,
    message_id: int,
    text: str,
    reply_markup: dict | None = None,
) -> bool:
    payload: dict = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    result = _api("editMessageText", payload)
    return bool(result and result.get("ok"))


def send_telegram_message(
    text: str,
    *,
    chat_id: str | None = None,
    reply_markup: dict | None = None,
    disable_web_page_preview: bool = False,
) -> bool:
    targets = [chat_id] if chat_id else notify_chat_ids()
    if not targets:
        return False

    ok = False
    for target in targets:
        payload: dict = {
            "chat_id": target,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_web_page_preview,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        result = _api("sendMessage", payload)
        ok = ok or bool(result and result.get("ok"))
    return ok


def notify_linkedin_auth_issue(
    *,
    reason: str,
    search_title: str = "",
    search_location: str = "",
) -> None:
    """Tell the user to fix LinkedIn manually on their phone — no code needed."""
    context = ""
    if search_title or search_location:
        context = f"\nSearch: <b>{search_title}</b> in {search_location or 'EU'}"

    if reason == "captcha":
        body = (
            "LinkedIn showed a CAPTCHA or security check."
            "\n\n<b>What to do (on your phone):</b>"
            "\n1. Open the LinkedIn app or browser and log in as the scraper account"
            "\n2. Complete any verification / CAPTCHA / “confirm it’s you” prompt"
            "\n3. Wait 2–3 minutes, then tap <b>Run scraper</b> again in the dashboard"
            "\n\nNo coding required — the saved session will resume after you verify."
        )
    elif reason == "account_restricted":
        body = (
            "LinkedIn has <b>restricted this account</b> (automation risk)."
            "\n\n<b>Do this now:</b>"
            "\n1. Stop all LinkedIn logins from ProjectEagle — do not retry scrape-login"
            "\n2. Change the LinkedIn password (and email password if it was reused)"
            "\n3. Clear <code>LINKEDIN_EMAIL</code> / <code>LINKEDIN_PASSWORD</code> from Cursor Cloud Secrets / <code>.env</code>"
            "\n4. Set <code>SCRAPER_PUBLIC_MODE=true</code> (guest LinkedIn) or <code>LINKEDIN_ENABLED=false</code>"
            "\n5. Keep EURES / Indeed / Arbeitnow / RemoteOK running for job discovery"
            "\n6. On your phone: LinkedIn Help → appeal / request review for restricted account"
            "\n\nLogged-in scraping stays off until you unlock the account and send "
            "<code>/linkedin_status</code>."
        )
    elif reason == "verification_required":
        body = (
            "LinkedIn wants extra verification (checkpoint)."
            "\n\n<b>What to do (on your phone):</b>"
            "\n1. Log into LinkedIn with the scraper account"
            "\n2. Complete SMS/email/app verification"
            "\n3. Retry the scraper from the dashboard when done"
        )
    elif reason == "bad_credentials":
        body = (
            "LinkedIn rejected the login (wrong password or locked account)."
            "\n\n<b>What to do:</b>"
            "\n1. Reset the password on LinkedIn if needed"
            "\n2. Update <code>LINKEDIN_EMAIL</code> / <code>LINKEDIN_PASSWORD</code> in <code>.env</code>"
            "\n3. Delete <code>data/linkedin_session.json</code> and retry"
        )
    else:
        body = (
            "LinkedIn login did not complete."
            "\n\n<b>What to do (on your phone):</b>"
            "\n1. Log into LinkedIn manually with the scraper account"
            "\n2. Clear any security prompts"
            "\n3. Retry the scraper — session cookies will be saved automatically"
        )

    send_telegram_message(
        f"<b>ProjectEagle — LinkedIn needs you</b>{context}\n\n{body}\n\n"
        "When finished on your phone, send <code>/linkedin_status</code> to verify the session."
    )


def notify_scrape_complete(
    *,
    found: int,
    inserted: int,
    skipped_easy_apply: int,
    captcha: bool,
    source: str = "LinkedIn",
) -> None:
    status = "CAPTCHA detected — partial run. Solve manually, then retry." if captcha else "Scrape finished"
    text = (
        f"<b>JantaSearcher — {source} {status}</b>\n"
        f"External-apply jobs found: {found}\n"
        f"New jobs saved: {inserted}\n"
        f"Skipped (Easy Apply / no external link): {skipped_easy_apply}"
    )
    send_telegram_message(text)


def notify_new_jobs(jobs: list) -> None:
    if not jobs:
        return
    lines = ["<b>JantaSearcher — New external-apply jobs</b>"]
    for job in jobs[:10]:
        title = getattr(job, "title", job.get("title", "Unknown"))
        company = getattr(job, "company", job.get("company", "Unknown"))
        url = getattr(job, "external_apply_url", job.get("external_apply_url", ""))
        lines.append(f"• <b>{title}</b> @ {company}\n  {url}")
    if len(jobs) > 10:
        lines.append(f"...and {len(jobs) - 10} more")
    send_telegram_message("\n\n".join(lines))


def notify_cover_letter_ready(*, job_title: str, company: str, job_id: str) -> None:
    text = (
        f"<b>JantaSearcher — Cover letter ready</b>\n"
        f"<b>{job_title}</b> @ {company}\n"
        f"Job ID: {job_id} — open the dashboard to review."
    )
    send_telegram_message(text)


def notify_canary_failure(scraper: str, message: str) -> None:
    send_telegram_message(
        f"<b>JantaSearcher — DOM canary FAILED</b>\n"
        f"Scraper: <code>{scraper}</code>\n"
        f"{message}"
    )


def notify_canary_ok(scraper: str, message: str) -> None:
    send_telegram_message(
        f"<b>JantaSearcher — DOM canary OK</b>\n"
        f"Scraper: <code>{scraper}</code>\n"
        f"{message}"
    )


def notify_question_escalation(
    *,
    job_title: str,
    company: str,
    external_url: str,
    job_id: str,
    question_text: str,
) -> None:
    send_telegram_message(
        f"<b>JantaSearcher — Question needed</b>\n"
        f"<b>{job_title}</b> @ {company}\n"
        f"Apply: {external_url}\n\n"
        f"<b>Question:</b>\n{question_text}\n\n"
        f"Reply with:\n<code>/answer {job_id} your answer here</code>"
    )


def notify_apply_review_pending(
    *,
    job_title: str,
    company: str,
    job_id: str,
    external_url: str,
) -> None:
    dashboard = job_dashboard_url(job_id)
    send_telegram_message(
        "<b>ProjectEagle — Review before submit</b>\n"
        f"<b>{job_title}</b> @ {company}\n"
        f"Form filled and ready — tap <b>Approve & submit</b> below.\n\n"
        f"🔗 <a href=\"{external_url}\">Open application form</a>\n"
        f"📋 <a href=\"{dashboard}\">View in dashboard</a>\n\n"
        f"Or reply: <code>/approve {job_id}</code>",
        reply_markup=approval_reply_markup(job_id=job_id, external_url=external_url),
        disable_web_page_preview=True,
    )


def notify_application_submitted(*, job_title: str, company: str, job_id: str) -> None:
    send_telegram_message(
        f"<b>JantaSearcher — Application submitted</b>\n"
        f"<b>{job_title}</b> @ {company}\n"
        f"Job ID: <code>{job_id}</code>"
    )


def notify_captcha_manual(*, job_id: str, job_title: str, url: str) -> None:
    send_telegram_message(
        f"<b>JantaSearcher — CAPTCHA on apply page</b>\n"
        f"<b>{job_title}</b> (job {job_id})\n"
        f"Solve manually in browser, then retry:\n{url}"
    )


def notify_needs_account(
    *,
    job_id: str,
    job_title: str,
    company: str,
    url: str,
    detail: str = "",
) -> None:
    send_telegram_message(
        "<b>ProjectEagle — Employer account needed</b>\n"
        f"<b>{job_title}</b> @ {company}\n"
        f"{detail or 'Could not auto-register / sign in.'}\n\n"
        "Open the link, create or verify the account, then retry apply "
        "(session will be saved for next time):\n"
        f"{url}\n"
        f"Job: <code>{job_id}</code>"
    )


def notify_needs_verification(
    *,
    job_id: str,
    job_title: str,
    company: str,
    url: str,
    detail: str = "",
) -> None:
    send_telegram_message(
        "<b>ProjectEagle — Verify employer email</b>\n"
        f"<b>{job_title}</b> @ {company}\n"
        f"{detail or 'Check your inbox and confirm the account.'}\n\n"
        "After you verify, reply or retry apply from the dashboard — "
        "we keep the saved site session.\n"
        f"{url}\n"
        f"Job: <code>{job_id}</code>"
    )


def send_command_list(*, chat_id: str | None = None) -> None:
    from notifications.telegram_commands import AUTOMATIC_ALERTS, COMMAND_CATALOG

    category_titles = {
        "essential": "Essential",
        "info": "Info & stats",
        "apply": "Applications",
        "scraper": "Scrapers (background)",
    }
    sections: list[str] = ["<b>ProjectEagle — Commands</b>"]
    for cat_key, title in category_titles.items():
        items = [row for row in COMMAND_CATALOG if row[2] == cat_key]
        if not items:
            continue
        blocks = []
        for cmd, desc, _c, _k in items:
            blocks.append(f"<code>{cmd}</code>\n{desc}")
        sections.append(f"\n<b>{title}</b>\n\n" + "\n\n".join(blocks))

    alert_lines = "\n".join(f"• {a}" for a in AUTOMATIC_ALERTS)
    sections.append(f"\n<b>Automatic alerts</b> (no command)\n{alert_lines}")
    sections.append(
        "\n<i>Tip:</i> Scraper commands run in the background — you still get "
        "<b>scrape complete</b> alerts when they finish."
    )
    send_telegram_message("\n".join(sections), chat_id=chat_id)


def send_daily_summary(stats: dict[str, int], *, chat_id: str | None = None) -> None:
    from automation.urgency import urgency_status

    urg = urgency_status()
    permit_line = f"\n⏳ {urg.message}" if urg.permit_deadline else ""
    send_telegram_message(
        "<b>ProjectEagle — Summary</b>\n"
        f"Total jobs: {stats.get('total', 0)}\n"
        f"Found (new): {stats.get('found', 0)}\n"
        f"Scholarships: {stats.get('scholarships', 0)}\n"
        f"Applied: {stats.get('applied', 0)}\n"
        f"Success: {stats.get('success', 0)}\n"
        f"Failed apply: {stats.get('failed_apply', 0)}\n"
        f"Pending: {stats.get('pending', 0)}\n"
        f"Needs answer: {stats.get('needs_answer', 0)}\n"
        f"Awaiting approval: {stats.get('applications_pending_review', 0)}\n"
        f"With cover letter: {stats.get('with_cover_letter', 0)}"
        f"{permit_line}\n\n"
        "Tap <code>/pending</code> for approval buttons.",
        chat_id=chat_id,
    )
