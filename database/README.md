# JobDragon database layer

Python helpers for the Supabase Postgres schema (`jobs`, `qa_memory`, `profiles`).

## Setup

```bash
pip install -r database/requirements.txt
```

Set in `.env` (see root `.env.example`):

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (backend/scraper only — never expose to frontend)

Apply SQL from `supabase/migrations/20250703000000_initial_schema.sql` to your Supabase project.

## Usage

```python
from database import JobInsert, insert_job_if_new, find_qa_answer, store_qa_answer

job, outcome = insert_job_if_new(
    JobInsert(
        source="linkedin",
        title="Controls Engineer",
        company="Acme Robotics",
        external_url="https://boards.greenhouse.io/acme/jobs/123",
        location="Budapest",
    )
)
# outcome: "inserted" | "duplicate" | "skipped_easy_apply"

match = find_qa_answer("Why do you want to work here?")
if match:
    print(match.answer_text)
```

## Profile JSON

Copy `data/profile.example.json` → `data/profile.json` and edit with your real data.
Schema: `data/profile.schema.json`.

```python
from database.profile import load_profile

profile = load_profile()
```
