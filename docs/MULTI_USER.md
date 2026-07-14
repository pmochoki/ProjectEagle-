# Multi-user accounts

Each person signs in with **email + password** (Supabase Auth). Data is private per account:

- Jobs & scholarships discovered
- Application status & cover letters
- Profile (mechatronics BSc, skills, experience)
- Q&A memory for ATS forms

## Sign up / sign in

1. Open the app → redirected to `/login`
2. **Create account** (friend or you) — mechatronics profile template is created automatically
3. Edit profile in **Settings** → Save

## Your Mac automation

Background scrapers use `AUTOMATION_USER_ID` in `.env` (your Supabase user UUID):

1. Sign in once on the dashboard
2. Supabase Dashboard → Authentication → Users → copy your UUID  
   Or call `GET /api/auth/me` with your session token
3. Set `AUTOMATION_USER_ID=<uuid>` in `.env` and restart the backend

Existing jobs without `user_id` can be assigned once:

```sql
UPDATE public.jobs SET user_id = '<your-uuid>' WHERE user_id IS NULL;
```

## Vercel env vars (frontend)

Add to the **frontend** project on Vercel:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

Backend already uses `SUPABASE_URL` and `SUPABASE_ANON_KEY` for JWT verification.

## Sign out

Sidebar → **Sign out** (or clear session by signing out on a shared computer).
