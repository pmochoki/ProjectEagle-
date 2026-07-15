from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from playwright.async_api import async_playwright

from ai.tailor import tailor_for_job
from ats.accounts import host_for_url, load_site_context, save_site_session
from ats.base import ApplyResult
from ats.forms import write_temp_text
from ats.greenhouse import apply_greenhouse
from ats.lever import apply_lever
from ats.smartrecruiters import apply_smartrecruiters
from ats.workday import apply_workday
from database.jobs import (
    get_job,
    job_to_api_dict,
    record_application_result,
    save_tailored_application,
    update_job_failure,
)
from database.profile import load_profile
from scraper.config import ScraperConfig, review_before_submit


SUPPORTED_APPLY_PLATFORMS = ("greenhouse", "lever", "workday", "smartrecruiters")


async def _apply_job_async(job_id: str, *, force_submit: bool = False) -> ApplyResult:
    job_rec = get_job(job_id)
    if not job_rec:
        raise ValueError(f"Job not found: {job_id}")

    profile = load_profile()
    job = job_to_api_dict(job_rec)
    meta = job_rec.metadata or {}

    cover_letter = meta.get("cover_letter", "")
    resume_md = meta.get("tailored_resume")
    if not cover_letter or not resume_md:
        tailored = tailor_for_job(
            profile,
            {
                "title": job_rec.title,
                "company": job_rec.company,
                "location": job_rec.location or "",
                "description": job_rec.description or "",
            },
        )
        save_tailored_application(job_id, tailored)
        cover_letter = tailored.cover_letter
        resume_md = tailored.tailored_resume

    resume_path = write_temp_text(resume_md, suffix="_resume.txt")
    review = False if force_submit else review_before_submit()
    job_payload = {
        "title": job_rec.title,
        "company": job_rec.company,
        "external_url": job_rec.external_url,
        "description": job_rec.description or "",
    }

    cfg = ScraperConfig.from_env()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=cfg.headless, slow_mo=75)
        context = await load_site_context(browser, job_rec.external_url, headless=cfg.headless)
        page = await context.new_page()
        try:
            platform = job_rec.ats_platform
            common = dict(
                job_id=job_id,
                profile=profile,
                job=job_payload,
                cover_letter=cover_letter,
                resume_path=resume_path,
                review_before_submit=review,
            )
            if platform == "greenhouse":
                result = await apply_greenhouse(page, **common)
            elif platform == "lever":
                result = await apply_lever(page, **common)
            elif platform == "workday":
                result = await apply_workday(page, context=context, **common)
            elif platform == "smartrecruiters":
                result = await apply_smartrecruiters(page, context=context, **common)
            else:
                update_job_failure(job_id, f"Unsupported ATS platform: {platform}")
                result = ApplyResult(
                    outcome="failed",
                    message=f"No filler for ATS platform: {platform}",
                )

            # Persist session after successful auth/fill paths
            if result.outcome in ("applied", "review_pending", "needs_verification"):
                try:
                    await save_site_session(context, host_for_url(job_rec.external_url))
                except Exception:
                    pass
        except Exception as exc:
            update_job_failure(job_id, str(exc))
            result = ApplyResult(outcome="failed", message=str(exc))
        finally:
            await browser.close()
            if resume_path.exists():
                resume_path.unlink(missing_ok=True)

    return result


def apply_to_job(job_id: str, *, force_submit: bool = False) -> dict[str, Any]:
    result = asyncio.run(_apply_job_async(job_id, force_submit=force_submit))
    if get_job(job_id):
        record_application_result(job_id, outcome=result.outcome, message=result.message)
    return asdict(result)


async def submit_after_review(job_id: str) -> ApplyResult:
    """Complete submit for a job that was paused at review step."""
    return await _apply_job_async(job_id, force_submit=True)
