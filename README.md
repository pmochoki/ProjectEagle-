# JobDragon

Automated job discovery and application system.

## Architecture

1. **Discovery** (LinkedIn + HU job boards) — browse-only, extract external apply URLs. Never Easy Apply.
2. **Application** (company ATS sites) — register, fill forms, upload tailored docs, submit.

## Tech

- Frontend: Next.js + Tailwind
- Backend: FastAPI (Python)
- DB: Supabase (Postgres)
- Automation: Playwright (Python)
- AI: Claude API (Anthropic)
- Notifications: Telegram Bot API

## Repo layout

- `frontend/`: Next.js app (UI)
- `backend/`: FastAPI server (API + secrets)
- `scraper/`: LinkedIn scraper (Playwright)
- `database/`: Supabase client + job/Q&A helpers
- `supabase/`: SQL migrations and local CLI config
- `data/`: Profile JSON schema + example
- `applier/`: Auto-apply + ATS handlers (pending)
- `ai/`: CV tailoring + cover letter modules (pending)
- `notifications/`: Telegram bot (pending)

## Build phases

| Phase | Status |
|-------|--------|
| 1. Supabase schema | Done |
| 2. Profile loader + Claude API test | Done |
| 3. LinkedIn session module | Pending |
| 4. Greenhouse ATS filler | Pending |
| 5. Telegram bot + Q&A memory | Pending |
| 6. Lever + more ATS | Pending |
| 7. HU job board scrapers | Pending |
| 8. Review-queue mode | Pending |

## Setup

### 1. Supabase

Apply `supabase/migrations/20250703000000_initial_schema.sql` to your Supabase project (SQL Editor or `supabase db reset` locally). See `supabase/README.md`.

### 2. Environment

```bash
cp .env.example .env
cp data/profile.example.json data/profile.json
```

Fill in `.env`:

| Variable | Where to get it |
|----------|-----------------|
| `SUPABASE_URL` | Supabase → Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API → service_role (secret) |
| `SUPABASE_ANON_KEY` | Supabase → Settings → API → anon public |
| `CLAUDE_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) |

Never commit `.env` or expose `SUPABASE_SERVICE_ROLE_KEY` in the frontend.

Fill in Supabase URL/keys, LinkedIn credentials, Claude API key, and Telegram tokens as needed.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Verify DB connectivity: `GET http://localhost:8000/db/health`

Verify Claude (needs `CLAUDE_API_KEY`): `POST http://localhost:8000/ai/test-tailor`

## Profile data

Copy the example profile and edit with your real details:

```bash
cp data/profile.example.json data/profile.json
```

`data/profile.json` is gitignored. Schema: `data/profile.schema.json`.

Verify profile loads: `GET http://localhost:8000/profile`
