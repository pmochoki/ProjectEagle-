from contextlib import asynccontextmanager
from pathlib import Path
import os
import sys

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from ai.answers import generate_application_answer  # noqa: E402
from ai.client import ClaudeConfigError, get_model  # noqa: E402
from ai.listing_analysis import analyze_listing  # noqa: E402
from ai.tailor import SAMPLE_JOB, tailor_for_job  # noqa: E402
from ats.runner import apply_to_job, submit_after_review  # noqa: E402
from database.client import SupabaseConfigError, get_supabase_client  # noqa: E402
from database.jobs import (  # noqa: E402
    get_job,
    get_stats,
    job_to_api_dict,
    list_jobs,
    rescore_jobs_for_user,
    update_job_cover_letter,
    update_job_status,
    update_job_analysis,
    update_job_summary,
    record_application_result,
)
from database.models import JobStatus  # noqa: E402
from database.qa_memory import find_qa_answer, store_qa_answer  # noqa: E402
from notifications.telegram import notify_cover_letter_ready, send_daily_summary  # noqa: E402
from notifications.telegram_bot import (  # noqa: E402
    start_telegram_bot_background,
    stop_telegram_bot,
    telegram_bot_status,
)
from automation.scheduler import (  # noqa: E402
    automation_status,
    run_automation_cycle,
    start_automation_background,
    stop_automation,
)
from automation.config import AutomationConfig  # noqa: E402
from scraper.canary import run_all_canaries_sync  # noqa: E402
from scraper.config import ScraperConfig, review_before_submit  # noqa: E402
from scraper.eu_jobs import run_eu_jobs_scraper_sync  # noqa: E402
from scraper.linkedin_scraper import run_scraper_sync  # noqa: E402
from scraper.profession_hu import run_profession_scraper_sync  # noqa: E402
from scraper.scholarships import run_scholarship_scraper_sync  # noqa: E402
from scraper.eures import run_eures_scraper_sync  # noqa: E402
from scraper.arbeitnow import run_arbeitnow_scraper_sync  # noqa: E402
from scraper.remoteok import run_remoteok_scraper_sync  # noqa: E402
from scraper.indeed_eu import run_indeed_scraper_sync  # noqa: E402
from scraper.adzuna import run_adzuna_scraper_sync  # noqa: E402
from scraper.scholarship_feeds import run_scholarship_feeds_sync  # noqa: E402
from scraper.sources.registry import ALL_SOURCES  # noqa: E402
from automation.urgency import urgency_status  # noqa: E402
from backend.app.deps import require_user  # noqa: E402
from backend.app.services_health import get_services_health, probe_claude_live  # noqa: E402
from database.auth import AuthUser  # noqa: E402
from database.profile import (  # noqa: E402
    ProfileError,
    get_profile_row,
    load_profile,
    save_profile_row,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Long-polling Telegram bot + automation need an always-on host (local/Render), not Vercel serverless.
    if not os.getenv("VERCEL"):
        start_telegram_bot_background()
        start_automation_background()
    yield
    if not os.getenv("VERCEL"):
        stop_telegram_bot()
        stop_automation()


app = FastAPI(title="ProjectEagle API", lifespan=lifespan)

@app.middleware("http")
async def strip_api_prefix(request, call_next):
    """Vercel rewrites /api/* to the backend service with the /api prefix intact."""
    path = request.scope.get("path", "")
    if path.startswith("/api"):
        request.scope["path"] = path[4:] or "/"
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://project-eagle-six.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
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


class ProfileUpdate(BaseModel):
    data: dict


@app.get("/auth/me")
def auth_me(user: AuthUser = Depends(require_user)):
    return {"ok": True, "user": {"id": user.id, "email": user.email}}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/services/health")
def services_health():
    """Unified public health for dashboard service banner."""
    return get_services_health()


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
def get_profile(user: AuthUser = Depends(require_user)):
    try:
        data = get_profile_row(user.id)
        if not data:
            data = load_profile(user_id=user.id)
        return {
            "ok": True,
            "contact_name": data["contact"].get("full_name"),
            "experience_count": len(data.get("experience", [])),
            "projects_count": len(data.get("projects", [])),
        }
    except ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/profile/full")
def get_profile_full(user: AuthUser = Depends(require_user)):
    data = get_profile_row(user.id)
    if not data:
        try:
            data = load_profile(user_id=user.id)
        except ProfileError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "profile": data}


