"""Supabase JWT verification for FastAPI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from supabase import Client, create_client

from database.auth_context import current_user_id


class AuthError(Exception):
    """Invalid or missing auth token."""


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None


@lru_cache(maxsize=1)
def _auth_client() -> Client:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if not url or not key:
        raise AuthError("Supabase auth is not configured on the server")
    return create_client(url, key)


def verify_access_token(access_token: str) -> AuthUser:
    token = access_token.strip()
    if not token:
        raise AuthError("Missing access token")
    try:
        response = _auth_client().auth.get_user(token)
    except Exception as exc:
        raise AuthError("Invalid or expired session") from exc
    user = getattr(response, "user", None)
    if not user or not user.id:
        raise AuthError("Invalid or expired session")
    return AuthUser(id=str(user.id), email=getattr(user, "email", None))


def set_request_user(user: AuthUser) -> None:
    current_user_id.set(user.id)
