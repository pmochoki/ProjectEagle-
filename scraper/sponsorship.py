"""Detect visa / work-permit sponsorship signals in job listings."""

from __future__ import annotations

import os
import re
from typing import Any

_OFFERED_PATTERNS = (
    r"visa sponsorship",
    r"sponsor(?:ship)?(?:\s+for)?\s+(?:a\s+)?visa",
    r"work permit sponsorship",
    r"relocation support",
    r"will sponsor",
    r"sponsorship available",
    r"eligible for sponsorship",
    r"we (?:can|will) sponsor",
)

_DENIED_PATTERNS = (
    r"no sponsorship",
    r"not (?:be )?able to sponsor",
    r"unable to sponsor",
    r"without sponsorship",
    r"must (?:already )?have (?:the )?right to work",
    r"must be (?:legally )?authorized to work",
    r"work authorization required",
    r"eu(?:/eea)? citizens only",
    r"must have (?:valid )?work (?:permit|authorization)",
    r"no visa sponsorship",
)


def detect_sponsorship(text: str) -> dict[str, Any]:
    """Return sponsorship_offered (True/False/None) and sponsorship_status string."""
    haystack = (text or "").lower()
    denied = any(re.search(p, haystack) for p in _DENIED_PATTERNS)
    offered = any(re.search(p, haystack) for p in _OFFERED_PATTERNS)

    if re.search(r"\bno visa sponsorship\b", haystack) or re.search(r"\bno sponsorship\b", haystack):
        denied = True
        offered = False

    if denied and not offered:
        return {"sponsorship_offered": False, "sponsorship_status": "not_offered"}
    if offered and not denied:
        return {"sponsorship_offered": True, "sponsorship_status": "offered"}
    if offered and denied:
        return {"sponsorship_offered": None, "sponsorship_status": "unclear"}
    return {"sponsorship_offered": None, "sponsorship_status": "unknown"}


def applicant_needs_sponsorship(profile: dict[str, Any] | None) -> bool:
    if profile:
        prefs = profile.get("preferences") or {}
        if isinstance(prefs.get("needs_visa_sponsorship"), bool):
            return prefs["needs_visa_sponsorship"]
    return os.getenv("APPLICANT_NEEDS_VISA_SPONSORSHIP", "true").lower() in ("1", "true", "yes")