@app.put("/profile")
def update_profile(body: ProfileUpdate, user: AuthUser = Depends(require_user)):
    try:
        saved = save_profile_row(user.id, body.data)
    except ProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    rescored = rescore_jobs_for_user(user_id=user.id)
    return {"ok": True, "profile": saved, "jobs_rescored": rescored}


@app.post("/jobs/rescore")
def rescore_jobs(user: AuthUser = Depends(require_user)):
    """Recompute profile match scores for all jobs belonging to the signed-in user."""
    count = rescore_jobs_for_user(user_id=user.id)
    return {"ok": True, "jobs_rescored": count}


@app.get("/ai/health")
def ai_health():
    try:
        from ai.client import get_claude_client

        get_claude_client()
        return {"ok": True, "configured": True, "model": get_model()}
    except ClaudeConfigError as exc:
        return {"ok": False, "configured": False, "detail": str(exc)}


@app.post("/ai/ping")
def ai_ping_claude(user: AuthUser = Depends(require_user)):
    """Live Claude API test — minimal token usage."""
    try:
        return {"ok": True, **probe_claude_live()}
    except ClaudeConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Claude ping failed: {exc}") from exc


@app.post("/ai/test-cover-letter")
def test_cover_letter(user: AuthUser = Depends(require_user)):
    """End-to-end cover letter test using profile + sample job."""
    try:
        profile = load_profile(user_id=user.id)
    except ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        result = tailor_for_job(profile, SAMPLE_JOB)
        return {
            "ok": True,
            "cover_letter_preview": result.cover_letter[:500],
            "cover_letter_length": len(result.cover_letter),
            "model": get_model(),
        }
    except ClaudeConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cover letter test failed: {exc}") from exc


@app.post("/ai/test-tailor")
def test_tailor(
    job: JobDescriptionInput | None = None,
    user: AuthUser = Depends(require_user),
):
    try:
        profile = load_profile(user_id=user.id)
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
def ai_answer(body: AnswerInput, user: AuthUser = Depends(require_user)):
    try:
        profile = load_profile(user_id=user.id)
    except ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    job_ctx = None
    if body.job_id:
        job = get_job(body.job_id, user_id=user.id)
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
def qa_lookup(question: str = Query(..., min_length=3), user: AuthUser = Depends(require_user)):
    from ai.qa_match import find_semantic_qa_answer

    hit = find_semantic_qa_answer(question)
    return {"ok": True, "match": hit}


@app.post("/qa/store")
def qa_store(body: QaStoreInput, user: AuthUser = Depends(require_user)):
    record = store_qa_answer(
        body.question_text,
        body.answer_text,
        job_id_first_asked=body.job_id_first_asked,
    )
    return {"ok": True, "record": record}


@app.get("/stats")
def stats(user: AuthUser = Depends(require_user)):
    try:
        return get_stats(user_id=user.id)
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/telegram/health")
def telegram_health():
    return telegram_bot_status()


@app.post("/telegram/daily-summary")
def trigger_daily_summary():
    stats_data = get_stats()
    send_daily_summary(stats_data)
    return {"ok": True, "stats": stats_data}


@app.get("/jobs")
def api_list_jobs(
    status: JobStatus | None = Query(default=None),
    limit: int = Query(default=100, le=200),
    user: AuthUser = Depends(require_user),
):
    try:
        jobs = list_jobs(status=status, external_only=True, limit=limit, user_id=user.id)
        return {"ok": True, "jobs": [job_to_api_dict(job) for job in jobs]}
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {exc}") from exc


@app.get("/jobs/{job_id}")
def read_job(job_id: str, user: AuthUser = Depends(require_user)):
    try:
        job = get_job(job_id, user_id=user.id)
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_api_dict(job)


