# JantaSearcher (JobDragon)

Automated job discovery and application assistant — scrape **external-apply** LinkedIn jobs, generate AI cover letters from your profile, and get Telegram alerts.

**GitHub:** [github.com/pmochoki/Jantasearcher](https://github.com/pmochoki/Jantasearcher)  
**Database:** Supabase project `Jantasearcher` (`twojjtkqifmscxvrettm`)

## What it does

1. **Scrape LinkedIn** — Playwright login, search jobs, save only roles with **Apply on company website** (skips Easy Apply).
2. **Supabase storage** — jobs, Q&A memory, and profile data with fuzzy dedup.
3. **AI cover letters** — Claude tailors cover letters from `data/profile.json` (never invents experience).
4. **Telegram alerts** — scrape summaries, new jobs, cover letter ready.

## Tech

- Frontend: Next.js + Tailwind
- Backend: FastAPI (Python)
- DB: **Supabase** (Postgres)
- Automation: Playwright
- AI: Claude API (Anthropic)
- Notifications: Telegram Bot API

## Repo layout

- `frontend/` — Next.js dashboard, jobs list, cover letter UI
- `backend/` — FastAPI API
- `scraper/` — LinkedIn scraper (external apply only)
- `database/` — Supabase client + job/Q&A helpers
- `ai/` — Claude tailoring module
- `notifications/` — Telegram bot helpers
- `supabase/` — SQL migrations
- `data/` — Profile JSON schema + example

## Setup

### 1. Environment

```bash
cp .env.example .env
cp data/profile.example.json data/profile.json
```

Edit `.env`:

| Variable | Where to get it |
|----------|-----------------|
| `SUPABASE_URL` | Supabase → Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API → `service_role` (secret, backend only) |
| `SUPABASE_ANON_KEY` | Supabase → Settings → API → anon public |
| `LINKEDIN_EMAIL` / `LINKEDIN_PASSWORD` | Secondary LinkedIn account recommended |
| `CLAUDE_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | [@BotFather](https://t.me/BotFather) (optional) |

Never commit `.env` or expose `SUPABASE_SERVICE_ROLE_KEY` in the frontend.

### 2. Supabase schema

Schema is already applied on the remote `Jantasearcher` project. To re-apply locally or on a new project, run `supabase/migrations/20250703000000_initial_schema.sql` in the SQL Editor.

### 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
PYTHONPATH=.. uvicorn app.main:app --reload --port 8000
```

Verify:
- `GET http://localhost:8000/db/health`
- `GET http://localhost:8000/profile`
- `POST http://localhost:8000/ai/test-tailor` (needs `CLAUDE_API_KEY`)

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

### 5. Run scraper

From the dashboard **Run scraper** button, or:

```bash
POST http://localhost:8000/scraper/run
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/db/health` | Supabase connectivity |
| GET | `/stats` | Dashboard counts |
| GET | `/jobs` | List external-apply jobs |
| GET | `/jobs/{id}` | Single job |
| POST | `/jobs/{id}/cover-letter` | Generate + save cover letter |
| PATCH | `/jobs/{id}/status` | Update job status |
| POST | `/scraper/run` | Run LinkedIn scraper |
| GET | `/profile` | Profile JSON loaded |
| POST | `/ai/test-tailor` | Test Claude tailoring |

## Build phases

| Phase | Status |
|-------|--------|
| 1. Supabase schema | Done |
| 2. Profile loader + Claude API | Done |
| 3. LinkedIn scraper → Supabase | Done |
| 4. Dashboard + jobs UI | Done |
| 5. Greenhouse ATS filler | Pending |
| 6. HU job board scrapers | Pending |

## Notes

- LinkedIn may show CAPTCHAs — scraper pauses and saves partial results.
- Use a VPN, low daily caps, and human-like delays (`SCRAPER_DELAY_*`).
- External apply URLs open the company's careers site; auto-submit is not in v1.
