from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ApplyOutcome = Literal[
    "applied",
    "needs_answer",
    "needs_account",
    "needs_verification",
    "review_pending",
    "failed",
    "captcha",
]


@dataclass
class ApplyResult:
    outcome: ApplyOutcome
    message: str
    pending_question: str | None = None
