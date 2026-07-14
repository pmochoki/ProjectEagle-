from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class AutomationConfig:
    enabled: bool
    poll_minutes: int
    scrape_eu_interval_hours: float
    scrape_scholarship_interval_hours: float
    scrape_profession_interval_hours: float
    locations_per_cycle: int
    titles_per_cycle: int
    scholarship_keywords_per_cycle: int
    apply_enabled: bool
    apply_max_per_day: int
    apply_min_interval_minutes: int
    timezone: str

    @staticmethod
    def from_env() -> "AutomationConfig":
        return AutomationConfig(
            enabled=os.getenv("AUTOMATION_ENABLED", "true").lower() == "true",
            poll_minutes=max(5, int(os.getenv("AUTOMATION_POLL_MINUTES", "30"))),
            scrape_eu_interval_hours=float(os.getenv("SCRAPE_EU_INTERVAL_HOURS", "6")),
            scrape_scholarship_interval_hours=float(
                os.getenv("SCRAPE_SCHOLARSHIP_INTERVAL_HOURS", "8")
            ),
            scrape_profession_interval_hours=float(
                os.getenv("SCRAPE_PROFESSION_INTERVAL_HOURS", "12")
            ),
            locations_per_cycle=max(1, int(os.getenv("SCRAPE_LOCATIONS_PER_CYCLE", "2"))),
            titles_per_cycle=max(1, int(os.getenv("SCRAPE_TITLES_PER_CYCLE", "1"))),
            scholarship_keywords_per_cycle=max(
                1, int(os.getenv("SCRAPE_SCHOLARSHIP_KEYWORDS_PER_CYCLE", "2"))
            ),
            apply_enabled=os.getenv("APPLY_ENABLED", "true").lower() == "true",
            apply_max_per_day=max(1, int(os.getenv("APPLY_MAX_PER_DAY", "6"))),
            apply_min_interval_minutes=max(
                15, int(os.getenv("APPLY_MIN_INTERVAL_MINUTES", "45"))
            ),
            timezone=os.getenv("DAILY_SUMMARY_TIMEZONE", "Europe/Budapest"),
        )
