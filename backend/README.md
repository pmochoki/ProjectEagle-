# JantaSearcher Backend

FastAPI server for JantaSearcher. Keep all secrets and third-party API calls here (Claude, LinkedIn automation control, Telegram).

**The Telegram bot only works while this server is running.** Vercel env vars do not start the bot — deploy this API to Render/Railway or keep it running on your Mac.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
PYTHONPATH=.. uvicorn app.main:app --reload --port 8000
```

On startup you should get a Telegram message: **"JantaSearcher is connected."**

## Always-on deploy (Render)

Use `render.yaml` in the repo root. After deploy:

1. Copy all backend secrets into Render env vars
2. Set Vercel `NEXT_PUBLIC_API_URL` to your Render URL (e.g. `https://jantasearcher-api.onrender.com`)

## Telegram troubleshooting

| Symptom | Fix |
|---------|-----|
| Commands get no reply | Backend is not running — start locally or deploy to Render |
| `/list` unknown | Pull latest `main` and restart backend |
| Worked before, stopped | Mac slept / terminal closed — use Render for 24/7 |
| Still silent | `GET /telegram/health` — check `webhook_blocks_polling` |

## Endpoints

- `GET /health`
- `GET /telegram/health` — bot token, chat IDs, webhook status
- `POST /telegram/daily-summary` — trigger summary now

