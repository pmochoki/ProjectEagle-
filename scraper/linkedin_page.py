"""Shared LinkedIn page detection helpers."""

from __future__ import annotations

# Login / help copy LinkedIn shows when the account itself is locked.
_ACCOUNT_RESTRICTED_MARKERS = (
    "your account is restricted",
    "account is restricted",
    "we've restricted your account",
    "we restricted your account",
    "account has been restricted",
    "temporarily restricted your account",
)


async def detect_captcha(page) -> bool:
    body_text = (await page.content()).lower()
    return (
        "captcha" in body_text
        or "security verification" in body_text
        or "let's do a quick security check" in body_text
        or "checkpoint" in page.url.lower()
    )


async def detect_account_restricted(page) -> bool:
    """True when LinkedIn shows an account-restriction banner or help page."""
    body_text = (await page.content()).lower()
    if any(marker in body_text for marker in _ACCOUNT_RESTRICTED_MARKERS):
        return True
    url = page.url.lower()
    return "account-restricted" in url or "/help/linkedin/answer/" in url and "restrict" in body_text


async def session_looks_authenticated(page) -> bool:
    if await page.locator("#username").count() > 0:
        return False
    url = page.url.lower()
    return "feed" in url or "/jobs" in url or "mynetwork" in url


def page_text_looks_restricted(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _ACCOUNT_RESTRICTED_MARKERS)
