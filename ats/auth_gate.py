"""Detect login / registration / CAPTCHA gates on employer apply pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from playwright.async_api import Page

GateKind = Literal["none", "login", "register", "captcha", "email_verify"]


@dataclass
class AuthGate:
    kind: GateKind
    detail: str = ""


_REGISTER_MARKERS = (
    "create account",
    "create an account",
    "sign up",
    "signup",
    "register",
    "new user",
    "join now",
)

_LOGIN_MARKERS = (
    "sign in",
    "log in",
    "login",
    "already have an account",
)

_VERIFY_MARKERS = (
    "verify your email",
    "check your email",
    "confirm your email",
    "email verification",
    "we sent you a",
    "activate your account",
)


async def detect_captcha(page: "Page") -> bool:
    body = (await page.content()).lower()
    return (
        "captcha" in body
        or "recaptcha" in body
        or "hcaptcha" in body
        or "cf-turnstile" in body
    )


async def detect_email_verification(page: "Page") -> bool:
    body = (await page.content()).lower()
    return any(m in body for m in _VERIFY_MARKERS)


async def page_looks_like_apply_form(page: "Page") -> bool:
    """Heuristic: resume upload or common application fields present."""
    if await page.locator("input[type='file']").count() > 0:
        return True
    for sel in (
        "textarea[name*='cover']",
        "input[name*='firstName']",
        "input[name*='first_name']",
        "#first_name",
        "input[name='email']",
        "input[data-automation-id*='email']",
        "button:has-text('Submit')",
        "button:has-text('Submit Application')",
    ):
        if await page.locator(sel).count() > 0:
            return True
    return False


async def detect_auth_gate(page: "Page") -> AuthGate:
    if await detect_captcha(page):
        return AuthGate(kind="captcha", detail="CAPTCHA / bot check on page")

    if await detect_email_verification(page):
        return AuthGate(kind="email_verify", detail="Email verification required")

    if await page_looks_like_apply_form(page):
        return AuthGate(kind="none", detail="Apply form visible")

    body = (await page.content()).lower()
    has_register = any(m in body for m in _REGISTER_MARKERS)
    has_login = any(m in body for m in _LOGIN_MARKERS)

    create_btn = page.locator(
        "a:has-text('Create Account'), button:has-text('Create Account'), "
        "a:has-text('Sign Up'), button:has-text('Sign Up'), "
        "a:has-text('Register'), button:has-text('Register')"
    )
    sign_in_btn = page.locator(
        "a:has-text('Sign In'), button:has-text('Sign In'), "
        "a:has-text('Log In'), button:has-text('Log In')"
    )

    if await create_btn.count() > 0 or (has_register and not await page_looks_like_apply_form(page)):
        return AuthGate(kind="register", detail="Registration / create-account wall")
    if await sign_in_btn.count() > 0 or has_login:
        return AuthGate(kind="login", detail="Sign-in wall")
    return AuthGate(kind="none", detail="No auth gate detected")
