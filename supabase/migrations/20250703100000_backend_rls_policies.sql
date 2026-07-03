-- Allow backend access via anon key (keys stay server-side only in FastAPI)
CREATE POLICY "backend_all_jobs" ON public.jobs
  FOR ALL TO anon, authenticated
  USING (true) WITH CHECK (true);

CREATE POLICY "backend_all_qa_memory" ON public.qa_memory
  FOR ALL TO anon, authenticated
  USING (true) WITH CHECK (true);

CREATE POLICY "backend_all_profiles" ON public.profiles
  FOR ALL TO anon, authenticated
  USING (true) WITH CHECK (true);
