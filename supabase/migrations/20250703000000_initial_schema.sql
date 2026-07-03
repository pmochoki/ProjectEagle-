-- JobDragon Phase 1: core schema (jobs, Q&A memory, profile storage, dedup helpers)

-- Extensions for fuzzy text matching and UUID generation
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------

CREATE TYPE job_source AS ENUM (
  'linkedin',
  'profession_hu',
  'jobline_hu',
  'other'
);

CREATE TYPE job_status AS ENUM (
  'new',
  'queued',
  'applied',
  'needs_answer',
  'skipped',
  'failed'
);

CREATE TYPE ats_platform AS ENUM (
  'greenhouse',
  'lever',
  'workday',
  'smartrecruiters',
  'custom',
  'unknown'
);

-- ---------------------------------------------------------------------------
-- Normalization helpers (used by dedup logic)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.normalize_job_text(input TEXT)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
STRICT
AS $$
  SELECT lower(
    trim(
      regexp_replace(
        regexp_replace(coalesce(input, ''), '[^\w\s]', ' ', 'g'),
        '\s+',
        ' ',
        'g'
      )
    )
  );
$$;

COMMENT ON FUNCTION public.normalize_job_text IS
  'Lowercase, strip punctuation, collapse whitespace for dedup matching.';

-- ---------------------------------------------------------------------------
-- jobs
-- ---------------------------------------------------------------------------

CREATE TABLE public.jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source job_source NOT NULL,
  source_job_id TEXT,
  title TEXT NOT NULL,
  company TEXT NOT NULL,
  location TEXT,
  description TEXT,
  external_url TEXT NOT NULL,
  ats_platform ats_platform NOT NULL DEFAULT 'unknown',
  status job_status NOT NULL DEFAULT 'new',
  posted_date DATE,
  date_found TIMESTAMPTZ NOT NULL DEFAULT now(),
  date_applied TIMESTAMPTZ,
  is_easy_apply BOOLEAN NOT NULL DEFAULT false,
  normalized_title TEXT GENERATED ALWAYS AS (public.normalize_job_text(title)) STORED,
  normalized_company TEXT GENERATED ALWAYS AS (public.normalize_job_text(company)) STORED,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT jobs_external_url_not_empty CHECK (length(trim(external_url)) > 0)
);

CREATE INDEX jobs_status_idx ON public.jobs (status);
CREATE INDEX jobs_source_idx ON public.jobs (source);
CREATE INDEX jobs_date_found_idx ON public.jobs (date_found DESC);
CREATE INDEX jobs_normalized_pair_idx ON public.jobs (normalized_company, normalized_title);
CREATE INDEX jobs_normalized_company_trgm_idx
  ON public.jobs USING gin (normalized_company gin_trgm_ops);
CREATE INDEX jobs_normalized_title_trgm_idx
  ON public.jobs USING gin (normalized_title gin_trgm_ops);
CREATE INDEX jobs_external_url_idx ON public.jobs (external_url);

COMMENT ON TABLE public.jobs IS
  'Discovered job listings from LinkedIn and Hungarian job boards.';

-- ---------------------------------------------------------------------------
-- qa_memory (Q&A memory bank for ATS free-text questions)
-- ---------------------------------------------------------------------------

CREATE TABLE public.qa_memory (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  question_text TEXT NOT NULL,
  question_normalized TEXT GENERATED ALWAYS AS (public.normalize_job_text(question_text)) STORED,
  answer_text TEXT NOT NULL,
  job_id_first_asked UUID REFERENCES public.jobs (id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT qa_memory_question_not_empty CHECK (length(trim(question_text)) > 0),
  CONSTRAINT qa_memory_answer_not_empty CHECK (length(trim(answer_text)) > 0)
);

CREATE INDEX qa_memory_question_normalized_trgm_idx
  ON public.qa_memory USING gin (question_normalized gin_trgm_ops);
CREATE INDEX qa_memory_created_at_idx ON public.qa_memory (created_at DESC);

COMMENT ON TABLE public.qa_memory IS
  'Reusable answers to ATS questions; matched fuzzily on question text.';

-- ---------------------------------------------------------------------------
-- profiles (optional DB mirror of profile JSON; JSON file remains source for editing)
-- ---------------------------------------------------------------------------

CREATE TABLE public.profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT NOT NULL UNIQUE DEFAULT 'default',
  data JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.profiles IS
  'Structured applicant profile (contact, experience, skills). Synced from data/profile.json.';

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER jobs_set_updated_at
  BEFORE UPDATE ON public.jobs
  FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER qa_memory_set_updated_at
  BEFORE UPDATE ON public.qa_memory
  FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER profiles_set_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Dedup: fuzzy match on normalized company + title
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.find_duplicate_job(
  p_company TEXT,
  p_title TEXT,
  p_similarity_threshold REAL DEFAULT 0.72
)
RETURNS UUID
LANGUAGE sql
STABLE
AS $$
  SELECT j.id
  FROM public.jobs j
  WHERE similarity(j.normalized_company, public.normalize_job_text(p_company)) >= p_similarity_threshold
    AND similarity(j.normalized_title, public.normalize_job_text(p_title)) >= p_similarity_threshold
  ORDER BY
    (
      similarity(j.normalized_company, public.normalize_job_text(p_company))
      + similarity(j.normalized_title, public.normalize_job_text(p_title))
    ) DESC,
    j.date_found DESC
  LIMIT 1;
$$;

COMMENT ON FUNCTION public.find_duplicate_job IS
  'Return an existing job id when company+title fuzzy-match above threshold.';

-- ---------------------------------------------------------------------------
-- Q&A lookup: fuzzy match on question text
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.find_qa_answer(
  p_question TEXT,
  p_similarity_threshold REAL DEFAULT 0.75
)
RETURNS TABLE (
  id UUID,
  question_text TEXT,
  answer_text TEXT,
  similarity_score REAL
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    q.id,
    q.question_text,
    q.answer_text,
    similarity(q.question_normalized, public.normalize_job_text(p_question)) AS similarity_score
  FROM public.qa_memory q
  WHERE similarity(q.question_normalized, public.normalize_job_text(p_question)) >= p_similarity_threshold
  ORDER BY similarity_score DESC, q.created_at DESC
  LIMIT 1;
$$;

COMMENT ON FUNCTION public.find_qa_answer IS
  'Return the best matching stored answer for a given ATS question.';

-- ---------------------------------------------------------------------------
-- ATS platform detection helper (URL pattern based)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.detect_ats_platform(p_url TEXT)
RETURNS ats_platform
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE
    WHEN p_url ~* '(greenhouse\.io|boards\.greenhouse\.io)' THEN 'greenhouse'::ats_platform
    WHEN p_url ~* '(jobs\.lever\.co|lever\.co)' THEN 'lever'::ats_platform
    WHEN p_url ~* 'myworkdayjobs\.com' THEN 'workday'::ats_platform
    WHEN p_url ~* 'smartrecruiters\.com' THEN 'smartrecruiters'::ats_platform
    ELSE 'unknown'::ats_platform
  END;
$$;

-- ---------------------------------------------------------------------------
-- Row Level Security (backend uses service_role; deny anon/authenticated by default)
-- ---------------------------------------------------------------------------

ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qa_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- No policies for anon/authenticated roles: tables are backend-only via service_role.
