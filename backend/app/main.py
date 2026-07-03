from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from ai.answers import generate_application_answer  # noqa: E402
from ai.client import ClaudeConfigError  # noqa: E402
from ai.tailor import SAMPLE_JOB, tailor_for_job  # noqa: E402
from ats.runner import apply_to_job, submit_after_review  # noqa: E402
from database.client import SupabaseConfigError, get_supabase_client  # noqa: E402
from database.jobs import (  # noqa: E402
    get_job,
    get_stats,
    job_to_api_dict,
    list_jobs,
    update_job_cover_letter,
    update_job_status,
)
from database.models import JobStatus  # noqa: E402
from database.profile import ProfileError, load_profile  # noqa: E402
from database.qa_memory import find_qa_answer, store_qa_answer  # noqa: E402
from notifications.telegram import send_daily_summary  # noqa: E402
from notifications.telegram_bot import start_telegram_bot_background, stop_telegram_bot  # noqa: E402
from notifications.telegram import notify_cover_letter_ready  # noqa: E402
from scraper.canary import run_all_canaries_sync  # noqa: E402
from scraper.config import ScraperConfig, review_before_submit  # noqa: E402
from scraper.linkedin_scraper import run_scraper_sync  # noqa: E402
from scraper.profession_hu import run_profession_scraper_sync  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_telegram_bot_background()
    yield
    stop_telegram_bot()


app = FastAPI(title="JantaSearcher API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StatusUpdate(BaseModel):
    status: JobStatus


class JobDescriptionInput(BaseModel):
    title: str = "Automation Engineer"
    company: str = "Example Corp"
    location: str = "Remote"
    description: str = Field(
        default="",
        description="Full job description text. Leave empty to use the built-in sample job.",
    )


class AnswerInput(BaseModel):
    question: str
    job_id: str | None = None


class QaStoreInput(BaseModel):
    question_text: str
    answer_text: str
    job_id_first_asked: str | None = None


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/config")
def get_config():
    return {
        "review_before_submit": review_before_submit(),
        "scraper_public_mode": ScraperConfig.from_env().public_mode,
    }


@app.get("/db/health")
def db_health():
    try:
        client = get_supabase_client()
        result = client.table("jobs").select("id", count="exact").limit(1).execute()
        return {"ok": True, "jobs_count": result.count}
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail=f"Database check failed: {exc}") from exc


@app.get("/profile")
def get_profile():
    try:
        profile = load_profile()
        return {
            "ok": True,
            "contact_name": profile["contact"].get("full_name"),
            "experience_count": len(profile.get("experience", [])),
            "projects_count": len(profile.get("projects", [])),
        }
    except ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/ai/health")
def ai_health():
    try:
        from ai.client import get_claude_client

        get_claude_client()
        return {"ok": True, "configured": True}
    except ClaudeConfigError as exc:
        return {"ok": False, "configured": False, "detail": str(exc)}


@app.post("/ai/test-tailor")
def test_tailor(job: JobDescriptionInput | None = None):
    try:
        profile = load_profile()
    except ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    job_payload = SAMPLE_JOB if job is None else job.model_dump()
    if job is not None and not job.description.strip():
        job_payload = SAMPLE_JOB

    try:
        result = tailor_for_job(profile, job_payload)
        return {
            "ok": True,
            "job": job_payload,
            "tailored_resume": result.tailored_resume,
            "cover_letter": result.cover_letter,
            "emphasized_skills": result.emphasized_skills,
            "notes": result.notes,
        }
    except ClaudeConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Claude tailoring failed: {exc}") from exc


@app.post("/ai/answer")
def ai_answer(body: AnswerInput):
    try:
        profile = load_profile()
    except ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    job_ctx = None
    if body.job_id:
        job = get_job(body.job_id)
        if job:
            job_ctx = {
                "title": job.title,
                "company": job.company,
                "description": job.description or "",
            }

    try:
        answer = generate_application_answer(body.question, profile, job=job_ctx)
    except ClaudeConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"ok": True, "answer": answer}


@app.get("/qa/lookup")
def qa_lookup(question: str = Query(..., min_length=3)):
    from ai.qa_match import find_semantic_qa_answer

    hit = find_semantic_qa_answer(question)
    return {"ok": True, "match": hit}


@app.post("/qa/store")
def qa_store(body: QaStoreInput):
    record = store_qa_answer(
        body.question_text,
        body.answer_text,
        job_id_first_asked=body.job_id_first_asked,
    )
    return {"ok": True, "record": record}


@app.get("/stats")
def stats():
    try:
        return get_stats()
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/telegram/daily-summary")
def trigger_daily_summary():
    stats_data = get_stats()
    send_daily_summary(stats_data)
    return {"ok": True, "stats": stats_data}


@app.get("/jobs")
def api_list_jobs(status: JobStatus | None = Query(default=None), limit: int = Query(default=100, le=200)):
    try:
        jobs = list_jobs(status=status, external_only=True, limit=limit)
        return {"ok": True, "jobs": [job_to_api_dict(job) for job in jobs]}
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {exc}") from exc


@app.get("/jobs/{job_id}")
def read_job(job_id: str):
    try:
        job = get_job(job_id)
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_api_dict(job)


@app.post("/jobs/{job_id}/cover-letter")
def create_cover_letter(job_id: str):
    try:
        job = get_job(job_id)
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        profile = load_profile()
    except ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    job_payload = {
        "title": job.title,
        "company": job.company,
        "location": job.location or "",
        "description": job.description or "",
    }

    try:
        result = tailor_for_job(profile, job_payload)
        letter = result.cover_letter
    except ClaudeConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Cover letter generation failed: {exc}") from exc

    update_job_cover_letter(job_id, letter)
    notify_cover_letter_ready(job_title=job.title, company=job.company, job_id=job_id)
    return {"ok": True, "cover_letter": letter}


@app.post("/jobs/{job_id}/apply")
def apply_job(job_id: str, force_submit: bool = Query(default=False)):
    try:
        if not get_job(job_id):
            raise HTTPException(status_code=404, detail="Job not found")
        result = apply_to_job(job_id, force_submit=force_submit)
        return {"ok": True, "result": result}
    except ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/jobs/{job_id}/approve")
async def approve_job(job_id: str):
    try:
        if not get_job(job_id):
            raise HTTPException(status_code=404, detail="Job not found")
        result = await submit_after_review(job_id)
        return {"ok": True, "result": {"outcome": result.outcome, "message": result.message}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/jobs/{job_id}/status")
def patch_job_status(job_id: str, body: StatusUpdate):
    allowed: set[JobStatus] = {
        "new",
        "queued",
        "applied",
        "needs_answer",
        "skipped",
        "failed",
    }
    if body.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {sorted(allowed)}")

    try:
        if not get_job(job_id):
            raise HTTPException(status_code=404, detail="Job not found")
        update_job_status(job_id, body.status)
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"ok": True, "status": body.status}


@app.post("/scraper/run")
def run_scraper():
    try:
        cfg = ScraperConfig.from_env()
        result = run_scraper_sync(cfg)
        return {"ok": True, "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Scraper run failed: {exc}") from exc


@app.post("/scraper/profession")
def run_profession():
    try:
        cfg = ScraperConfig.from_env()
        result = run_profession_scraper_sync(cfg)
        return {"ok": True, "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/scraper/canary")
def run_canary():
    try:
        cfg = ScraperConfig.from_env()
        results = run_all_canaries_sync(cfg)
        return {"ok": True, "results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
