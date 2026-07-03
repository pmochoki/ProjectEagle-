from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scraper.config import ScraperConfig  # noqa: E402
from scraper.linkedin_scraper import run_scraper_sync  # noqa: E402


def main() -> None:
    cfg = ScraperConfig.from_env()
    result = run_scraper_sync(cfg)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
