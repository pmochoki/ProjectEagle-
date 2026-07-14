"""FastAPI authentication dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from database.auth import AuthError, AuthUser, set_request_user, verify_access_token


async def require_user(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in required")
    token = authorization.split(" ", 1)[1].strip()
    try:
        user = verify_access_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    set_request_user(user)
    return user


async def _optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthUser | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        user = verify_access_token(token)
    except AuthError:
        return None
    set_request_user(user)
    return user


OptionalUser = Annotated[AuthUser | None, Depends(_optional_user)]
