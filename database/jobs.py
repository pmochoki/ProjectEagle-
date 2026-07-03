from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from database.client import get_supabase_client
from database.models import JobInsert, JobRecord, JobStatus, _row_to_job, detect_ats_platform


def job_to_api_dict(job: JobRecord) -> dict[str, Any]:
    """Serialize a job for the Next.js frontend."""
    meta = job.metadata or {}
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location or "",
        "description": job.description or "",
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
    }


def find_duplicate_job(
    company: str,
    title: str,
    *,
    similarity_threshold: float = 0.72,
) -> str | None:
    """Return an existing job id when company+title fuzzy-match, else None."""
    client = get_supabase_client()
    result = client.rpc(
        "find_duplicate_job",
        {
            "p_company": company,
            "p_title": title,
            "p_similarity_threshold": similarity_threshold,
        },
    ).execute()

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

    client = get_supabase_client()
    result = client.table("jobs").insert(payload).execute()
    if not result.data:
        raise RuntimeError("Supabase insert returned no rows")

    return _row_to_job(result.data[0]), "inserted"


def get_job(job_id: str) -> JobRecord | None:
    client = get_supabase_client()
    result = client.table("jobs").select("*").eq("id", job_id).limit(1).execute()
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
) -> list[JobRecord]:
    client = get_supabase_client()
    query = client.table("jobs").select("*").order("date_found", desc=True).limit(limit)
    if status:
        query = query.eq("status", status)
    if external_only:
        query = query.eq("is_easy_apply", False)

    result = query.execute()
    return [_row_to_job(row) for row in (result.data or [])]


def get_stats() -> dict[str, int]:
    client = get_supabase_client()
    result = (
        client.table("jobs")
        .select("status, is_easy_apply, metadata")
        .eq("is_easy_apply", False)
        .execute()
    )
    rows = result.data or []

    stats = {
        "found": len(rows),
        "applied": 0,
        "pending": 0,
        "failed": 0,
        "needs_answer": 0,
        "with_cover_letter": 0,
    }
    for row in rows:
        status = row.get("status")
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


def save_scraped_jobs(jobs: list[Any]) -> int:
    """Insert scraped jobs via Supabase dedup logic. Returns count inserted."""
    inserted = 0
    for scraped in jobs:
        job_insert = JobInsert(
            source="linkedin",
            title=scraped.title,
            company=scraped.company,
            external_url=scraped.external_apply_url,
            location=scraped.location,
            description=scraped.description,
            is_easy_apply=scraped.is_easy_apply,
            metadata={
                "linkedin_url": scraped.linkedin_url,
            },
        )
        _, outcome = insert_job_if_new(job_insert)
        if outcome == "inserted":
            inserted += 1
    return inserted
