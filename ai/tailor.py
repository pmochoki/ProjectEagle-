from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from ai.client import get_claude_client, get_model


@dataclass
class TailoredApplicationContent:
    tailored_resume: str
    cover_letter: str
    emphasized_skills: list[str]
    notes: str


SYSTEM_PROMPT = """You are a truthful job-application assistant for JobDragon.

Rules (strict):
- Use ONLY facts from the applicant profile. Never invent employers, dates, skills, degrees, or projects.
- Tailoring means reordering and re-emphasizing existing bullets/skills to match the job description language.
- If the job asks for something not in the profile, do not claim it — omit or note the gap in "notes".
- Output valid JSON only, no markdown fences."""


def _build_user_prompt(profile: dict[str, Any], job: dict[str, Any]) -> str:
    return f"""Applicant profile (source of truth):
{json.dumps(profile, indent=2)}

Job listing:
{json.dumps(job, indent=2)}

Generate application content as JSON with this exact shape:
{{
  "tailored_resume": "Markdown resume using ONLY profile facts, reordered/emphasized for this job",
  "cover_letter": "Short cover letter referencing specific job requirements and real profile experience",
  "emphasized_skills": ["skill from profile most relevant to this job"],
  "notes": "Any gaps or honest caveats; empty string if none"
}}"""


def tailor_for_job(
    profile: dict[str, Any],
    job_description: dict[str, Any],
) -> TailoredApplicationContent:
    """Generate tailored resume + cover letter for a job using Claude."""
    client = get_claude_client()
    response = client.messages.create(
        model=get_model(),
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(profile, job_description)}],
    )

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise RuntimeError("Claude returned no text content")

    raw = text_blocks[0].strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    data = json.loads(raw)
    return TailoredApplicationContent(
        tailored_resume=data["tailored_resume"],
        cover_letter=data["cover_letter"],
        emphasized_skills=list(data.get("emphasized_skills", [])),
        notes=data.get("notes", ""),
    )


SAMPLE_JOB = {
    "title": "Automation Engineer",
    "company": "RoboTech Kft.",
    "location": "Budapest, Hungary",
    "description": """
We are looking for an Automation Engineer to build internal tooling and integrate
Playwright-based workflows with our hiring pipeline. You will work with Python, FastAPI,
and cloud databases (Postgres/Supabase). Experience with PLC/control systems is a plus.
Strong communication in English required.
""".strip(),
}
