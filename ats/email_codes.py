"""Fetch employer verification codes from email (IMAP) and extract with Claude/regex.

Claude cannot open Gmail directly — we pull recent messages over IMAP, then use
Claude (when CLAUDE_API_KEY is set) to pull out the OTP / verification code.
"""

from __future__ import annotations

import email as email_lib
import imaplib
import os
import re
import time
from dataclasses import dataclass
from email.header import decode_header
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

from ats.forms import click_if_present, fill_if_present


@dataclass
class InboxMessage:
    subject: str
    from_addr: str
    body: str
    uid: str


def imap_configured() -> bool:
    user = os.getenv("EMAIL_IMAP_USER", "").strip() or os.getenv("ATS_ACCOUNT_EMAIL", "").strip()
    password = os.getenv("EMAIL_IMAP_PASSWORD", "").strip() or os.getenv("ATS_SITE_PASSWORD", "").strip()
    return bool(user and password)


def _imap_settings() -> tuple[str, int, str, str]:
    host = os.getenv("EMAIL_IMAP_HOST", "imap.gmail.com").strip() or "imap.gmail.com"
    port = int(os.getenv("EMAIL_IMAP_PORT", "993") or "993")
    user = os.getenv("EMAIL_IMAP_USER", "").strip() or os.getenv("ATS_ACCOUNT_EMAIL", "").strip()
    password = os.getenv("EMAIL_IMAP_PASSWORD", "").strip() or os.getenv("ATS_SITE_PASSWORD", "").strip()
    if not user or not password:
        raise RuntimeError(
            "Email IMAP not configured. Set EMAIL_IMAP_USER + EMAIL_IMAP_PASSWORD "
            "(Gmail: use an App Password) or ATS_ACCOUNT_EMAIL + ATS_SITE_PASSWORD."
        )
    return host, port, user, password


def _decode_mime(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    parts = decode_header(value)
    out: list[str] = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(chunk)
    return "".join(out)


def _message_body(msg: email_lib.message.Message) -> str:
    texts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html"):
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                texts.append(payload.decode(charset, errors="replace"))
    else:
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        texts.append(payload.decode(charset, errors="replace"))
    return "\n".join(texts)


def _looks_like_verification(subject: str, body: str) -> bool:
    blob = f"{subject}\n{body}".lower()
    markers = (
        "verification",
        "verify",
        "one-time",
        "otp",
        "security code",
        "confirmation code",
        "passcode",
        "authenticate",
        "confirm your",
        "your code",
    )
    return any(m in blob for m in markers)


def extract_code_with_regex(text: str) -> str | None:
    """Prefer 6-digit codes, then 4–8 digit standalone numbers."""
    for pattern in (
        r"(?:code|otp|pin|passcode)[^\d]{0,20}(\d{4,8})",
        r"\b(\d{6})\b",
        r"\b(\d{4,8})\b",
    ):
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    # Alphanumeric codes like AB12-CD34
    m = re.search(r"\b([A-Z0-9]{4,8}(?:-[A-Z0-9]{2,8})?)\b", text)
    if m and any(c.isdigit() for c in m.group(1)):
        return m.group(1)
    return None


def extract_code_with_claude(subject: str, body: str) -> str | None:
    try:
        from ai.client import get_claude_client, get_model
    except Exception:
        return None
    try:
        client = get_claude_client()
    except Exception:
        return None

    clipped = body[:6000]
    response = client.messages.create(
        model=get_model(),
        max_tokens=64,
        system=(
            "You extract verification / OTP codes from emails. "
            "Reply with ONLY the code characters. If no code exists, reply NONE."
        ),
        messages=[
            {
                "role": "user",
                "content": f"Subject: {subject}\n\nEmail body:\n{clipped}",
            }
        ],
    )
    parts = [b.text for b in response.content if getattr(b, "type", "") == "text"]
    if not parts:
        return None
    text = parts[0].strip()
    if not text or text.upper() == "NONE":
        return None
    # Take first token-looking code
    return extract_code_with_regex(text) or text.split()[0].strip(".:;")


def fetch_recent_messages(*, limit: int = 12) -> list[InboxMessage]:
    host, port, user, password = _imap_settings()
    client = imaplib.IMAP4_SSL(host, port)
    try:
        client.login(user, password)
        client.select("INBOX")
        status, data = client.search(None, "ALL")
        if status != "OK" or not data or not data[0]:
            return []
        uids = data[0].split()
        recent = uids[-limit:]
        messages: list[InboxMessage] = []
        for uid in reversed(recent):
            st, msg_data = client.fetch(uid, "(RFC822)")
            if st != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw)
            subject = _decode_mime(msg.get("Subject"))
            from_addr = _decode_mime(msg.get("From"))
            body = _message_body(msg)
            messages.append(
                InboxMessage(
                    subject=subject,
                    from_addr=from_addr,
                    body=body,
                    uid=uid.decode() if isinstance(uid, bytes) else str(uid),
                )
            )
        return messages
    finally:
        try:
            client.logout()
        except Exception:
            pass


