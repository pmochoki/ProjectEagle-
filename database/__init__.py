"""JantaSearcher database layer (Supabase Postgres)."""

from database.client import get_supabase_client
from database.jobs import (
    find_duplicate_job,
    get_job,
    get_stats,
    insert_job_if_new,
    job_to_api_dict,
    list_jobs,
    save_scraped_jobs,
    update_job_cover_letter,
    update_job_failure,
    update_job_metadata,
    update_job_status,
)
from database.models import JobInsert, JobRecord, JobStatus, detect_ats_platform
from database.qa_memory import QAMemoryRecord, find_qa_answer, store_qa_answer

__all__ = [
    "JobInsert",
    "JobRecord",
    "JobStatus",
    "QAMemoryRecord",
    "detect_ats_platform",
    "find_duplicate_job",
    "find_qa_answer",
    "get_job",
    "get_stats",
    "get_supabase_client",
    "insert_job_if_new",
    "job_to_api_dict",
    "list_jobs",
    "save_scraped_jobs",
    "store_qa_answer",
    "update_job_cover_letter",
    "update_job_failure",
    "update_job_metadata",
    "update_job_status",
]
