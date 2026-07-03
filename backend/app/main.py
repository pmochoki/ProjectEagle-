from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException, Query

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from database.client import SupabaseConfigError, get_supabase_client  # noqa: E402
from database.jobs import list_jobs  # noqa: E402
from database.models import JobStatus  # noqa: E402
from scraper.config import ScraperConfig  # noqa: E402
from scraper.linkedin_scraper import run_scraper_sync  # noqa: E402

app = FastAPI(title="JobDragon API")


@app.get("/health")
def health():
    return {"ok": True}


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


@app.get("/jobs")
def get_jobs(status: JobStatus | None = Query(default=None), limit: int = Query(default=50, le=200)):
    try:
        jobs = list_jobs(status=status, limit=limit)
        return {"ok": True, "jobs": [job.__dict__ for job in jobs]}
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {exc}") from exc


@app.post("/scraper/run")
def run_scraper():
    try:
        cfg = ScraperConfig.from_env()
        result = run_scraper_sync(cfg)
        return {"ok": True, "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Scraper run failed: {exc}") from exc
