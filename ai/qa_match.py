from __future__ import annotations

import json
from typing import Any

from ai.client import get_claude_client, get_model


def _list_qa_candidates(limit: int = 15) -> list[dict[str, Any]]:
    from database.client import get_supabase_client

    client = get_supabase_client()
    result = (
        client.table("qa_memory")
        .select("id, question_text, answer_text")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def find_semantic_qa_answer(
    question: str,
    *,
    similarity_threshold: float = 0.75,
) -> dict[str, Any] | None:
    """
    Two-stage Q&A lookup:
    1. pg_trgm pre-filter (broad)
    2. Claude picks semantically matching stored answer (or returns no match)
    """
    from database.qa_memory import find_qa_answer

    trgm_hit = find_qa_answer(question, similarity_threshold=similarity_threshold)
    candidates = _list_qa_candidates()
    if trgm_hit and not any(c["id"] == trgm_hit.id for c in candidates):
        candidates.insert(
            0,
            {
                "id": trgm_hit.id,
                "question_text": trgm_hit.question_text,
                "answer_text": trgm_hit.answer_text,
            },
        )

    if not candidates:
        return None

    client = get_claude_client()
    prompt = f"""You match ATS application questions to stored answers.

New question from a job application form:
{question}

Stored Q&A pairs (JSON):
{json.dumps(candidates, indent=2)}

If one stored question is semantically the same (or close enough to reuse the answer), respond with JSON:
{{"match_id": "<uuid>", "confidence": 0.0-1.0, "reason": "brief"}}

If none match well enough to reuse safely, respond with:
{{"match_id": null, "confidence": 0, "reason": "no match"}}

Output JSON only."""

    response = client.messages.create(
        model=get_model(),
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    match_id = data.get("match_id")
    if not match_id or float(data.get("confidence", 0)) < 0.7:
        return None

    for row in candidates:
        if row["id"] == match_id:
            return {
                "id": row["id"],
                "question_text": row["question_text"],
                "answer_text": row["answer_text"],
                "confidence": data.get("confidence"),
                "method": "claude_semantic",
            }
    return None
