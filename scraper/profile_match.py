"""Profile-aware match score (0–100) and human-readable match reasons."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from scraper.hungary_focus import is_hungary_location
from scraper.sponsorship import applicant_needs_sponsorship, detect_sponsorship

_PROFILE_FIELDS = (
    "mechatronics",
    "robotics",
    "automation",
    "mechanical",
    "control",
    "embedded",
    "manufacturing",
    "engineer",
    "graduate",
)


def _flatten_skills(profile: dict[str, Any]) -> list[str]:
    skills = profile.get("skills") or {}
    out: list[str] = []
    if isinstance(skills, dict):
        for items in skills.values():
            if isinstance(items, list):
                out.extend(str(item) for item in items if item)
    return out


def _education_fields(profile: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for row in profile.get("education") or []:
        if not isinstance(row, dict):
            continue
        for key in ("field", "degree", "institution"):
            value = row.get(key)
            if value:
                fields.append(str(value))
    return fields


def _experience_roles(profile: dict[str, Any]) -> list[str]:
    roles: list[str] = []
    for row in profile.get("experience") or []:
        if isinstance(row, dict) and row.get("role"):
            roles.append(str(row["role"]))
    return roles


def _project_technologies(profile: dict[str, Any]) -> list[str]:
    tech: list[str] = []
    for row in profile.get("projects") or []:
        if not isinstance(row, dict):
            continue
        for item in row.get("technologies") or []:
            tech.append(str(item))
    return tech


def compute_profile_match(
    profile: dict[str, Any] | None,
    *,
    title: str,
    location: str,
    description: str,
    opportunity_type: str = "job",
    ats_platform: str = "unknown",
    posted_date: date | None = None,
    date_found: datetime | None = None,
) -> tuple[int, list[str], dict[str, Any]]:
    """Return (score 0–100, match_reasons, sponsorship metadata)."""
    text = f"{title}\n{description}".lower()
    loc = (location or "").lower()
    score = 0
    reasons: list[str] = []

    sponsorship_meta = detect_sponsorship(text)
    needs_sponsor = applicant_needs_sponsorship(profile)

    if opportunity_type == "scholarship":
        score += 35
        reasons.append("Scholarship / funded programme")
        for kw in ("scholarship", "master", "msc", "funding", "erasmus", "stipendium", "daad"):
            if kw in text:
                score += 6
                if len(reasons) < 6:
                    reasons.append(f"Funding keyword: {kw}")

    if profile:
        matched_skills: list[str] = []
        for skill in _flatten_skills(profile):
            token = skill.lower().strip()
            if len(token) < 2:
                continue
            if token in text:
                matched_skills.append(skill)
                score += 6
        if matched_skills:
            preview = ", ".join(matched_skills[:4])
            reasons.append(f"Skills: {preview}")

        for field in _education_fields(profile):
            field_l = field.lower()
            if any(term in field_l for term in _PROFILE_FIELDS) and any(
                term in text for term in field_l.split() if len(term) > 3
            ):
                score += 12
                reasons.append(f"Education: {field}")
                break
            if field_l in text:
                score += 12
                reasons.append(f"Education: {field}")
                break

        for role in _experience_roles(profile):
            role_l = role.lower()
            if role_l in text or any(word in text for word in role_l.split() if len(word) > 4):
                score += 8
                reasons.append(f"Experience: {role}")
                break

        proj_hits = [t for t in _project_technologies(profile) if t.lower() in text]
        if proj_hits:
            score += min(15, len(proj_hits) * 5)
            reasons.append(f"Projects: {', '.join(proj_hits[:3])}")

        summary = str(profile.get("summary") or "").lower()
        if summary:
            for term in _PROFILE_FIELDS:
                if term in summary and term in text:
                    score += 4
                    break
    else:
        for term in _PROFILE_FIELDS:
            if term in text:
                score += 8
        if score:
            reasons.append("Keyword overlap (no profile loaded)")

    if is_hungary_location(loc):
        score += 20
        reasons.append("Hungary location")
    elif any(x in loc for x in ("europe", "eu", "germany", "netherlands", "austria", "czech", "poland")):
        score += 8
        reasons.append("EU location")

    if ats_platform in ("greenhouse", "lever"):
        score += 12
        reasons.append(f"{ats_platform.title()} ATS")
    elif ats_platform in ("workday", "smartrecruiters"):
        score += 5

    if posted_date:
        age = (date.today() - posted_date).days
        if age <= 3:
            score += 12
            reasons.append("Posted within 3 days")
        elif age <= 7:
            score += 8
        elif age <= 14:
            score += 4

    if date_found:
        found = date_found
        if found.tzinfo is None:
            found = found.replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - found).total_seconds() / 3600
        if hours <= 48:
            score += 4

    status = sponsorship_meta.get("sponsorship_status")
    if needs_sponsor:
        if sponsorship_meta.get("sponsorship_offered") is True:
            score += 15
            reasons.append("Visa sponsorship offered")
        elif sponsorship_meta.get("sponsorship_offered") is False:
            score -= 20
            reasons.append("No visa sponsorship (you need sponsorship)")
        elif status == "unknown":
            reasons.append("Sponsorship not mentioned")

    capped = max(0, min(100, score))
    return capped, reasons[:8], sponsorship_meta


def enrich_listing_metadata(
    metadata: dict[str, Any],
    profile: dict[str, Any] | None,
    *,
    title: str,
    location: str,
    description: str,
    opportunity_type: str = "job",
    ats_platform: str = "unknown",
    posted_date: date | None = None,
) -> dict[str, Any]:
    """Add match_score, match_reasons, and sponsorship fields to job metadata."""
    score, reasons, sponsorship = compute_profile_match(
        profile,
        title=title,
        location=location,
        description=description,
        opportunity_type=opportunity_type,
        ats_platform=ats_platform,
        posted_date=posted_date,
    )
    enriched = dict(metadata)
    enriched["match_score"] = score
    enriched["match_reasons"] = reasons
    enriched.update(sponsorship)
    enriched["applicant_needs_sponsorship"] = applicant_needs_sponsorship(profile)
    return enriched
