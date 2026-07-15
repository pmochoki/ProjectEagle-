"""Shared ATS form helpers: contact fields, resume upload, cover letter."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from playwright.async_api import Page


async def fill_if_present(page: Page, selectors: list[str], value: str) -> bool:
    if not value:
        return False
    for sel in selectors:
        loc = page.locator(sel)
        if await loc.count() > 0:
            try:
                await loc.first.fill(value, timeout=3000)
                return True
            except Exception:
                continue
    return False


async def click_if_present(page: Page, selectors: list[str]) -> bool:
    for sel in selectors:
        loc = page.locator(sel)
        if await loc.count() > 0:
            try:
                await loc.first.click(timeout=3000)
                await page.wait_for_timeout(800)
                return True
            except Exception:
                continue
    return False


async def upload_resume(page: Page, resume_path: Path, selectors: list[str] | None = None) -> bool:
    if not resume_path.exists():
        return False
    sels = selectors or [
        "input[type='file'][name*='resume' i]",
        "input[type='file'][id*='resume' i]",
        "input[type='file'][data-automation-id*='file-upload']",
        "input[type='file'][accept*='pdf']",
        "input[type='file']",
    ]
    for sel in sels:
        loc = page.locator(sel)
        if await loc.count() > 0:
            try:
                await loc.first.set_input_files(str(resume_path), timeout=8000)
                return True
            except Exception:
                continue
    return False


async def fill_cover_letter(page: Page, cover_letter: str, selectors: list[str] | None = None) -> bool:
    if not cover_letter:
        return False
    sels = selectors or [
        "textarea[name*='cover' i]",
        "textarea[id*='cover' i]",
        "textarea[data-automation-id*='coverLetter']",
        "div[contenteditable='true'][data-placeholder*='cover' i]",
        "textarea[name='comments']",
        "textarea",
    ]
    for sel in sels:
        loc = page.locator(sel)
        if await loc.count() == 0:
            continue
        try:
            target = loc.first
            tag = (await target.evaluate("el => el.tagName")).lower()
            if tag == "textarea":
                await target.fill(cover_letter, timeout=4000)
            else:
                await target.click()
                await page.keyboard.type(cover_letter[:4000], delay=5)
            return True
        except Exception:
            continue
    return False


async def fill_basic_contact(page: Page, profile: dict[str, Any]) -> None:
    contact = profile.get("contact", {})
    full = (contact.get("full_name") or "").strip()
    parts = full.split()
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""

    await fill_if_present(
        page,
        [
            "#first_name",
            "input[name='first_name']",
            "input[name='firstName']",
            "input[name*='firstName']",
            "input[data-automation-id='legalNameSection_firstName']",
            "input[autocomplete='given-name']",
        ],
        first,
    )
    await fill_if_present(
        page,
        [
            "#last_name",
            "input[name='last_name']",
            "input[name='lastName']",
            "input[name*='lastName']",
            "input[data-automation-id='legalNameSection_lastName']",
            "input[autocomplete='family-name']",
        ],
        last,
    )
    await fill_if_present(
        page,
        [
            "input[name='name']",
            "input[autocomplete='name']",
            "input[data-automation-id='name']",
        ],
        full,
    )
    await fill_if_present(
        page,
        [
            "#email",
            "input[type='email']",
            "input[name='email']",
            "input[name*='email' i]",
            "input[data-automation-id*='email']",
            "input[autocomplete='email']",
        ],
        contact.get("email", ""),
    )
    await fill_if_present(
        page,
        [
            "#phone",
            "input[type='tel']",
            "input[name='phone']",
            "input[name*='phone' i]",
            "input[data-automation-id*='phone']",
            "input[autocomplete='tel']",
        ],
        contact.get("phone", ""),
    )


def write_temp_text(content: str, suffix: str) -> Path:
    fd, path = tempfile.mkstemp(suffix=suffix)
    Path(path).write_text(content or "", encoding="utf-8")
    return Path(path)
