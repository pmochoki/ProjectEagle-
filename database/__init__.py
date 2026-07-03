"""JobDragon database layer (Supabase Postgres)."""

from database.client import get_supabase_client
from database.jobs import (
    find_duplicate_job,
    insert_job_if_new,
    list_jobs,
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
    "get_supabase_client",
    "insert_job_if_new",
    "list_jobs",
    "store_qa_answer",
    "update_job_status",
]
