from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

LAST_SUMMARY_FILE = PROJECT_ROOT / "data" / ".last_daily_summary"
POLL_OFFSET_FILE = PROJECT_ROOT / "data" / ".telegram_offset"

_bot_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def _chat_id() -> str:
    return os.getenv("TELEGRAM_CHAT_ID", "").strip()


def _get_updates(offset: int | None) -> list[dict]:
    token = _token()
    if not token:
        return []
    params: dict = {"timeout": 25}
    if offset is not None:
        params["offset"] = offset
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        resp = httpx.get(url, params=params, timeout=30.0)
        data = resp.json()
        if data.get("ok"):
            return data.get("result", [])
    except httpx.HTTPError:
        pass
    return []


def _load_offset() -> int | None:
    if POLL_OFFSET_FILE.exists():
        try:
            return int(POLL_OFFSET_FILE.read_text().strip())
        except ValueError:
            pass
    return None


def _save_offset(offset: int) -> None:
    POLL_OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    POLL_OFFSET_FILE.write_text(str(offset), encoding="utf-8")


def _handle_message(text: str, chat_id: str) -> None:
    from database.jobs import get_job, update_job_metadata, update_job_status
    from database.qa_memory import store_qa_answer
    from notifications.telegram import send_telegram_message

    if chat_id != _chat_id():
        return

    text = text.strip()
    if text.startswith("/answer "):
        # /answer <job_id> <answer text>
        parts = text[len("/answer ") :].strip().split(" ", 1)
        if len(parts) < 2:
            send_telegram_message("Usage: <code>/answer JOB_ID your answer</code>")
            return
        job_id, answer = parts[0], parts[1].strip()
        job = get_job(job_id)
        if not job:
            send_telegram_message(f"Job not found: <code>{job_id}</code>")
            return
        question = (job.metadata or {}).get("pending_question", "Unknown question")
        store_qa_answer(question, answer, job_id_first_asked=job_id)
        update_job_metadata(job_id, pending_question=None, last_answer=answer)
        update_job_status(job_id, "queued")
        send_telegram_message(
            f"Answer saved to Q&A memory for job <code>{job_id}</code>.\n"
            f"Retry apply from dashboard or <code>/approve {job_id}</code> if review pending."
        )
        return

    if text.startswith("/approve "):
        job_id = text[len("/approve ") :].strip()
        from ats.runner import apply_to_job

        send_telegram_message(f"Submitting job <code>{job_id}</code>…")
        result = apply_to_job(job_id, force_submit=True)
        send_telegram_message(f"Apply result: <code>{result.get('outcome')}</code> — {result.get('message')}")
        return

    if text == "/summary":
        from database.jobs import get_stats
        from notifications.telegram import send_daily_summary

        send_daily_summary(get_stats())
        return


def _poll_loop() -> None:
    offset = _load_offset()
    while not _stop_event.is_set():
        updates = _get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            _save_offset(offset)
            msg = update.get("message") or {}
            text = msg.get("text") or ""
            chat = msg.get("chat") or {}
            if text:
                _handle_message(text, str(chat.get("id", "")))

        _maybe_send_daily_summary()
        time.sleep(1)


def _maybe_send_daily_summary() -> None:
    from database.jobs import get_stats
    from notifications.telegram import send_daily_summary

    now = datetime.now(timezone.utc)
    if now.hour != int(os.getenv("DAILY_SUMMARY_HOUR_UTC", "7")):
        return

    today = now.date().isoformat()
    if LAST_SUMMARY_FILE.exists() and LAST_SUMMARY_FILE.read_text().strip() == today:
        return

    send_daily_summary(get_stats())
    LAST_SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_SUMMARY_FILE.write_text(today, encoding="utf-8")


def start_telegram_bot_background() -> None:
    global _bot_thread
    if not _token() or not _chat_id():
        return
    if _bot_thread and _bot_thread.is_alive():
        return

    _stop_event.clear()
    _bot_thread = threading.Thread(target=_poll_loop, name="telegram-bot", daemon=True)
    _bot_thread.start()


def stop_telegram_bot() -> None:
    _stop_event.set()
