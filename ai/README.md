# JobDragon AI layer

Claude API integration for truthful resume tailoring and cover letter generation.

## Setup

Add to `.env`:

```
CLAUDE_API_KEY=sk-ant-...
```

Optional: `CLAUDE_MODEL` (default `claude-sonnet-4-20250514`)

## API

With backend running (`uvicorn app.main:app --reload --port 8000`):

```bash
# Check Claude key is configured
curl http://localhost:8000/ai/health

# Test tailoring with built-in sample job
curl -X POST http://localhost:8000/ai/test-tailor

# Test with custom job description
curl -X POST http://localhost:8000/ai/test-tailor \
  -H "Content-Type: application/json" \
  -d '{"title":"PLC Engineer","company":"Factory Ltd","location":"Debrecen","description":"Need Siemens TIA Portal experience..."}'
```

## Rules enforced in prompts

- Only use facts from `data/profile.json`
- Reorder/re-emphasize — never fabricate experience
- Gaps noted in `notes` field
