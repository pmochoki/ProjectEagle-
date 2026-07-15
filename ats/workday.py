"""Workday careers apply + optional account registration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.async_api import Page

from ai.answers import generate_application_answer
from ats.accounts import host_for_url, save_site_session
from ats.auth_gate import detect_captcha
from ats.base import ApplyResult
from ats.forms import fill_basic_contact, fill_cover_letter, fill_if_present, upload_resume
from ats.register import ensure_authenticated
from database.jobs import update_job_failure, update_job_metadata, update_job_status
from notifications.telegram import (
    notify_application_submitted,
    notify_apply_review_pending,
    notify_captcha_manual,
    notify_needs_account,
    notify_needs_verification,
    notify_question_escalation,
)


async def _fill_workday_questions(page: Page, profile: dict[str, Any], job: dict[str, Any], job_id: str):
    textareas = page.locator("textarea")
    count = await textareas.count()
    for i in range(min(count, 8)):
        field = textareas.nth(i)
        if not await field.is_visible():
            continue
        try:
            current = await field.input_value()
        except Exception:
            continue
        if current.strip():
            continue
        question = f"Workday free-text question #{i + 1}"
        try:
            answer = generate_application_answer(question, profile, job=job)
            await field.fill(answer.text)
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
                message=question,
                pending_question=question,
            )
    return None


async def apply_workday(
    page: Page,
    *,
    job_id: str,
    profile: dict[str, Any],
    job: dict[str, Any],
    cover_letter: str,
    resume_path: Path | None,
    review_before_submit: bool,
    context,
) -> ApplyResult:
    url = job["external_url"]
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(2500)

    if await detect_captcha(page):
        notify_captcha_manual(job_id=job_id, job_title=job.get("title", ""), url=url)
        return ApplyResult(outcome="captcha", message="CAPTCHA on Workday page")

    # Workday often needs "Apply" / "Start Your Application" first
    for label in ("Apply", "Start Your Application", "Apply Manually", "Autofill with Resume"):
        btn = page.locator(f"button:has-text('{label}'), a:has-text('{label}')")
        if await btn.count() > 0:
            try:
                await btn.first.click(timeout=4000)
                await page.wait_for_timeout(2000)
            except Exception:
                pass
            break

    from ats.accounts import auto_register_enabled

    if auto_register_enabled():
        gate = await ensure_authenticated(
            page, job_url=url, profile=profile, context=context
        )
        if gate.kind == "captcha":
            notify_captcha_manual(job_id=job_id, job_title=job.get("title", ""), url=url)
            return ApplyResult(outcome="captcha", message=gate.detail)
        if gate.kind == "email_verify":
            update_job_status(job_id, "needs_answer")
            update_job_metadata(job_id, pending_question=gate.detail, needs_verification=True)
            notify_needs_verification(
                job_id=job_id,
                job_title=job.get("title", ""),
                company=job.get("company", ""),
                url=url,
                detail=gate.detail,
            )
            return ApplyResult(outcome="needs_verification", message=gate.detail)
        if gate.kind in ("register", "login"):
            update_job_status(job_id, "failed")
            update_job_metadata(job_id, needs_account=True)
            notify_needs_account(
                job_id=job_id,
                job_title=job.get("title", ""),
                company=job.get("company", ""),
                url=url,
                detail=gate.detail,
            )
            return ApplyResult(outcome="needs_account", message=gate.detail)

    await fill_basic_contact(page, profile)
    if resume_path:
        uploaded = await upload_resume(
            page,
            resume_path,
            [
                "input[type='file'][data-automation-id*='file-upload']",
                "input[type='file'][data-uxi-element-id*='file']",
                "input[type='file']",
            ],
        )
        if not uploaded:
            # Workday sometimes hides file input behind a dropzone — still try continue
            update_job_metadata(job_id, resume_upload_uncertain=True)

    await fill_cover_letter(
        page,
        cover_letter,
        [
            "textarea[data-automation-id*='coverLetter']",
            "textarea[id*='coverLetter']",
            "textarea[name*='cover']",
            "textarea",
        ],
    )

    # Common Workday profile fields
    contact = profile.get("contact", {})
    await fill_if_present(
        page,
        ["input[data-automation-id='addressSection_addressLine1']", "input[autocomplete='address-line1']"],
        contact.get("location", ""),
    )

    escalated = await _fill_workday_questions(page, profile, job, job_id)
    if escalated:
        return escalated

    submit = page.locator(
        "button[data-automation-id='bottom-navigation-next-button'], "
        "button:has-text('Submit'), "
        "button:has-text('Submit Application'), "
        "button:has-text('Save and Continue'), "
        "button:has-text('Continue')"
    )
    if await submit.count() == 0:
        update_job_failure(job_id, "Workday submit/continue control not found")
        return ApplyResult(outcome="failed", message="Workday submit control not found")

    if review_before_submit:
        await save_site_session(context, host_for_url(url))
        update_job_status(job_id, "queued")
        update_job_metadata(job_id, review_pending=True)
        notify_apply_review_pending(
            job_title=job.get("title", ""),
            company=job.get("company", ""),
            job_id=job_id,
            external_url=url,
        )
        return ApplyResult(
            outcome="review_pending",
            message="Workday form filled; waiting for approval before submit",
        )

    try:
        await submit.first.click(timeout=5000)
        await page.wait_for_timeout(3000)
    except Exception as exc:
        update_job_failure(job_id, f"Workday submit failed: {exc}")
        return ApplyResult(outcome="failed", message=str(exc))

    if await detect_captcha(page):
        notify_captcha_manual(job_id=job_id, job_title=job.get("title", ""), url=url)
        return ApplyResult(outcome="captcha", message="CAPTCHA after Workday submit")

    await save_site_session(context, host_for_url(url))
    update_job_status(job_id, "applied")
    update_job_metadata(job_id, review_pending=False)
    notify_application_submitted(
        job_title=job.get("title", ""),
        company=job.get("company", ""),
        job_id=job_id,
    )
    return ApplyResult(outcome="applied", message="Application submitted on Workday")
