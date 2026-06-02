from __future__ import annotations

import sqlite3
from pathlib import Path

from scraper.models import ScrapedJob

DB_PATH = Path(__file__).resolve().parents[1] / "database" / "jobdragon.db"


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                apply_url TEXT NOT NULL UNIQUE,
                is_easy_apply INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                scraped_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                applied_at DATETIME
            )
            """
        )
        conn.commit()


def save_jobs(jobs: list[ScrapedJob]) -> int:
    if not jobs:
        return 0

    inserted = 0
    with sqlite3.connect(DB_PATH) as conn:
        for job in jobs:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO jobs
                    (title, company, location, description, apply_url, is_easy_apply)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job.title,
                    job.company,
                    job.location,
                    job.description,
                    job.apply_url,
                    int(job.is_easy_apply),
                ),
            )
            if cur.rowcount > 0:
                inserted += 1
        conn.commit()
    return inserted

