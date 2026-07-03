from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Page

from ai.answers import generate_application_answer
from ats.base import ApplyResult
from database.jobs import update_job_failure, update_job_metadata, update_job_status
from notifications.telegram import notify_apply_review_pending, notify_captcha_manual, notify_question_escalation


async def _detect_captcha(page: Page) -> bool:
    body = (await page.content()).lower()
    return "captcha" in body or "recaptcha" in body or "hcaptcha" in body


async def _fill_if_present(page: Page, selectors: list[str], value: str) -> None:
    if not value:
        return
    for sel in selectors:
        loc = page.locator(sel)
        if await loc.count() > 0:
            await loc.first.fill(value, timeout=3000)
            return


async def _upload_file(page: Page, selectors: list[str], file_path: Path) -> bool:
    for sel in selectors:
        loc = page.locator(sel)
        if await loc.count() > 0:
            await loc.first.set_input_files(str(file_path), timeout=5000)
            return True
    return False


async def _fill_custom_questions(
    page: Page,
    profile: dict[str, Any],
    job: dict[str, Any],
    job_id: str,
) -> ApplyResult | None:
    """Fill known textareas; escalate if unanswered required field remains."""
    textareas = page.locator("textarea")
    count = await textareas.count()
    for i in range(count):
        field = textareas.nth(i)
        if not await field.is_visible():
            continue
        current = await field.input_value()
        if current.strip():
            continue

        label = ""
        field_id = await field.get_attribute("id") or ""
        if field_id:
            label_loc = page.locator(f"label[for='{field_id}']")
            if await label_loc.count():
                label = (await label_loc.first.inner_text()).strip()

        question = label or f"Free-text question #{i + 1}"
        try:
            answer = generate_application_answer(question, profile, job=job)
        except Exception:
            update_job_status(job_id, "needs_answer")
            update_job_metadata(job_id, pending_question=question)
            notify_question_escalation(
                job_title=job.get("title", ""),
                company=job.get("company", ""),
                external_url=job.get("external_url", ""),
                job_id=job_id,
                question_text=question,
            )
            return ApplyResult(
                outcome="needs_answer",
                message=f"Escalated question to Telegram: {question}",
                pending_question=question,
            )

        await field.fill(answer)

    return None


async def apply_greenhouse(
    page: Page,
    *,
    job_id: str,
    profile: dict[str, Any],
    job: dict[str, Any],
    cover_letter: str,
    resume_path: Path | None,
    review_before_submit: bool,
) -> ApplyResult:
    contact = profile.get("contact", {})
    await page.goto(job["external_url"], wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(2000)

    if await _detect_captcha(page):
        notify_captcha_manual(job_id=job_id, job_title=job.get("title", ""), url=job["external_url"])
        return ApplyResult(outcome="captcha", message="CAPTCHA on apply page — solve manually")

    await _fill_if_present(
        page,
        ["#first_name", "input[name='job_application[first_name]']", "input[name='first_name']"],
        contact.get("full_name", "").split()[0] if contact.get("full_name") else "",
    )
    name_parts = (contact.get("full_name") or "").split()
    last = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
    await _fill_if_present(
        page,
        ["#last_name", "input[name='job_application[last_name]']", "input[name='last_name']"],
        last,
    )
    await _fill_if_present(
        page,
        ["#email", "input[name='job_application[email]']", "input[type='email']"],
        contact.get("email", ""),
    )
    await _fill_if_present(
        page,
        ["#phone", "input[name='job_application[phone]']", "input[type='tel']"],
        contact.get("phone", ""),
    )

    if resume_path and resume_path.exists():
        uploaded = await _upload_file(
            page,
            [
                "input[type='file'][name*='resume']",
                "input[type='file'][id*='resume']",
                "input[type='file']",
            ],
            resume_path,
        )
        if not uploaded:
            return ApplyResult(outcome="failed", message="Could not find resume file input")

    if cover_letter:
        await _fill_if_present(
            page,
            [
                "textarea[name*='cover_letter']",
                "textarea[id*='cover_letter']",
                "#cover_letter",
            ],
            cover_letter,
        )

    escalated = await _fill_custom_questions(page, profile, job, job_id)
    if escalated:
        return escalated

    submit = page.locator(
        "input[type='submit'][value*='Submit'], "
        "button[type='submit'], "
        "input#submit_app, "
        "button:has-text('Submit application')"
    )
    if await submit.count() == 0:
        update_job_failure(job_id, "Submit button not found on Greenhouse form")
        return ApplyResult(outcome="failed", message="Submit button not found")

    if review_before_submit:
        update_job_status(job_id, "queued")
        update_job_metadata(job_id, review_pending=True)
        notify_apply_review_pending(
            job_title=job.get("title", ""),
            company=job.get("company", ""),
            job_id=job_id,
            external_url=job["external_url"],
        )
        return ApplyResult(
            outcome="review_pending",
            message="Form filled; waiting for manual approval before submit",
        )

    try:
        await submit.first.click(timeout=5000)
        await page.wait_for_timeout(3000)
    except PlaywrightTimeoutError as exc:
        update_job_failure(job_id, f"Submit click failed: {exc}")
        return ApplyResult(outcome="failed", message=str(exc))

    if await _detect_captcha(page):
        notify_captcha_manual(job_id=job_id, job_title=job.get("title", ""), url=job["external_url"])
        return ApplyResult(outcome="captcha", message="CAPTCHA after submit — solve manually")

    update_job_status(job_id, "applied")
    update_job_metadata(job_id, review_pending=False)
    return ApplyResult(outcome="applied", message="Application submitted on Greenhouse")


def write_temp_text(content: str, suffix: str) -> Path:
    fd, path = tempfile.mkstemp(suffix=suffix)
    Path(path).write_text(content, encoding="utf-8")
    return Path(path)
