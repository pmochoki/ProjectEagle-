"""Attempt employer-site registration / login using profile + site vault.

Never bypasses CAPTCHA. Email verification escalates to the user via Telegram.
"""

from __future__ import annotations

from typing import Any

from playwright.async_api import Page

from ats.accounts import (
    SiteAccount,
    get_or_create_account,
    host_for_url,
    mark_account_created,
    save_site_session,
)
from ats.auth_gate import AuthGate, detect_auth_gate, detect_captcha, detect_email_verification
from ats.forms import click_if_present, fill_if_present


async def _click_create_account(page: Page) -> bool:
    return await click_if_present(
        page,
        [
            "a:has-text('Create Account')",
            "button:has-text('Create Account')",
            "a:has-text('Sign Up')",
            "button:has-text('Sign Up')",
            "a:has-text('Register')",
            "button:has-text('Register')",
            "a:has-text('Create an Account')",
            "button:has-text('Create an Account')",
        ],
    )


async def _click_sign_in(page: Page) -> bool:
    return await click_if_present(
        page,
        [
            "a:has-text('Sign In')",
            "button:has-text('Sign In')",
            "a:has-text('Log In')",
            "button:has-text('Log In')",
            "button:has-text('Sign in')",
        ],
    )


async def fill_registration_form(page: Page, account: SiteAccount, profile: dict[str, Any]) -> bool:
    contact = profile.get("contact", {})
    full = (contact.get("full_name") or "").strip()
    parts = full.split()
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""

    filled_email = await fill_if_present(
        page,
        [
            "input[type='email']",
            "input[name*='email' i]",
            "input[id*='email' i]",
            "input[data-automation-id*='email']",
            "input[autocomplete='email']",
        ],
        account.email,
    )
    filled_password = await fill_if_present(
        page,
        [
            "input[type='password']",
            "input[name*='password' i]",
            "input[id*='password' i]",
            "input[data-automation-id*='password']",
            "input[autocomplete='new-password']",
        ],
        account.password,
    )
    # Confirm password (second password field if present)
    pw_fields = page.locator("input[type='password']")
    if await pw_fields.count() >= 2:
        try:
            await pw_fields.nth(1).fill(account.password, timeout=3000)
        except Exception:
            pass

    await fill_if_present(
        page,
        [
            "input[name*='first' i]",
            "input[id*='first' i]",
            "input[autocomplete='given-name']",
            "input[data-automation-id*='firstName']",
        ],
        first,
    )
    await fill_if_present(
        page,
        [
            "input[name*='last' i]",
            "input[id*='last' i]",
            "input[autocomplete='family-name']",
            "input[data-automation-id*='lastName']",
        ],
        last,
    )
    await fill_if_present(
        page,
        ["input[name='name']", "input[autocomplete='name']"],
        full,
    )
    return filled_email and filled_password


async def submit_auth_form(page: Page) -> bool:
    return await click_if_present(
        page,
        [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Create Account')",
            "button:has-text('Sign Up')",
            "button:has-text('Register')",
            "button:has-text('Sign In')",
            "button:has-text('Log In')",
            "button:has-text('Continue')",
            "button:has-text('Next')",
        ],
    )


async def fill_login_form(page: Page, account: SiteAccount) -> bool:
    email_ok = await fill_if_present(
        page,
        [
            "input[type='email']",
            "input[name*='email' i]",
            "input[name*='username' i]",
            "input[id*='email' i]",
            "input[autocomplete='username']",
            "input[data-automation-id*='email']",
        ],
        account.email,
    )
    pw_ok = await fill_if_present(
        page,
        [
            "input[type='password']",
            "input[name*='password' i]",
            "input[autocomplete='current-password']",
            "input[data-automation-id*='password']",
        ],
        account.password,
    )
    return email_ok and pw_ok


async def ensure_authenticated(
    page: Page,
    *,
    job_url: str,
    profile: dict[str, Any],
    context,
) -> AuthGate:
    """
    If the page needs an account, try create/login using the site vault.
    Returns AuthGate describing the resulting state (none = proceed to apply).
    """
    gate = await detect_auth_gate(page)
    if gate.kind == "none":
        return gate
    if gate.kind == "captcha":
        return gate
    if gate.kind == "email_verify":
        return gate

    contact = profile.get("contact", {})
    account = get_or_create_account(job_url, profile_email=contact.get("email", ""))
    host = host_for_url(job_url)

    if gate.kind == "register" or (gate.kind == "login" and not account.created):
        await _click_create_account(page)
        await page.wait_for_timeout(1200)
        if await detect_captcha(page):
            return AuthGate(kind="captcha", detail="CAPTCHA on registration form")
        if not await fill_registration_form(page, account, profile):
            return AuthGate(kind="register", detail="Could not fill registration fields")
        await submit_auth_form(page)
        await page.wait_for_timeout(2500)
        if await detect_captcha(page):
            return AuthGate(kind="captcha", detail="CAPTCHA after registration submit")
        if await detect_email_verification(page):
            mark_account_created(host, notes="pending email verification")
            await save_site_session(context, host)
            return AuthGate(kind="email_verify", detail=f"Verify email for {account.email}")
        mark_account_created(host, notes="registered via ProjectEagle")
        await save_site_session(context, host)
        return await detect_auth_gate(page)

    # Existing account → login
    await _click_sign_in(page)
    await page.wait_for_timeout(1000)
    if await detect_captcha(page):
        return AuthGate(kind="captcha", detail="CAPTCHA on login form")
    if not await fill_login_form(page, account):
        # Fall back to create-account path
        await _click_create_account(page)
        await page.wait_for_timeout(1000)
        if await fill_registration_form(page, account, profile):
            await submit_auth_form(page)
            await page.wait_for_timeout(2500)
            if await detect_email_verification(page):
                mark_account_created(host, notes="pending email verification")
                await save_site_session(context, host)
                return AuthGate(kind="email_verify", detail=f"Verify email for {account.email}")
            mark_account_created(host)
            await save_site_session(context, host)
            return await detect_auth_gate(page)
        return AuthGate(kind="login", detail="Could not fill login fields")
    await submit_auth_form(page)
    await page.wait_for_timeout(2500)
    if await detect_captcha(page):
        return AuthGate(kind="captcha", detail="CAPTCHA after login")
    if await detect_email_verification(page):
        return AuthGate(kind="email_verify", detail=f"Verify email for {account.email}")
    await save_site_session(context, host)
    return await detect_auth_gate(page)
