from __future__ import annotations

import json
from typing import Any

from ai.client import get_claude_client, get_model
from ai.qa_match import find_semantic_qa_answer


SYSTEM = """You answer ATS job-application free-text questions truthfully.

Rules:
- Use ONLY facts from the applicant profile and any provided Q&A memory.
- Never invent employers, dates, skills, or credentials.
- Keep answers concise (2-6 sentences unless the question asks for more).
- Output plain text only, no markdown."""


def generate_application_answer(
    question: str,
    profile: dict[str, Any],
    *,
    job: dict[str, Any] | None = None,
) -> str:
    """Generate or reuse an answer for an ATS free-text question."""
    cached = find_semantic_qa_answer(question)
    if cached:
        return cached["answer_text"]

    job_block = ""
    if job:
        job_block = f"\nJob context:\n{json.dumps(job, indent=2)}\n"

    memory = profile.get("qa_memory") or []
    memory_block = ""
    if memory:
        memory_block = f"\nProfile Q&A seed memory:\n{json.dumps(memory, indent=2)}\n"

    user = f"""Applicant profile:
{json.dumps(profile, indent=2)}
{job_block}{memory_block}
ATS question to answer:
{question}

Write a truthful, specific answer."""

    client = get_claude_client()
    response = client.messages.create(
        model=get_model(),
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    parts = [b.text for b in response.content if b.type == "text"]
    if not parts:
        raise RuntimeError("Claude returned no answer text")
    return parts[0].strip()
