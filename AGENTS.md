# Jantasearcher / ProjectEagle — Agent instructions

## Project

Automated EU job discovery and master's scholarship assistant for a **Mechatronics Engineering BSc** holder. Scrape external-apply roles, generate Claude cover letters, auto-fill ATS forms, Telegram bot.

- **Repo:** https://github.com/pmochoki/ProjectEagle-
- **Supabase project ref:** `twojjtkqifmscxvrettm`
- **Stack:** Next.js frontend (`frontend/`), FastAPI backend (`backend/`), Python packages at repo root (`ai/`, `scraper/`, `database/`, etc.)

## Cursor Cloud specific instructions

Cloud agents run from `.cursor/environment.json`. On boot, `bash .cursor/scripts/cloud-install.sh` installs:

- `backend/.venv` + `pip install -r backend/requirements.txt` + Playwright Chromium
- `frontend` → `npm ci`
- `data/profile.json` from example if missing
- `.env` from `.env.example` if missing (real values come from **Cursor Cloud Secrets**)

### Dev servers (pre-started in tmux)

- **API:** http://localhost:8000 — `PYTHONPATH=.. uvicorn app.main:app`
- **Web:** http://localhost:3000 — `npm run dev`

### Environment variables

All secrets live in **Cursor Dashboard → Cloud Agents → Secrets**, not in git. Required names match `.env.example`. Never commit `.env` or `data/profile.json`.

### Supabase MCP

Repo MCP config: `.cursor/mcp.json` scoped to `project_ref=twojjtkqifmscxvrettm`.

- **Desktop Cursor:** OAuth login when prompted (Settings → Tools & MCP).
- **Cloud Agents:** Add secret `SUPABASE_ACCESS_TOKEN` (Personal Access Token from https://supabase.com/dashboard/account/tokens) if OAuth is unavailable; use read-only PAT for safety when possible.

### Common commands

```bash
# Health check
cd backend && source .venv/bin/activate && PYTHONPATH=.. python ../scripts/check_setup.py

# Run automation cycle (EU+HU scrape, scholarships, careful apply)
PYTHONPATH=. python scripts/run_automation.py --force-all

# Run LinkedIn scraper (needs LINKEDIN_* or SCRAPER_PUBLIC_MODE=true)
curl -X POST http://localhost:8000/scraper/run

# List jobs
curl http://localhost:8000/jobs
```

### Constraints (do not violate)

- No LinkedIn Easy Apply automation
- No CAPTCHA bypass
- No fabricating profile facts in cover letters
- `REVIEW_BEFORE_SUBMIT=true` by default — do not auto-submit ATS forms without approval
- If LinkedIn shows **account restricted**: stop credential login immediately; clear `LINKEDIN_*` secrets; set `SCRAPER_PUBLIC_MODE=true` or `LINKEDIN_ENABLED=false`; rely on EURES/Indeed/Arbeitnow/RemoteOK; appeal via LinkedIn Help — do not bypass locks

### Profile data

`data/profile.json` is gitignored. Replace placeholder content with the applicant's real mechatronics BSc details before generating cover letters or applying.
