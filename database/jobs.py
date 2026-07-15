from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from database.auth_context import active_user_id
from database.client import get_supabase_client
from database.models import JobInsert, JobRecord, JobStatus, _row_to_job, detect_ats_platform

_DB_SOURCES = {"linkedin", "profession_hu", "jobline_hu", "other"}


def _normalize_source(source: str) -> str:
    if source in _DB_SOURCES:
        return source
    if source.startswith("linkedin"):
        return "linkedin"
    return "other"


def job_to_api_dict(job: JobRecord) -> dict[str, Any]:
    """Serialize a job for the Next.js frontend."""
    meta = job.metadata or {}
    application_outcome = meta.get("application_outcome")
    if not application_outcome:
        if job.status == "applied":
            application_outcome = "applied"
        elif job.status == "failed":
            application_outcome = "failed"
        elif job.status == "queued" and meta.get("review_pending"):
            application_outcome = "review_pending"
        elif job.status == "needs_answer":
            application_outcome = "needs_answer"

    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location or "",
        "description": job.description or "",
        "summary": meta.get("summary"),
        "description_en": meta.get("description_en"),
        "fit_probability": meta.get("fit_probability"),
        "fit_rationale": meta.get("fit_rationale"),
        "match_score": meta.get("match_score"),
        "match_reasons": meta.get("match_reasons") or [],
        "sponsorship_offered": meta.get("sponsorship_offered"),
        "sponsorship_status": meta.get("sponsorship_status"),
        "applicant_needs_sponsorship": meta.get("applicant_needs_sponsorship"),
        "opportunity_type": meta.get("opportunity_type", "job"),
        "linkedin_url": meta.get("linkedin_url", ""),
        "external_apply_url": job.external_url,
        "apply_url": job.external_url,
        "is_easy_apply": job.is_easy_apply,
        "status": job.status,
        "cover_letter": meta.get("cover_letter"),
        "scraped_at": job.date_found,
        "applied_at": job.date_applied,
        "ats_platform": job.ats_platform,
        "source": job.source,
        "scrape_source": meta.get("scrape_source", job.source),
        "source_job_id": meta.get("adzuna_id")
        or meta.get("eures_id")
        or meta.get("remoteok_id")
        or meta.get("arbeitnow_slug"),
        "failure_reason": meta.get("failure_reason"),
        "application_outcome": application_outcome,
        "application_message": meta.get("application_message"),
        "review_pending": meta.get("review_pending", False),
        "pending_question": meta.get("pending_question"),
        "search_location": meta.get("search_location"),
    }


def find_duplicate_job(
    company: str,
    title: str,
    *,
    similarity_threshold: float = 0.72,
    user_id: str | None = None,
) -> str | None:
    """Return an existing job id when company+title fuzzy-match, else None."""
    uid = user_id or active_user_id()
    client = get_supabase_client()
    params: dict[str, Any] = {
        "p_company": company,
        "p_title": title,
        "p_similarity_threshold": similarity_threshold,
    }
    if uid:
        params["p_user_id"] = uid
    result = client.rpc("find_duplicate_job", params).execute()

    if not result.data:
        return None
    return str(result.data)


def insert_job_if_new(
    job: JobInsert,
    *,
    similarity_threshold: float = 0.72,
    skip_easy_apply: bool = True,
) -> tuple[JobRecord | None, str]:
    """
    Insert a discovered job if it is not a duplicate.

    Returns (job_record_or_none, outcome) where outcome is one of:
    inserted, duplicate, skipped_easy_apply
    """
    if skip_easy_apply and job.is_easy_apply:
        return None, "skipped_easy_apply"

    duplicate_id = find_duplicate_job(
        job.company, job.title, similarity_threshold=similarity_threshold
    )
    if duplicate_id:
        return None, "duplicate"

    ats = job.ats_platform or detect_ats_platform(job.external_url)
    payload: dict[str, Any] = {
        "source": job.source,
        "title": job.title,
        "company": job.company,
        "external_url": job.external_url,
        "location": job.location,
        "description": job.description,
        "source_job_id": job.source_job_id,
        "posted_date": job.posted_date.isoformat() if job.posted_date else None,
        "is_easy_apply": job.is_easy_apply,
        "ats_platform": ats,
        "metadata": job.metadata or {},
        "status": "new",
    }
    uid = active_user_id()
    if uid:
        payload["user_id"] = uid

    client = get_supabase_client()
    result = client.table("jobs").insert(payload).execute()
    if not result.data:
        raise RuntimeError("Supabase insert returned no rows")

    return _row_to_job(result.data[0]), "inserted"


