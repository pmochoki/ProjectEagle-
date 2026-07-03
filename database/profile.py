from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[1] / "data" / "profile.json"
EXAMPLE_PROFILE_PATH = Path(__file__).resolve().parents[1] / "data" / "profile.example.json"


class ProfileError(ValueError):
    """Raised when profile JSON is missing or invalid."""


def load_profile(path: Path | None = None) -> dict[str, Any]:
    """Load applicant profile from JSON file (Phase 2 will add validation + Claude usage)."""
    profile_path = path or DEFAULT_PROFILE_PATH
    if not profile_path.exists():
        raise ProfileError(
            f"Profile not found at {profile_path}. "
            f"Copy data/profile.example.json to data/profile.json and fill in your details."
        )

    with profile_path.open(encoding="utf-8") as f:
        data = json.load(f)

    required = ("contact", "summary", "skills", "experience", "projects", "education")
    missing = [key for key in required if key not in data]
    if missing:
        raise ProfileError(f"Profile missing required keys: {', '.join(missing)}")

    return data
