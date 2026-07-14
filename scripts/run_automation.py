#!/usr/bin/env python3
"""Run one ProjectEagle automation cycle (for cron / launchd on your Mac)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from automation.scheduler import run_automation_cycle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="ProjectEagle automation cycle")
    parser.add_argument("--force-eu", action="store_true", help="Force EU+Hungary scrape")
    parser.add_argument(
        "--force-scholarships", action="store_true", help="Force scholarship scrape"
    )
    parser.add_argument("--force-apply", action="store_true", help="Force apply attempt")
    parser.add_argument("--force-all", action="store_true", help="Force all steps")
    args = parser.parse_args()

    force_eu = args.force_eu or args.force_all
    force_scholarships = args.force_scholarships or args.force_all
    force_apply = args.force_apply or args.force_all

    result = run_automation_cycle(
        force_eu=force_eu,
        force_scholarships=force_scholarships,
        force_apply=force_apply,
    )
    print(result)
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
