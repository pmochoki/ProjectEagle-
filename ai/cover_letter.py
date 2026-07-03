from __future__ import annotations

import anthropic

from ai.config import AIConfig


def generate_cover_letter(
    *,
    job_title: str,
    company: str,
    location: str,
    description: str,
    cfg: AIConfig | None = None,
) -> str:
    cfg = cfg or AIConfig.from_env()
    cfg.validate()

    client = anthropic.Anthropic(api_key=cfg.api_key)
    prompt = f"""Write a professional, concise cover letter for this job application.

Applicant name: {cfg.applicant_name}
Applicant background:
{cfg.applicant_background}

Job title: {job_title}
Company: {company}
Location: {location}

Job description:
{description[:6000]}

Requirements:
- Keep it under 350 words
- Sound human and specific to this role (reference 1-2 details from the description)
- Include a clear opening, 2 short body paragraphs, and a closing
- Do not invent credentials not implied by the applicant background
- Return only the cover letter text, no subject line or metadata
"""

    message = client.messages.create(
        model=cfg.model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()
