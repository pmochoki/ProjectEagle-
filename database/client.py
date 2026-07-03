from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


class SupabaseConfigError(RuntimeError):
    """Raised when required Supabase environment variables are missing."""


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SupabaseConfigError(f"Missing required environment variable: {name}")
    return value


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Return a cached Supabase client using the service role key (backend only)."""
    url = _require_env("SUPABASE_URL")
    key = _require_env("SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)
