from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _is_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def _api(method: str, payload: dict) -> dict | None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return None
    url = TELEGRAM_API.format(token=token, method=method)
    try:
        response = httpx.post(url, json=payload, timeout=20.0)
        if response.status_code == 200:
            return response.json()
    except httpx.HTTPError:
        return None
    return None


def send_telegram_message(text: str) -> bool:
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not chat_id:
        return False
    result = _api("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
    return bool(result and result.get("ok"))


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
    send_telegram_message(
        f"<b>JantaSearcher — Review before submit</b>\n"
        f"<b>{job_title}</b> @ {company}\n"
        f"Form filled. Approve submit:\n<code>/approve {job_id}</code>\n"
        f"Or open: {external_url}"
    )


def notify_captcha_manual(*, job_id: str, job_title: str, url: str) -> None:
    send_telegram_message(
        f"<b>JantaSearcher — CAPTCHA on apply page</b>\n"
        f"<b>{job_title}</b> (job {job_id})\n"
        f"Solve manually in browser, then retry:\n{url}"
    )


def send_daily_summary(stats: dict[str, int]) -> None:
    send_telegram_message(
        "<b>JantaSearcher — Daily summary</b>\n"
        f"Jobs found: {stats.get('found', 0)}\n"
        f"Applied: {stats.get('applied', 0)}\n"
        f"Pending: {stats.get('pending', 0)}\n"
        f"Needs answer: {stats.get('needs_answer', 0)}\n"
        f"Failed: {stats.get('failed', 0)}\n"
        f"With cover letter: {stats.get('with_cover_letter', 0)}"
    )
