from __future__ import annotations

import json
from pathlib import Path

SESSION_PATH = Path(__file__).resolve().parents[1] / "data" / "linkedin_session.json"


def session_exists() -> bool:
    return SESSION_PATH.exists() and SESSION_PATH.stat().st_size > 0


async def save_session(context) -> None:
    """Persist Playwright storage state (cookies + localStorage)."""
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = await context.storage_state()
    SESSION_PATH.write_text(json.dumps(state), encoding="utf-8")


async def load_session_context(browser, *, headless: bool):
    """Return a browser context, reusing saved session when available."""
    if session_exists():
        return await browser.new_context(storage_state=str(SESSION_PATH))
    return await browser.new_context()
