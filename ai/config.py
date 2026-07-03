from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class AIConfig:
    api_key: str
    model: str
    applicant_name: str
    applicant_background: str

    @staticmethod
    def from_env() -> "AIConfig":
        return AIConfig(
            api_key=os.getenv("CLAUDE_API_KEY", ""),
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            applicant_name=os.getenv("APPLICANT_NAME", ""),
            applicant_background=os.getenv("APPLICANT_BACKGROUND", ""),
        )

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError("Missing CLAUDE_API_KEY in .env")
        if not self.applicant_name:
            raise ValueError("Missing APPLICANT_NAME in .env")
        if not self.applicant_background:
            raise ValueError("Missing APPLICANT_BACKGROUND in .env")
