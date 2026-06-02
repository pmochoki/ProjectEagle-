from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from scraper.config import ScraperConfig  # noqa: E402
from scraper.linkedin_scraper import run_scraper_sync  # noqa: E402

app = FastAPI(title="JobDragon API")


@app.get("/health")
def health():
    return {"ok": True}


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

