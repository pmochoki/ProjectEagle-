from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from database.auth_context import active_user_id
from database.client import get_supabase_client

DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[1] / "data" / "profile.json"
EXAMPLE_PROFILE_PATH = Path(__file__).resolve().parents[1] / "data" / "profile.example.json"


class ProfileError(ValueError):
    """Raised when profile JSON is missing or invalid."""


def _validate_profile(data: dict[str, Any]) -> None:
    required = ("contact", "summary", "skills", "experience", "projects", "education")
    missing = [key for key in required if key not in data]
    if missing:
        raise ProfileError(f"Profile missing required keys: {', '.join(missing)}")


def load_profile_from_file(path: Path | None = None) -> dict[str, Any]:
    profile_path = path or DEFAULT_PROFILE_PATH
    if not profile_path.exists():
        raise ProfileError(
            f"Profile not found at {profile_path}. "
            f"Copy data/profile.example.json to data/profile.json and fill in your details, "
            f"or sign in and edit your profile in Settings."
        )
    with profile_path.open(encoding="utf-8") as f:
        data = json.load(f)
    _validate_profile(data)
    return data


def get_profile_row(user_id: str) -> dict[str, Any] | None:
    client = get_supabase_client()
    result = (
        client.table("profiles")
        .select("data")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return result.data[0].get("data")


def save_profile_row(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    _validate_profile(data)
    client = get_supabase_client()
    existing = (
        client.table("profiles")
        .select("id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        result = (
            client.table("profiles")
            .update({"data": data})
            .eq("user_id", user_id)
            .select("data")
            .single()
            .execute()
        )
    else:
        result = (
            client.table("profiles")
            .insert({"user_id": user_id, "slug": user_id, "data": data})
            .select("data")
            .single()
            .execute()
        )
    if not result.data:
        raise ProfileError("Failed to save profile")
    return result.data["data"]


def load_profile(*, user_id: str | None = None, path: Path | None = None) -> dict[str, Any]:
    """Load profile for the active user from DB, else local JSON file (automation)."""
    uid = user_id or active_user_id()
    if uid:
        row = get_profile_row(uid)
        if row:
            _validate_profile(row)
            return row
    return load_profile_from_file(path)
