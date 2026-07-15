"""Priority score 0–100 for apply queue ordering."""

from __future__ import annotations

from database.models import JobRecord


def compute_match_score(job: JobRecord, profile: dict | None = None) -> int:
    """Use cached profile match score when present, else compute on the fly."""
    meta = job.metadata or {}
    cached = meta.get("match_score")
    if cached is not None:
        try:
            return max(0, min(100, int(cached)))
        except (TypeError, ValueError):
            pass

    from scraper.profile_match import compute_profile_match

    if profile is None:
        try:
            from database.profile import ProfileError, load_profile

            profile = load_profile()
        except ProfileError:
            profile = None

    opportunity_type = meta.get("opportunity_type", "job")
    score, _, _ = compute_profile_match(
        profile,
        title=job.title or "",
        location=job.location or "",
        description=job.description or "",
        opportunity_type=opportunity_type,
        ats_platform=job.ats_platform or "unknown",
        posted_date=job.posted_date,
        date_found=job.date_found,
    )
    return score