@app.post("/jobs/{job_id}/summary")
def create_job_summary(job_id: str, user: AuthUser = Depends(require_user)):
    """Legacy alias — returns full analysis."""
    return create_job_analysis(job_id, user)


@app.post("/jobs/{job_id}/analyze")
def create_job_analysis(job_id: str, user: AuthUser = Depends(require_user)):
    try:
        job = get_job(job_id, user_id=user.id)
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    meta = job.metadata or {}
    cached_summary = meta.get("summary")
    cached_fit = meta.get("fit_probability")
    cached_desc = meta.get("description_en")
    if cached_summary and cached_fit is not None and cached_desc:
        return {
            "ok": True,
            "cached": True,
            "summary": cached_summary,
            "description_en": cached_desc,
            "fit_probability": cached_fit,
            "fit_rationale": meta.get("fit_rationale", ""),
        }

    if not (job.description or "").strip():
        raise HTTPException(status_code=400, detail="Listing has no description to analyze")

    try:
        profile = load_profile(user_id=user.id)
        analysis = analyze_listing(
            profile=profile,
            title=job.title,
            company=job.company,
            location=job.location or "",
            description=job.description or "",
            opportunity_type=meta.get("opportunity_type", "job"),
        )
        update_job_analysis(
            job_id,
            summary=analysis.summary,
            description_en=analysis.description_en,
            fit_probability=analysis.fit_probability,
            fit_rationale=analysis.fit_rationale,
        )
    except ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ClaudeConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Listing analysis failed: {exc}") from exc

    return {
        "ok": True,
        "cached": False,
        "summary": analysis.summary,
        "description_en": analysis.description_en,
        "fit_probability": analysis.fit_probability,
        "fit_rationale": analysis.fit_rationale,
    }


@app.post("/jobs/{job_id}/cover-letter")
def create_cover_letter(job_id: str, user: AuthUser = Depends(require_user)):
    try:
        job = get_job(job_id, user_id=user.id)
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        profile = load_profile(user_id=user.id)
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
def apply_job(
    job_id: str,
    force_submit: bool = Query(default=False),
    user: AuthUser = Depends(require_user),
):
    try:
        if not get_job(job_id, user_id=user.id):
            raise HTTPException(status_code=404, detail="Job not found")
        result = apply_to_job(job_id, force_submit=force_submit)
        return {"ok": True, "result": result}
    except ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/jobs/{job_id}/approve")
async def approve_job(job_id: str, user: AuthUser = Depends(require_user)):
    try:
        if not get_job(job_id, user_id=user.id):
            raise HTTPException(status_code=404, detail="Job not found")
        result = await submit_after_review(job_id)
        record_application_result(job_id, outcome=result.outcome, message=result.message)
        return {"ok": True, "result": {"outcome": result.outcome, "message": result.message}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/jobs/{job_id}/status")
def patch_job_status(job_id: str, body: StatusUpdate, user: AuthUser = Depends(require_user)):
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
        if not get_job(job_id, user_id=user.id):
            raise HTTPException(status_code=404, detail="Job not found")
        update_job_status(job_id, body.status)
        if body.status == "applied":
            record_application_result(job_id, outcome="applied", message="Marked applied manually")
        elif body.status == "failed":
            record_application_result(
                job_id, outcome="failed", message="Marked failed manually"
            )
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"ok": True, "status": body.status}


@app.post("/scraper/run")
def run_scraper(user: AuthUser = Depends(require_user)):
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
def run_profession(user: AuthUser = Depends(require_user)):
    try:
        cfg = ScraperConfig.from_env()
        result = run_profession_scraper_sync(cfg)
        return {"ok": True, "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/scraper/eu-jobs")
