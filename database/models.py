from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal
from urllib.parse import urlparse

JobSource = Literal["linkedin", "profession_hu", "jobline_hu", "other"]
JobStatus = Literal["new", "queued", "applied", "needs_answer", "skipped", "failed"]
AtsPlatform = Literal[
    "greenhouse", "lever", "workday", "smartrecruiters", "custom", "unknown"
]


@dataclass(frozen=True)
class JobInsert:
    source: JobSource
    title: str
    company: str
    external_url: str
    location: str | None = None
    description: str | None = None
    source_job_id: str | None = None
    posted_date: date | None = None
    is_easy_apply: bool = False
    ats_platform: AtsPlatform | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class JobRecord:
    id: str
    source: JobSource
    title: str
    company: str
    external_url: str
    status: JobStatus
    location: str | None = None
    description: str | None = None
    ats_platform: AtsPlatform = "unknown"
    posted_date: date | None = None
    date_found: datetime | None = None
    date_applied: datetime | None = None
    is_easy_apply: bool = False
    metadata: dict[str, Any] | None = None


def detect_ats_platform(url: str) -> AtsPlatform:
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    combined = f"{host}{path}"

    if "greenhouse.io" in combined or "boards.greenhouse.io" in combined:
        return "greenhouse"
    if "jobs.lever.co" in combined or "lever.co" in combined:
        return "lever"
    if "myworkdayjobs.com" in combined:
        return "workday"
    if "smartrecruiters.com" in combined:
        return "smartrecruiters"
    return "unknown"


def _row_to_job(row: dict[str, Any]) -> JobRecord:
    posted = row.get("posted_date")
    if isinstance(posted, str) and posted:
        posted_date = date.fromisoformat(posted[:10])
    else:
        posted_date = None

    return JobRecord(
        id=row["id"],
        source=row["source"],
        title=row["title"],
        company=row["company"],
        external_url=row["external_url"],
        status=row["status"],
        location=row.get("location"),
        description=row.get("description"),
        ats_platform=row.get("ats_platform") or "unknown",
        posted_date=posted_date,
        date_found=row.get("date_found"),
        date_applied=row.get("date_applied"),
        is_easy_apply=bool(row.get("is_easy_apply")),
        metadata=row.get("metadata") or {},
    )
