# JantaSearcher

Automated job discovery and application assistant — scrape **external-apply** jobs, generate AI cover letters, auto-fill Greenhouse/Lever forms, and manage applications via Telegram.

**GitHub:** [github.com/pmochoki/Jantasearcher](https://github.com/pmochoki/Jantasearcher)  
**Database:** Supabase project `Jantasearcher` (`twojjtkqifmscxvrettm`)

## Pipeline

1. **Discover** — LinkedIn (logged-in or public mode) + profession.hu → Supabase with fuzzy dedup
2. **Tailor** — Claude generates cover letters + resume text from `data/profile.json` (no fabrication)
3. **Apply** — Greenhouse / Lever Playwright fillers; file uploads via `<input type="file">`
4. **Q&A** — Semantic memory bank (pg_trgm + Claude) + Telegram `/answer` for unknown questions
5. **Safety** — `REVIEW_BEFORE_SUBMIT=true` by default; CAPTCHA → pause + notify (no bypass)
6. **Canary** — DOM selector health checks with Telegram alerts (`POST /scraper/canary` or cron)

## Tech

- Frontend: Next.js + Tailwind
- Backend: FastAPI (Python)
- DB: Supabase (Postgres)
- Automation: Playwright
- AI: Claude API (Anthropic)
- Notifications: Telegram Bot API (outbound + inbound commands)

## Repo layout

| Path | Purpose |
|------|---------|
| `frontend/` | Dashboard, jobs, apply UI |
| `backend/` | FastAPI API |
| `scraper/` | LinkedIn, profession.hu, session, canary |
| `ats/` | Greenhouse + Lever fillers, apply runner |
| `ai/` | Tailoring, answers, semantic Q&A match |
| `database/` | Supabase client + jobs/Q&A |
| `notifications/` | Telegram alerts + bot polling |
| `data/` | Profile JSON, LinkedIn session (gitignored) |

## Setup

```bash
cp .env.example .env
cp data/profile.example.json data/profile.json
```

Key `.env` variables:

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Database |
| `LINKEDIN_EMAIL` / `PASSWORD` | Scraper login (optional if `SCRAPER_PUBLIC_MODE=true`) |
| `CLAUDE_API_KEY` | Cover letters + Q&A |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Alerts + `/answer` / `/approve` |
| `TELEGRAM_CHANNEL_ID` | Optional channel for alerts and commands (bot must be channel admin) |
| `REVIEW_BEFORE_SUBMIT` | Default `true` — blocks final submit until approved |

### Backend

```bash
cd backend && source .venv/bin/activate
pip install -r requirements.txt && playwright install chromium
PYTHONPATH=.. uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:3000

## Deploy on Vercel (frontend + backend)

**Production:** https://project-eagle-six.vercel.app

The repo includes `vercel.json` for Vercel **Services** (Next.js frontend + FastAPI backend in one project).

1. Import `pmochoki/ProjectEagle-` on [vercel.com/new](https://vercel.com/new)
2. Vercel detects `vercel.json` — click **Deploy**
3. Add **Environment Variables** (Project Settings → Environment Variables):

| Variable | Required |
|----------|----------|
| `SUPABASE_URL` | Yes |
| `SUPABASE_ANON_KEY` | Yes |
| `TELEGRAM_BOT_TOKEN` | Yes (for bot) |
| `TELEGRAM_CHAT_ID` | Yes (for bot) |
| `TELEGRAM_CHANNEL_ID` | Optional |
| `CLAUDE_API_KEY` | Yes (for cover letters) |
| `DAILY_SUMMARY_TIMEZONE` | Optional (`Europe/Budapest`) |
| `DAILY_SUMMARY_HOUR_LOCAL` | Optional (`22` = 10pm) |
| `NEXT_PUBLIC_API_URL` | Optional (`/api` — set on production) |

API routes are proxied: `https://project-eagle-six.vercel.app/api/stats` → FastAPI backend.

**Note:** Scraper/Playwright apply flows are heavy; Telegram bot + dashboard should work once deployed.
**Automation** runs on your **local Mac** (not Vercel): EU+Hungary job rotation, scholarship scans, and careful apply (max 6/day, 45 min apart). Keep the backend running or use `scripts/run_automation.py` via cron.

## Telegram commands

| Command | Action |
|---------|--------|
| `/list`, `/help`, `/start` | Show full command list |
| `/ping` | Quick bot connectivity check |
| `/status` | Bot + database health |
| `/summary`, `/stats` | Job stats now |
| `/jobs [N]` | List recent jobs (default 10) |
| `/job JOB_ID` | One job details |
| `/answer JOB_ID text` | Save answer to Q&A memory, unblock job |
| `/approve JOB_ID` | Submit after review pause |
| `/scan eu` | EU + Hungary LinkedIn scan (background) |
| `/scan scholarships` | Scholarship keyword scan (background) |
| `/scan linkedin` | Default LinkedIn search (background) |
| `/scan profession` | profession.hu scraper (background) |
| `/canary` | DOM selector health check (background) |

Daily summary auto-sends at `DAILY_SUMMARY_HOUR_LOCAL` (default 22 = 10pm) in
`DAILY_SUMMARY_TIMEZONE` (default `Europe/Budapest`). The backend must be running locally for polling.

## API highlights

| Method | Path | Description |
|--------|------|-------------|
| POST | `/scraper/run` | LinkedIn scraper |
| POST | `/scraper/profession` | profession.hu scraper |
| POST | `/scraper/canary` | DOM selector health check |
| POST | `/jobs/{id}/cover-letter` | Generate cover letter |
| POST | `/jobs/{id}/apply` | Auto-fill ATS form |
| POST | `/jobs/{id}/approve` | Submit after review |
| POST | `/ai/answer` | Generate ATS free-text answer |
| GET | `/qa/lookup` | Semantic Q&A memory lookup |

## Scheduled canary (cron)

```bash
0 6 * * * cd /path/to/Jantasearcher && python3 scripts/run_canary.py
```

## Constraints (enforced)

- No LinkedIn Easy Apply automation (skip only)
- No fingerprint spoofing / anti-bot evasion
- No CAPTCHA auto-solving — manual handoff
- Resume/cover letter generation must not fabricate profile facts

## Build status

| Component | Status |
|-----------|--------|
| Supabase schema + dedup | Done |
| LinkedIn scraper + session + public mode | Done |
| profession.hu scraper | Done |
| DOM canary + Telegram alerts | Done |
| Claude tailoring + answers | Done |
| Q&A memory (semantic via Claude) | Done |
| Telegram bot (escalation + replies) | Done |
| Review-before-submit (default ON) | Done |
| Greenhouse + Lever fillers | Done |
| Real profile data | **You must fill `data/profile.json`** |
