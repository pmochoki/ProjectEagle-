# JantaSearcher Scraper (Step 3)

Playwright-based LinkedIn job scraper that:

- Logs in with credentials from `.env`
- Searches jobs from configured criteria
- Iterates through pagination up to `SCRAPER_MAX_PAGES`
- Scrapes title/company/location/description/apply URL
- Detects Easy Apply button presence
- Saves jobs into SQLite (`database/jantasearcher.db`)
- Detects CAPTCHA/security checks and pauses
- Uses randomized delays between actions (default 3-15 seconds)

## Setup

```bash
cd scraper
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Run manually

```bash
python -m scraper.run
```

## Trigger via backend

Start backend and call:

```bash
curl -X POST http://localhost:8000/scraper/run
```

## Notes

- Prefer `SCRAPER_PUBLIC_MODE=true` (default). Logged-in LinkedIn scraping can get the
  account restricted; if that happens set `LINKEDIN_ENABLED=false`, clear credentials,
  and rely on EURES / Indeed / Arbeitnow / RemoteOK while you appeal via LinkedIn Help.
- LinkedIn frequently changes selectors; this module is structured for iterative hardening.
- If CAPTCHA is detected, the run exits with `captcha_detected=true` so notifications/pausing can be handled in later modules.
- If the account-restricted banner is detected, credential login stops permanently until
  `/linkedin_status` clears the flag after a successful logged-in probe.