def run_eu_jobs(user: AuthUser = Depends(require_user)):
    try:
        cfg = ScraperConfig.from_env()
        result = run_eu_jobs_scraper_sync(cfg)
        return {"ok": True, "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"EU scraper failed: {exc}") from exc


@app.post("/scraper/scholarships")
def run_scholarships(user: AuthUser = Depends(require_user)):
    try:
        cfg = ScraperConfig.from_env()
        result = run_scholarship_scraper_sync(cfg)
        return {"ok": True, "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Scholarship scraper failed: {exc}") from exc


@app.get("/linkedin/status")
def linkedin_status():
    """Probe saved LinkedIn session — public health for dashboard."""
    from scraper.linkedin_auth import probe_linkedin_session_sync

    cfg = ScraperConfig.from_env()
    return probe_linkedin_session_sync(cfg)


@app.post("/scraper/canary")
def run_canary():
    try:
        cfg = ScraperConfig.from_env()
        results = run_all_canaries_sync(cfg, notify_ok=False)
        return {"ok": True, "results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/urgency/status")
def get_urgency_status(user: AuthUser = Depends(require_user)):
    u = urgency_status()
    cfg = AutomationConfig.from_env()
    return {
        "ok": True,
        "urgency_active": u.active,
        "permit_deadline": u.permit_deadline,
        "days_remaining": u.days_remaining,
        "weeks_remaining": u.weeks_remaining,
        "message": u.message,
        "recommended_action": u.recommended_action,
        "schedule": {
            "check_cycle_minutes": cfg.poll_minutes,
            "linkedin_europe_hours": cfg.scrape_eu_interval_hours,
            "scholarships_hours": cfg.scrape_scholarship_interval_hours,
            "extra_sources_hours": cfg.scrape_extra_interval_hours,
            "apply_max_per_day": cfg.apply_max_per_day,
            "apply_min_interval_minutes": cfg.apply_min_interval_minutes,
        },
        "sources": [{"id": s.id, "name": s.name, "kind": s.kind} for s in ALL_SOURCES],
    }


@app.post("/scraper/eures")
def run_eures(user: AuthUser = Depends(require_user)):
    try:
        cfg = ScraperConfig.from_env()
        return {"ok": True, "result": run_eures_scraper_sync(cfg)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/scraper/arbeitnow")
def run_arbeitnow(user: AuthUser = Depends(require_user)):
    try:
        return {"ok": True, "result": run_arbeitnow_scraper_sync(ScraperConfig.from_env())}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/scraper/remoteok")
def run_remoteok(user: AuthUser = Depends(require_user)):
    try:
        return {"ok": True, "result": run_remoteok_scraper_sync(ScraperConfig.from_env())}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/scraper/indeed")
def run_indeed(user: AuthUser = Depends(require_user)):
    try:
        return {"ok": True, "result": run_indeed_scraper_sync(ScraperConfig.from_env())}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/scraper/adzuna")
def run_adzuna(user: AuthUser = Depends(require_user)):
    try:
        return {"ok": True, "result": run_adzuna_scraper_sync(ScraperConfig.from_env())}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/scraper/scholarship-feeds")
def run_scholarship_feeds(user: AuthUser = Depends(require_user)):
    try:
        return {"ok": True, "result": run_scholarship_feeds_sync(ScraperConfig.from_env())}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/automation/status")
def get_automation_status(user: AuthUser = Depends(require_user)):
    status = automation_status()
    state = status.pop("state")
    return {
        "ok": True,
        **status,
        "state": {
            "cycles_completed": state.cycles_completed,
            "last_eu_scrape_at": state.last_eu_scrape_at,
            "last_scholarship_scrape_at": state.last_scholarship_scrape_at,
            "last_profession_scrape_at": state.last_profession_scrape_at,
            "last_apply_at": state.last_apply_at,
            "applications_today_count": state.applications_today_count,
            "last_eu_message": state.last_eu_message,
            "last_scholarship_message": state.last_scholarship_message,
            "last_apply_message": state.last_apply_message,
            "last_error": state.last_error,
        },
    }


@app.post("/automation/run")
def trigger_automation(
    force_eu: bool = Query(default=False),
    force_scholarships: bool = Query(default=False),
    force_apply: bool = Query(default=False),
    user: AuthUser = Depends(require_user),
):
    """Run one automation cycle (respects intervals unless force_* is true)."""
    try:
        result = run_automation_cycle(
            force_eu=force_eu,
            force_scholarships=force_scholarships,
            force_apply=force_apply,
        )
        return {"ok": result.get("ok", True), **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
