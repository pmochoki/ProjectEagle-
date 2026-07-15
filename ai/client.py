from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MODEL = "claude-sonnet-4-6"

# Retired June 15, 2026 — remap old env values so production keeps working.
_RETIRED_MODEL_MAP = {
    "claude-sonnet-4-20250514": "claude-sonnet-4-6",
    "claude-opus-4-20250514": "claude-opus-4-8",
}


class ClaudeConfigError(RuntimeError):
    """Raised when Claude API key is missing."""


def _require_api_key() -> str:
    key = os.getenv("CLAUDE_API_KEY", "").strip()
    if not key:
        raise ClaudeConfigError(
            "Missing CLAUDE_API_KEY in .env. Get one at https://console.anthropic.com/"
        )
    return key


@lru_cache(maxsize=1)
def get_claude_client() -> Anthropic:
    return Anthropic(api_key=_require_api_key())


def get_model() -> str:
    raw = os.getenv("CLAUDE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return _RETIRED_MODEL_MAP.get(raw, raw)