def find_verification_code(*, since_uid: str | None = None) -> str | None:
    """Scan recent inbox mail for a verification code (Claude first, regex fallback)."""
    for msg in fetch_recent_messages(limit=15):
        if since_uid and msg.uid <= since_uid:
            continue
        if not _looks_like_verification(msg.subject, msg.body):
            # Still try regex — some employers use sparse subjects
            code = extract_code_with_regex(f"{msg.subject}\n{msg.body}")
            if code and len(code) >= 4:
                return code
            continue
        code = extract_code_with_claude(msg.subject, msg.body)
        if code:
            return code
        code = extract_code_with_regex(f"{msg.subject}\n{msg.body}")
        if code:
            return code
    return None


def wait_for_verification_code(
    *,
    timeout_seconds: float | None = None,
    poll_seconds: float | None = None,
) -> str | None:
    timeout = float(
        timeout_seconds
        if timeout_seconds is not None
        else os.getenv("EMAIL_CODE_POLL_SECONDS", "120")
    )
    interval = float(
        poll_seconds if poll_seconds is not None else os.getenv("EMAIL_CODE_POLL_INTERVAL", "8")
    )
    if not imap_configured():
        return None
    deadline = time.time() + max(15.0, timeout)
    seen: set[str] = set()
    while time.time() < deadline:
        try:
            for msg in fetch_recent_messages(limit=10):
                if msg.uid in seen:
                    continue
                seen.add(msg.uid)
                blob = f"{msg.subject}\n{msg.body}"
                if not _looks_like_verification(msg.subject, msg.body):
                    continue
                code = extract_code_with_claude(msg.subject, msg.body) or extract_code_with_regex(
                    blob
                )
                if code:
                    return code
        except Exception:
            pass
        time.sleep(interval)
    return None


async def fill_verification_code(page: "Page", code: str) -> bool:
    """Enter an OTP / verification code on the current page and submit if possible."""
    filled = await fill_if_present(
        page,
        [
            "input[name*='code' i]",
            "input[id*='code' i]",
            "input[autocomplete='one-time-code']",
            "input[inputmode='numeric']",
            "input[name*='otp' i]",
            "input[id*='otp' i]",
            "input[name*='token' i]",
            "input[data-automation-id*='verification']",
            "input[type='tel']",
            "input[type='text']",
        ],
        code,
    )
    if not filled:
        # Multi-box OTP (one digit per input)
        boxes = page.locator("input[maxlength='1']")
        count = await boxes.count()
        if count >= 4 and len(code) >= count:
            for i in range(count):
                await boxes.nth(i).fill(code[i])
            filled = True
    if not filled:
        return False
    await click_if_present(
        page,
        [
            "button[type='submit']",
            "button:has-text('Verify')",
            "button:has-text('Confirm')",
            "button:has-text('Continue')",
            "button:has-text('Submit')",
            "button:has-text('Next')",
        ],
    )
    await page.wait_for_timeout(2000)
    return True
