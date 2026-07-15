"""LinkedIn auth cooldown, search caps, and session probe."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from scraper.backoff import backoff_seconds

if TYPE_CHECKING:
    from automation.config import AutomationConfig
    from automation.state import AutomationState
    from scraper.config import ScraperConfig


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def linkedin_auth_backoff_base() -> float:
    return float(os.getenv("LINKEDIN_AUTH_BACKOFF_BASE_SECONDS", "60"))


def linkedin_auth_backoff_max() -> float:
    return float(os.getenv("LINKEDIN_AUTH_BACKOFF_MAX_SECONDS", "3600"))


def linkedin_enabled() -> bool:
    """Hard kill switch — set LINKEDIN_ENABLED=false after an account restriction."""
    return os.getenv("LINKEDIN_ENABLED", "true").lower() not in ("0", "false", "no")


def canary_before_scrape() -> bool:
    return os.getenv("CANARY_BEFORE_SCRAPE", "false").lower() in ("1", "true", "yes")


def canary_use_session() -> bool:
    return os.getenv("CANARY_USE_SESSION", "true").lower() != "false"


def is_linkedin_auth_blocked(state: "AutomationState") -> bool:
    if getattr(state, "linkedin_account_restricted", False):
        return True
    until = state.linkedin_auth_blocked_until
    if not until:
        return False
    try:
        blocked_until = datetime.fromisoformat(until.replace("Z", "+00:00"))
        if blocked_until.tzinfo is None:
            blocked_until = blocked_until.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < blocked_until
    except ValueError:
        return False


def linkedin_auth_blocked_message(state: "AutomationState") -> str:
    if getattr(state, "linkedin_account_restricted", False):
        return (
            "LinkedIn account is restricted — logged-in scraping stopped. "
            "Appeal via LinkedIn Help, remove LINKEDIN_EMAIL/PASSWORD from secrets, "
            "set SCRAPER_PUBLIC_MODE=true (or LINKEDIN_ENABLED=false), and use EURES/"
            "Indeed/Arbeitnow. After unlock, send /linkedin_status."
        )
    until = state.linkedin_auth_blocked_until or "unknown"
    failures = state.linkedin_auth_failures
    return (
        f"LinkedIn auth cooldown ({failures} failure(s)) — retry after {until[:19]} UTC. "
        "Complete verification on your phone, then send /linkedin_status."
    )


def record_linkedin_auth_failure(state: "AutomationState", reason: str) -> None:
    if reason == "account_restricted":
        record_linkedin_account_restricted(state)
        return
    state.linkedin_auth_failures += 1
    delay = backoff_seconds(
        state.linkedin_auth_failures,
        base=linkedin_auth_backoff_base(),
        cap=linkedin_auth_backoff_max(),
    )
    blocked_until = datetime.now(timezone.utc).timestamp() + delay
    state.linkedin_auth_blocked_until = datetime.fromtimestamp(
        blocked_until, tz=timezone.utc
    ).isoformat()
    state.last_error = f"LinkedIn auth blocked ({reason}); cooldown {int(delay)}s"


def record_linkedin_account_restricted(state: "AutomationState") -> None:
    """Hard-stop logged-in LinkedIn until the user clears the flag after unlock."""
    state.linkedin_account_restricted = True
    state.linkedin_auth_failures += 1
    # Far-future cooldown so older callers that only check blocked_until also pause.
    far = datetime.now(timezone.utc).timestamp() + 60 * 60 * 24 * 30
    state.linkedin_auth_blocked_until = datetime.fromtimestamp(far, tz=timezone.utc).isoformat()
    state.last_error = (
        "LinkedIn account restricted — stop credential scrape; use public/alt sources"
    )


def clear_linkedin_auth_block(state: "AutomationState") -> None:
    state.linkedin_auth_failures = 0
    state.linkedin_auth_blocked_until = None
    state.linkedin_account_restricted = False


def _linkedin_searches_today(state: "AutomationState") -> int:
    today = _today_str()
    if state.linkedin_searches_today_date != today:
        return 0
    return state.linkedin_searches_today_count


def linkedin_scrape_allowed(state: "AutomationState", auto_cfg: "AutomationConfig") -> tuple[bool, str]:
    if not linkedin_enabled():
        return False, (
            "LinkedIn disabled (LINKEDIN_ENABLED=false). "
            "EURES / Indeed / Arbeitnow / RemoteOK continue as usual."
        )
    public_mode = os.getenv("SCRAPER_PUBLIC_MODE", "true").lower() == "true"
    if getattr(state, "linkedin_account_restricted", False):
        if not public_mode:
            return False, linkedin_auth_blocked_message(state)
        # Guest search does not use the restricted account credentials.
    elif is_linkedin_auth_blocked(state):
        return False, linkedin_auth_blocked_message(state)
    if _linkedin_searches_today(state) >= auto_cfg.linkedin_daily_search_cap:
        return False, (
            f"LinkedIn daily search cap reached ({auto_cfg.linkedin_daily_search_cap}). "
            "Resets at midnight UTC."
        )
    return True, ""


def consume_linkedin_search(state: "AutomationState", auto_cfg: "AutomationConfig") -> bool:
    """Record one LinkedIn search if under cycle + daily caps. Returns False when capped."""
    today = _today_str()
    if state.linkedin_searches_today_date != today:
        state.linkedin_searches_today_date = today
        state.linkedin_searches_today_count = 0
        state.linkedin_searches_cycle_count = 0

    if state.linkedin_searches_cycle_count >= auto_cfg.linkedin_max_searches_per_cycle:
        return False
    if state.linkedin_searches_today_count >= auto_cfg.linkedin_daily_search_cap:
        return False

    state.linkedin_searches_cycle_count += 1
    state.linkedin_searches_today_count += 1
    return True


def reset_linkedin_cycle_search_count(state: "AutomationState") -> None:
    state.linkedin_searches_cycle_count = 0


async def probe_linkedin_session(cfg: "ScraperConfig") -> dict:
    """Check whether saved LinkedIn session can reach feed/jobs without login form."""
    from playwright.async_api import async_playwright

    from scraper.linkedin_page import detect_account_restricted, detect_captcha, session_looks_authenticated
    from scraper.session import load_session_context, session_exists

    if cfg.public_mode:
        return {
            "ok": True,
            "detail": "Public/guest mode — no session required",
            "session_saved": False,
            "public_mode": True,
        }

    if not session_exists():
        has_creds = bool(cfg.linkedin_email and cfg.linkedin_password)
        return {
            "ok": has_creds,
            "detail": "No saved session — credentials set, login on next scrape"
            if has_creds
            else "No session and missing LINKEDIN_EMAIL/PASSWORD",
            "session_saved": False,
        }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=cfg.headless, slow_mo=50)
        context = await load_session_context(browser, headless=cfg.headless)
        page = await context.new_page()
        try:
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)
            if await detect_account_restricted(page):
                return {
                    "ok": False,
                    "detail": "LinkedIn account is restricted — appeal via Help; do not retry login",
                    "session_saved": True,
                    "reason": "account_restricted",
                }
            if await detect_captcha(page):
                return {
                    "ok": False,
                    "detail": "Verification or CAPTCHA required — complete on your phone",
                    "session_saved": True,
                    "reason": "captcha",
                }
            if await session_looks_authenticated(page):
                return {
                    "ok": True,
                    "detail": "Session valid — feed accessible",
                    "session_saved": True,
                }
            if "checkpoint" in page.url.lower() or "challenge" in page.url.lower():
                return {
                    "ok": False,
                    "detail": "LinkedIn checkpoint — complete SMS/email verification",
                    "session_saved": True,
                    "reason": "verification_required",
                }
            return {
                "ok": False,
                "detail": "Session expired — will re-login on next scrape",
                "session_saved": True,
                "reason": "session_expired",
            }
        except Exception as exc:
            return {"ok": False, "detail": f"Probe failed: {exc}", "session_saved": True}
        finally:
            await browser.close()


def probe_linkedin_session_sync(cfg: "ScraperConfig") -> dict:
    import asyncio

    return asyncio.run(probe_linkedin_session(cfg))