def _job_query(client, user_id: str | None):
    query = client.table("jobs").select("*")
    if user_id:
        query = query.eq("user_id", user_id)
    return query


def get_job(job_id: str, *, user_id: str | None = None) -> JobRecord | None:
    uid = user_id or active_user_id()
    client = get_supabase_client()
    query = _job_query(client, uid).eq("id", job_id).limit(1)
    result = query.execute()
    if not result.data:
        return None
    return _row_to_job(result.data[0])


def update_job_status(
    job_id: str,
    status: JobStatus,
    *,
    date_applied: datetime | None = None,
) -> JobRecord:
    """Update job status; sets date_applied automatically when status is applied."""
    payload: dict[str, Any] = {"status": status}
    if status == "applied":
        payload["date_applied"] = (date_applied or datetime.now(timezone.utc)).isoformat()

    client = get_supabase_client()
    result = (
        client.table("jobs").update(payload).eq("id", job_id).select("*").single().execute()
    )
    if not result.data:
        raise RuntimeError(f"Job not found: {job_id}")

    return _row_to_job(result.data)


def update_job_metadata(job_id: str, **fields: Any) -> JobRecord:
    job = get_job(job_id)
    if not job:
        raise RuntimeError(f"Job not found: {job_id}")
    metadata = dict(job.metadata or {})
    metadata.update(fields)
    client = get_supabase_client()
    result = (
        client.table("jobs")
        .update({"metadata": metadata})
        .eq("id", job_id)
        .select("*")
        .single()
        .execute()
    )
    if not result.data:
        raise RuntimeError(f"Failed to update metadata for job: {job_id}")
    return _row_to_job(result.data)


def update_job_failure(job_id: str, error: str) -> JobRecord:
    """Mark job failed and persist error reason in metadata."""
    job = get_job(job_id)
    if not job:
        raise RuntimeError(f"Job not found: {job_id}")
    metadata = dict(job.metadata or {})
    metadata["failure_reason"] = error
    metadata["last_error_at"] = datetime.now(timezone.utc).isoformat()
    client = get_supabase_client()
    result = (
        client.table("jobs")
        .update({"status": "failed", "metadata": metadata})
        .eq("id", job_id)
        .select("*")
        .single()
        .execute()
    )
    if not result.data:
        raise RuntimeError(f"Failed to mark job failed: {job_id}")
    return _row_to_job(result.data)


def update_job_cover_letter(job_id: str, cover_letter: str) -> JobRecord:
    job = get_job(job_id)
    if not job:
        raise RuntimeError(f"Job not found: {job_id}")

    metadata = dict(job.metadata or {})
    metadata["cover_letter"] = cover_letter

    client = get_supabase_client()
    result = (
        client.table("jobs")
        .update({"metadata": metadata})
        .eq("id", job_id)
        .select("*")
        .single()
        .execute()
    )
    if not result.data:
        raise RuntimeError(f"Failed to update cover letter for job: {job_id}")
    return _row_to_job(result.data)


def list_jobs(
    *,
    status: JobStatus | None = None,
    external_only: bool = True,
    limit: int = 100,
    user_id: str | None = None,
) -> list[JobRecord]:
    uid = user_id or active_user_id()
    client = get_supabase_client()
    query = _job_query(client, uid).order("date_found", desc=True).limit(limit)
    if status:
        query = query.eq("status", status)
    if external_only:
        query = query.eq("is_easy_apply", False)

    result = query.execute()
    return [_row_to_job(row) for row in (result.data or [])]


def update_job_summary(job_id: str, summary: str) -> JobRecord:
    return update_job_metadata(job_id, summary=summary)


def update_job_analysis(
    job_id: str,
    *,
    summary: str,
    description_en: str,
    fit_probability: int,
    fit_rationale: str,
) -> JobRecord:
    return update_job_metadata(
        job_id,
        summary=summary,
        description_en=description_en,
        fit_probability=fit_probability,
        fit_rationale=fit_rationale,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )


