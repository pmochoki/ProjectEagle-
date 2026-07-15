"""SmartRecruiters apply + optional account registration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.async_api import Page

from ats.accounts import auto_register_enabled, host_for_url, save_site_session
from ats.auth_gate import detect_captcha
from ats.base import ApplyResult
from ats.forms import fill_basic_contact, fill_cover_letter, upload_resume
from ats.register import ensure_authenticated
from database.jobs import update_job_failure, update_job_metadata, update_job_status
from notifications.telegram import (
    notify_application_submitted,
    notify_apply_review_pending,
    notify_captcha_manual,
    notify_needs_account,
    notify_needs_verification,
)


async def apply_smartrecruiters(
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
    await page.wait_for_timeout(2000)

    if await detect_captcha(page):
        notify_captcha_manual(job_id=job_id, job_title=job.get("title", ""), url=url)
        return ApplyResult(outcome="captcha", message="CAPTCHA on SmartRecruiters")

    apply_btn = page.locator(
        "button:has-text('Apply'), a:has-text('Apply now'), a:has-text('Apply')"
    )
    if await apply_btn.count() > 0:
        try:
            await apply_btn.first.click(timeout=4000)
            await page.wait_for_timeout(1500)
        except Exception:
            pass

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
        await upload_resume(page, resume_path)
    await fill_cover_letter(page, cover_letter)

    submit = page.locator(
        "button[type='submit'], button:has-text('Submit'), "
        "button:has-text('Send application'), button:has-text('Apply')"
    )
    if await submit.count() == 0:
        update_job_failure(job_id, "SmartRecruiters submit not found")
        return ApplyResult(outcome="failed", message="Submit button not found")

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
            message="SmartRecruiters form filled; waiting for approval",
        )

    await submit.first.click()
    await page.wait_for_timeout(3000)
    await save_site_session(context, host_for_url(url))
    update_job_status(job_id, "applied")
    notify_application_submitted(
        job_title=job.get("title", ""),
        company=job.get("company", ""),
        job_id=job_id,
    )
    return ApplyResult(outcome="applied", message="Application submitted on SmartRecruiters")
