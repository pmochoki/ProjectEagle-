"""Request-scoped authenticated user id (set by FastAPI auth dependency)."""

from __future__ import annotations

import os
from contextvars import ContextVar

current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)


def resolve_automation_user_id() -> str | None:
    """User id for local scrapers/automation (service role writes)."""
    raw = os.getenv("AUTOMATION_USER_ID", "").strip()
    return raw or None


def active_user_id() -> str | None:
    """Current API user or automation user for background jobs."""
    return current_user_id.get() or resolve_automation_user_id()
