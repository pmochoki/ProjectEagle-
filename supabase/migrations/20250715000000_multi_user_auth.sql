-- Multi-user auth: scope jobs, profiles, and Q&A per Supabase Auth user.

ALTER TABLE public.jobs
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users (id) ON DELETE CASCADE;

ALTER TABLE public.qa_memory
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users (id) ON DELETE CASCADE;

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users (id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS jobs_user_id_idx ON public.jobs (user_id);
CREATE INDEX IF NOT EXISTS qa_memory_user_id_idx ON public.qa_memory (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS profiles_user_id_unique
  ON public.profiles (user_id)
  WHERE user_id IS NOT NULL;

-- Per-user dedup
CREATE OR REPLACE FUNCTION public.find_duplicate_job(
  p_company TEXT,
  p_title TEXT,
  p_similarity_threshold REAL DEFAULT 0.72,
  p_user_id UUID DEFAULT NULL
)
RETURNS UUID
LANGUAGE sql
STABLE
AS $$
  SELECT j.id
  FROM public.jobs j
  WHERE similarity(j.normalized_company, public.normalize_job_text(p_company)) >= p_similarity_threshold
    AND similarity(j.normalized_title, public.normalize_job_text(p_title)) >= p_similarity_threshold
    AND (p_user_id IS NULL OR j.user_id = p_user_id)
  ORDER BY
    (
      similarity(j.normalized_company, public.normalize_job_text(p_company))
      + similarity(j.normalized_title, public.normalize_job_text(p_title))
    ) DESC,
    j.date_found DESC
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.find_qa_answer(
  p_question TEXT,
  p_similarity_threshold REAL DEFAULT 0.75,
  p_user_id UUID DEFAULT NULL
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
    AND (p_user_id IS NULL OR q.user_id = p_user_id)
  ORDER BY similarity_score DESC, q.created_at DESC
  LIMIT 1;
$$;

-- Seed profile row when a user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (user_id, slug, data)
  VALUES (
    NEW.id,
    NEW.id::text,
    jsonb_build_object(
      'contact', jsonb_build_object(
        'full_name', coalesce(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)),
        'email', NEW.email,
        'phone', '',
        'location', 'Budapest, Hungary',
        'linkedin_url', '',
        'github_url', '',
        'portfolio_url', ''
      ),
      'summary', 'Mechatronics engineering graduate — update this summary in Settings.',
      'skills', jsonb_build_object(
        'control_systems', jsonb_build_array('PLC programming', 'PID tuning'),
        'programming', jsonb_build_array('Python', 'C++'),
        'hardware', jsonb_build_array('Embedded systems', 'Robotics'),
        'cad', jsonb_build_array('SolidWorks'),
        'languages', jsonb_build_array('English', 'Hungarian')
      ),
      'experience', '[]'::jsonb,
      'projects', '[]'::jsonb,
      'education', jsonb_build_array(
        jsonb_build_object(
          'degree', 'BSc Mechatronics Engineering',
          'institution', 'Your university',
          'graduation_date', '2024',
          'notes', 'Update in Settings'
        )
      )
    )
  )
  ON CONFLICT DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();

-- Replace open backend policies with per-user RLS
DROP POLICY IF EXISTS "backend_all_jobs" ON public.jobs;
DROP POLICY IF EXISTS "backend_all_qa_memory" ON public.qa_memory;
DROP POLICY IF EXISTS "backend_all_profiles" ON public.profiles;

CREATE POLICY "users_select_own_jobs" ON public.jobs
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "users_insert_own_jobs" ON public.jobs
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "users_update_own_jobs" ON public.jobs
  FOR UPDATE TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "users_delete_own_jobs" ON public.jobs
  FOR DELETE TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "users_select_own_qa" ON public.qa_memory
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "users_insert_own_qa" ON public.qa_memory
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "users_update_own_qa" ON public.qa_memory
  FOR UPDATE TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "users_select_own_profiles" ON public.profiles
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "users_insert_own_profiles" ON public.profiles
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "users_update_own_profiles" ON public.profiles
  FOR UPDATE TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
