from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _is_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def send_telegram_message(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False

    url = TELEGRAM_API.format(token=token)
    try:
        response = httpx.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=15.0,
        )
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def notify_scrape_complete(
    *,
    found: int,
    inserted: int,
    skipped_easy_apply: int,
    captcha: bool,
) -> None:
    status = "CAPTCHA detected — partial run" if captcha else "Scrape finished"
    text = (
        f"<b>JantaSearcher — {status}</b>\n"
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
