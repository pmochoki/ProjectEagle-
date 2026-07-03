from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class QAMemoryRecord:
    id: str
    question_text: str
    answer_text: str
    similarity_score: float | None = None
    job_id_first_asked: str | None = None


def find_qa_answer(
    question: str,
    *,
    similarity_threshold: float = 0.75,
) -> QAMemoryRecord | None:
    """Return the best matching stored answer for an ATS question, if any."""
    from database.client import get_supabase_client

    client = get_supabase_client()
    result = client.rpc(
        "find_qa_answer",
        {
            "p_question": question,
            "p_similarity_threshold": similarity_threshold,
        },
    ).execute()

    rows = result.data or []
    if not rows:
        return None

    row: dict[str, Any] = rows[0] if isinstance(rows, list) else rows
    return QAMemoryRecord(
        id=row["id"],
        question_text=row["question_text"],
        answer_text=row["answer_text"],
        similarity_score=row.get("similarity_score"),
    )


def store_qa_answer(
    question_text: str,
    answer_text: str,
    *,
    job_id_first_asked: str | None = None,
) -> QAMemoryRecord:
    """Persist a new Q&A pair for future fuzzy reuse."""
    from database.client import get_supabase_client

    payload: dict[str, Any] = {
        "question_text": question_text.strip(),
        "answer_text": answer_text.strip(),
    }
    if job_id_first_asked:
        payload["job_id_first_asked"] = job_id_first_asked

    client = get_supabase_client()
    result = client.table("qa_memory").insert(payload).select("*").single().execute()
    if not result.data:
        raise RuntimeError("Failed to store Q&A answer")

    row = result.data
    return QAMemoryRecord(
        id=row["id"],
        question_text=row["question_text"],
        answer_text=row["answer_text"],
        job_id_first_asked=row.get("job_id_first_asked"),
    )
