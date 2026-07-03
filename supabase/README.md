# Supabase (JobDragon)

Phase 1 database schema for job discovery, application tracking, Q&A memory, and profile storage.

## Apply migrations

### Option A: Supabase Dashboard (hosted project)

1. Open your project: `https://twojjtkqifmscxvrettm.supabase.co`
2. Open **SQL Editor** and run the contents of:
   `supabase/migrations/20250703000000_initial_schema.sql`
3. Copy the project URL and keys into `.env` (see root `.env.example`).

### Option B: Supabase CLI (local)

```bash
supabase start
supabase db reset   # applies all migrations in supabase/migrations/
```

## Schema overview

| Table       | Purpose |
|------------|---------|
| `jobs`     | Discovered listings with status, external apply URL, ATS platform |
| `qa_memory`| Reusable answers to ATS free-text questions (fuzzy matched) |
| `profiles` | Optional DB mirror of `data/profile.json` |

## Dedup

`find_duplicate_job(company, title)` uses `pg_trgm` similarity on normalized company + title.
Default threshold: `0.72`. Tune per source volume if needed.

## Q&A lookup

`find_qa_answer(question)` returns the best stored answer when similarity ≥ `0.75`.
