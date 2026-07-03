from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.async_api import Page

from ai.answers import generate_application_answer
from ats.base import ApplyResult
from database.jobs import update_job_failure, update_job_metadata, update_job_status
from notifications.telegram import notify_apply_review_pending, notify_captcha_manual, notify_question_escalation


async def _detect_captcha(page: Page) -> bool:
    body = (await page.content()).lower()
    return "captcha" in body or "recaptcha" in body


async def apply_lever(
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
        return ApplyResult(outcome="captcha", message="CAPTCHA on Lever page — solve manually")

    name = contact.get("full_name", "")
    for sel, val in [
        ("input[name='name']", name),
        ("input[name='email']", contact.get("email", "")),
        ("input[name='phone']", contact.get("phone", "")),
    ]:
        loc = page.locator(sel)
        if await loc.count() and val:
            await loc.first.fill(val)

    if resume_path and resume_path.exists():
        file_input = page.locator("input[type='file']")
        if await file_input.count():
            await file_input.first.set_input_files(str(resume_path))

    if cover_letter:
        loc = page.locator("textarea[name='comments'], textarea")
        if await loc.count():
            await loc.first.fill(cover_letter)

    custom = page.locator(".application-question textarea, .application-field textarea")
    count = await custom.count()
    for i in range(count):
        field = custom.nth(i)
        if (await field.input_value()).strip():
            continue
        label_el = field.locator("xpath=ancestor::li//label")
        question = (
            (await label_el.first.inner_text()).strip()
            if await label_el.count()
            else f"Lever question #{i + 1}"
        )
        try:
            answer = generate_application_answer(question, profile, job=job)
            await field.fill(answer)
        except Exception:
            update_job_status(job_id, "needs_answer")
            update_job_metadata(job_id, pending_question=question)
            notify_question_escalation(
                job_title=job.get("title", ""),
                company=job.get("company", ""),
                external_url=job["external_url"],
                job_id=job_id,
                question_text=question,
            )
            return ApplyResult(outcome="needs_answer", message=question, pending_question=question)

    submit = page.locator("button[type='submit'], button.postings-btn-submit")
    if await submit.count() == 0:
        update_job_failure(job_id, "Lever submit button not found")
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
        return ApplyResult(outcome="review_pending", message="Lever form filled; awaiting approval")

    await submit.first.click()
    await page.wait_for_timeout(3000)
    update_job_status(job_id, "applied")
    return ApplyResult(outcome="applied", message="Application submitted on Lever")