def record_application_result(job_id: str, *, outcome: str, message: str) -> JobRecord:
    """Persist last apply attempt outcome for dashboard visibility."""
    fields: dict[str, Any] = {
        "application_outcome": outcome,
        "application_message": message,
        "application_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if outcome == "applied":
        fields["review_pending"] = False
    return update_job_metadata(job_id, **fields)


def get_stats(*, user_id: str | None = None) -> dict[str, int]:
    uid = user_id or active_user_id()
    client = get_supabase_client()
    query = client.table("jobs").select("status, is_easy_apply, metadata").eq("is_easy_apply", False)
    if uid:
        query = query.eq("user_id", uid)
    result = query.execute()
    rows = result.data or []

    stats = {
        "found": len(rows),
        "applied": 0,
        "pending": 0,
        "failed": 0,
        "needs_answer": 0,
        "with_cover_letter": 0,
        "scholarships": 0,
        "applications_successful": 0,
        "applications_failed": 0,
        "applications_pending_review": 0,
    }
    for row in rows:
        status = row.get("status")
        meta = row.get("metadata") or {}
        if meta.get("opportunity_type") == "scholarship":
            stats["scholarships"] += 1

        outcome = meta.get("application_outcome")
        if outcome == "applied" or status == "applied":
            stats["applications_successful"] += 1
        elif outcome == "failed" or status == "failed":
            stats["applications_failed"] += 1
        elif outcome == "review_pending" or (status == "queued" and meta.get("review_pending")):
            stats["applications_pending_review"] += 1

        if status == "applied":
            stats["applied"] += 1
        elif status in ("new", "queued"):
            stats["pending"] += 1
        elif status == "failed":
            stats["failed"] += 1
        elif status == "needs_answer":
            stats["needs_answer"] += 1

        meta = row.get("metadata") or {}
        if meta.get("cover_letter"):
            stats["with_cover_letter"] += 1

    return stats


def list_jobs_pending_review(*, limit: int = 10) -> list[JobRecord]:
    pending: list[JobRecord] = []
    for job in list_jobs(limit=100):
        if (job.metadata or {}).get("review_pending"):
            pending.append(job)
        if len(pending) >= limit:
            break
    return pending


def list_apply_candidates(*, limit: int = 20) -> list[JobRecord]:
    """Jobs ready for careful auto-apply (Greenhouse/Lever, not scholarships), best match first."""
    from scraper.match_score import compute_match_score

    jobs = list_jobs(status="new", limit=100)
    candidates: list[JobRecord] = []
    for job in jobs:
        meta = job.metadata or {}
        if meta.get("opportunity_type") == "scholarship":
            continue
        if job.ats_platform not in ("greenhouse", "lever"):
            continue
        if not job.external_url or job.is_easy_apply:
            continue
        candidates.append(job)
    candidates.sort(key=compute_match_score, reverse=True)
    return candidates[:limit]


def save_scraped_jobs(jobs: list[Any], *, default_source: str = "linkedin") -> int:
    """Insert scraped jobs via Supabase dedup logic. Returns count inserted."""
    from dataclasses import replace

    from scraper.config import ScraperConfig
    from scraper.normalize import scraped_to_job_insert
    from scraper.profile_match import enrich_listing_metadata

    cfg = ScraperConfig.from_env()
    profile = None
    try:
        from database.profile import ProfileError, load_profile

        profile = load_profile()
    except ProfileError:
        profile = None

    inserted = 0
    for scraped in jobs:
        job_insert = scraped_to_job_insert(scraped, cfg, default_source=default_source)
        if job_insert is None:
            continue
        meta = job_insert.metadata or {}
        opportunity_type = meta.get("opportunity_type", "job")
        enriched = enrich_listing_metadata(
            meta,
            profile,
            title=job_insert.title,
            location=job_insert.location or "",
            description=job_insert.description or "",
            opportunity_type=opportunity_type,
            ats_platform=job_insert.ats_platform or "unknown",
            posted_date=job_insert.posted_date,
        )
        job_insert = replace(job_insert, metadata=enriched)
        _, outcome = insert_job_if_new(job_insert)
        if outcome == "inserted":
            inserted += 1
    return inserted


def rescore_jobs_for_user(*, user_id: str | None = None, limit: int = 500) -> int:
    """Recompute profile match scores for existing jobs (e.g. after profile update)."""
    from database.profile import ProfileError, load_profile
    from scraper.profile_match import enrich_listing_metadata

    uid = user_id or active_user_id()
    try:
        profile = load_profile(user_id=uid)
    except ProfileError:
        profile = None

    updated = 0
    for job in list_jobs(limit=limit, user_id=uid):
        meta = dict(job.metadata or {})
        enriched = enrich_listing_metadata(
            meta,
            profile,
            title=job.title,
            location=job.location or "",
            description=job.description or "",
            opportunity_type=meta.get("opportunity_type", "job"),
            ats_platform=job.ats_platform or "unknown",
            posted_date=job.posted_date,
        )
        update_job_metadata(job.id, **enriched)
        updated += 1
    return updated
