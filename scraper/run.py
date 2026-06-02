from __future__ import annotations

import json

from scraper.config import ScraperConfig
from scraper.linkedin_scraper import run_scraper_sync


def main() -> None:
    cfg = ScraperConfig.from_env()
    result = run_scraper_sync(cfg)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

