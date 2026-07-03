#!/usr/bin/env python3
"""Run DOM canary checks. Schedule via cron, e.g. daily at 6:00 UTC:
0 6 * * * cd /path/to/Jantasearcher && python3 scripts/run_canary.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.canary import run_all_canaries_sync  # noqa: E402
from scraper.config import ScraperConfig  # noqa: E402


def main() -> int:
    cfg = ScraperConfig.from_env()
    results = run_all_canaries_sync(cfg)
    print(json.dumps(results, indent=2))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
