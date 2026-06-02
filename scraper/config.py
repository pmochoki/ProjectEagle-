from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ScraperConfig:
    linkedin_email: str
    linkedin_password: str
    job_title: str
    location: str
    experience_level: str
    date_posted: str
    max_pages: int
    delay_min_seconds: int
    delay_max_seconds: int
    headless: bool

    @staticmethod
    def from_env() -> "ScraperConfig":
        return ScraperConfig(
            linkedin_email=os.getenv("LINKEDIN_EMAIL", ""),
            linkedin_password=os.getenv("LINKEDIN_PASSWORD", ""),
            job_title=os.getenv("JOB_SEARCH_TITLE", "Software Engineer"),
            location=os.getenv("JOB_SEARCH_LOCATION", "Remote"),
            experience_level=os.getenv("JOB_SEARCH_EXPERIENCE_LEVEL", "mid"),
            date_posted=os.getenv("JOB_SEARCH_DATE_POSTED", "past_week"),
            max_pages=int(os.getenv("SCRAPER_MAX_PAGES", "5")),
            delay_min_seconds=int(os.getenv("SCRAPER_DELAY_MIN", "3")),
            delay_max_seconds=int(os.getenv("SCRAPER_DELAY_MAX", "15")),
            headless=os.getenv("SCRAPER_HEADLESS", "true").lower() == "true",
        )

    def validate(self) -> None:
        if not self.linkedin_email or not self.linkedin_password:
            raise ValueError("Missing LINKEDIN_EMAIL or LINKEDIN_PASSWORD in .env")
        if self.delay_min_seconds < 1 or self.delay_max_seconds < self.delay_min_seconds:
            raise ValueError("Invalid scraper delay range")
        if self.max_pages < 1:
            raise ValueError("SCRAPER_MAX_PAGES must be >= 1")

