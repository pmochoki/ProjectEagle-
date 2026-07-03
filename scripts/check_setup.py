#!/usr/bin/env python3
"""Quick setup check for JantaSearcher. Run from project root."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OK = "✓"
FAIL = "✗"


def main() -> int:
    print("JantaSearcher setup check\n")

    # .env
    env_path = ROOT / ".env"
    if env_path.exists():
        print(f"{OK} .env exists")
    else:
        print(f"{FAIL} .env missing — run: cp .env.example .env")
        return 1

    # Profile
    profile_path = ROOT / "data" / "profile.json"
    if profile_path.exists():
        import json

        profile = json.loads(profile_path.read_text())
        name = profile.get("contact", {}).get("full_name", "")
        if name and name != "Your Name":
            print(f"{OK} profile.json — {name}")
        else:
            print(f"{FAIL} profile.json still has placeholder name — edit data/profile.json")
    else:
        print(f"{FAIL} data/profile.json missing — run: cp data/profile.example.json data/profile.json")

    # Supabase
    try:
        from database.jobs import get_stats

        stats = get_stats()
        print(f"{OK} Supabase connected — {stats['found']} jobs in DB")
    except Exception as exc:
        print(f"{FAIL} Supabase — {exc}")

    # Claude
    try:
        from ai.client import get_claude_client, get_model

        get_claude_client()
        print(f"{OK} Claude API key set — model: {get_model()}")
    except Exception as exc:
        print(f"{FAIL} Claude — {exc}")

    print("\nDashboard: http://localhost:3000")
    print("API:       http://localhost:8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
