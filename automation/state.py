from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parents[1] / "data" / ".automation_state.json"


@dataclass
class AutomationState:
    eu_location_index: int = 0
    eu_title_index: int = 0
    scholarship_keyword_index: int = 0
    scholarship_location_index: int = 0
    last_eu_scrape_at: str | None = None
    last_scholarship_scrape_at: str | None = None
    last_profession_scrape_at: str | None = None
    last_apply_at: str | None = None
    applications_today_date: str | None = None
    applications_today_count: int = 0
    last_eu_message: str = ""
    last_scholarship_message: str = ""
    last_apply_message: str = ""
    last_error: str = ""
    cycles_completed: int = 0

    @staticmethod
    def load() -> "AutomationState":
        if not STATE_FILE.exists():
            return AutomationState()
        try:
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return AutomationState(**{k: v for k, v in raw.items() if k in AutomationState.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError, ValueError):
            return AutomationState()

    def save(self) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def bump_apply_count(self, *, today: str) -> None:
        if self.applications_today_date != today:
            self.applications_today_date = today
            self.applications_today_count = 0
        self.applications_today_count += 1
        self.last_apply_at = datetime.now(timezone.utc).isoformat()

    def apply_count_for_today(self, today: str) -> int:
        if self.applications_today_date != today:
            return 0
        return self.applications_today_count
