from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from database.client import get_supabase_client
from database.models import JobInsert, JobRecord, JobStatus, _row_to_job, detect_ats_platform


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


def list_jobs(
    *,
    status: JobStatus | None = None,
    limit: int = 100,
) -> list[JobRecord]:
    client = get_supabase_client()
    query = client.table("jobs").select("*").order("date_found", desc=True).limit(limit)
    if status:
        query = query.eq("status", status)

    result = query.execute()
    return [_row_to_job(row) for row in (result.data or [])]
