const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "production" ? "/api" : "http://localhost:8000");

let authAccessToken: string | null = null;

export function setAuthToken(token: string | null) {
  authAccessToken = token;
}

export type JobStatus =
  | "new"
  | "queued"
  | "applied"
  | "needs_answer"
  | "skipped"
  | "failed";

export type ApplicationOutcome =
  | "applied"
  | "failed"
  | "review_pending"
  | "needs_answer"
  | "captcha"
  | string;

export interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  description: string;
  summary: string | null;
  description_en: string | null;
  fit_probability: number | null;
  fit_rationale: string | null;
  match_score: number | null;
  match_reasons: string[];
  sponsorship_offered: boolean | null;
  sponsorship_status: string | null;
  applicant_needs_sponsorship?: boolean | null;
  opportunity_type: "job" | "scholarship" | string;
  linkedin_url: string;
  external_apply_url: string;
  apply_url: string;
  is_easy_apply: boolean;
  status: JobStatus;
  cover_letter: string | null;
  scraped_at: string | null;
  applied_at: string | null;
  failure_reason?: string | null;
  application_outcome?: ApplicationOutcome | null;
  application_message?: string | null;
  review_pending?: boolean;
  pending_question?: string | null;
  search_location?: string | null;
  scrape_source?: string | null;
  source_job_id?: string | null;
}

export interface Stats {
  found: number;
  applied: number;
  pending: number;
  failed: number;
  needs_answer: number;
  with_cover_letter: number;
  scholarships?: number;
  applications_successful?: number;
  applications_failed?: number;
  applications_pending_review?: number;
}

async function apiFetchPublic<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    throw new Error(
      typeof detail === "string" ? detail : `API error ${res.status}`,
    );
  }
  return res.json() as Promise<T>;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(authAccessToken ? { Authorization: `Bearer ${authAccessToken}` } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (res.status === 401) {
    throw new Error("Sign in required — please log in again.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    throw new Error(
      typeof detail === "string" ? detail : `API error ${res.status}`,
    );
  }
  return res.json() as Promise<T>;
}

export interface ServiceHealthEntry {
  ok: boolean;
  detail?: string;
  jobs_count?: number;
  model?: string;
  configured?: boolean;
  local_only?: boolean;
  vercel?: boolean;
  token_configured?: boolean;
  thread_alive?: boolean;
  enabled?: boolean;
  session_saved?: boolean;
  public_mode?: boolean;
}

export interface ServicesHealth {
  ok: boolean;
  host: "vercel" | "local" | string;
  services: {
    supabase: ServiceHealthEntry;
    claude: ServiceHealthEntry;
    linkedin: ServiceHealthEntry;
    telegram: ServiceHealthEntry;
    automation: ServiceHealthEntry;
  };
}

export async function fetchServicesHealth(): Promise<ServicesHealth> {
  return apiFetchPublic<ServicesHealth>("/services/health");
}

export interface ClaudePingResult {
  ok: boolean;
  model?: string;
  reply?: string;
  input_tokens?: number;
  output_tokens?: number;
}

export async function pingClaude(): Promise<ClaudePingResult> {
  return apiFetch<ClaudePingResult>("/ai/ping", { method: "POST" });
}

export async function fetchProfileFull(): Promise<Record<string, unknown>> {
  const data = await apiFetch<{ profile: Record<string, unknown> }>("/profile/full");
  return data.profile;
}

export async function saveProfile(profile: Record<string, unknown>): Promise<void> {
  await apiFetch("/profile", {
    method: "PUT",
    body: JSON.stringify({ data: profile }),
  });
}

export async function fetchStats(): Promise<Stats> {
  return apiFetch<Stats>("/stats");
}

export async function fetchJobs(options?: {
  status?: string;
  limit?: number;
  offset?: number;
  review_pending?: boolean;
}): Promise<{ jobs: Job[]; has_more: boolean }> {
  const params = new URLSearchParams();
  if (options?.status) params.set("status", options.status);
  if (options?.limit != null) params.set("limit", String(options.limit));
  if (options?.offset != null) params.set("offset", String(options.offset));
  if (options?.review_pending != null) {
    params.set("review_pending", String(options.review_pending));
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  const data = await apiFetch<{
    jobs: Job[];
    has_more?: boolean;
  }>(`/jobs${query}`);
  return { jobs: data.jobs, has_more: Boolean(data.has_more) };
}

export interface JobAnalysis {
  summary: string;
  description_en: string;
  fit_probability: number;
  fit_rationale: string;
  cached?: boolean;
}

export async function fetchJobAnalysis(jobId: string): Promise<JobAnalysis> {
  const parse = (data: JobAnalysis & { ok: boolean }) => ({
    summary: data.summary,
    description_en: data.description_en,
    fit_probability: data.fit_probability,
    fit_rationale: data.fit_rationale,
    cached: data.cached,
  });

  try {
    const data = await apiFetch<JobAnalysis & { ok: boolean }>(
      `/jobs/${jobId}/analyze`,
      { method: "POST" },
    );
    return parse(data);
  } catch (analyzeErr) {
    const msg = analyzeErr instanceof Error ? analyzeErr.message : "";
    // Older deployments only expose POST /summary
    if (!msg.includes("Not Found") && !msg.includes("404")) {
      throw formatAnalysisError(analyzeErr);
    }
    try {
      const data = await apiFetch<JobAnalysis & { ok: boolean }>(
        `/jobs/${jobId}/summary`,
        { method: "POST" },
      );
      return parse(data);
    } catch (summaryErr) {
      throw formatAnalysisError(summaryErr);
    }
  }
}

function formatAnalysisError(err: unknown): Error {
  const msg = err instanceof Error ? err.message : "Analysis failed";
  if (msg.includes("not_found_error") || msg.includes("model:")) {
    return new Error(
      "Claude model unavailable — update CLAUDE_MODEL on Vercel to claude-sonnet-4-6 and redeploy.",
    );
  }
  if (msg.includes("Profile not found") || msg.includes("Profile missing")) {
    return new Error("Complete your profile in Settings before generating summaries.");
  }
  if (msg.includes("CLAUDE_API_KEY") || msg.includes("Missing CLAUDE")) {
    return new Error("Claude API key missing — set CLAUDE_API_KEY on the server.");
  }
  if (msg.includes("no description")) {
    return new Error("This listing has no description text to summarize.");
  }
  return new Error(msg || "Could not load summary.");
}

export async function fetchJobSummary(jobId: string): Promise<string> {
  const analysis = await fetchJobAnalysis(jobId);
  return analysis.summary;
}

export async function generateCoverLetter(jobId: string): Promise<string> {
  const data = await apiFetch<{ cover_letter: string }>(
    `/jobs/${jobId}/cover-letter`,
    { method: "POST" },
  );
  return data.cover_letter;
}

export async function updateJobStatus(
  jobId: string,
  status: JobStatus,
): Promise<void> {
  await apiFetch(`/jobs/${jobId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function runScraper(): Promise<void> {
  await apiFetch("/scraper/run", { method: "POST" });
}

export async function runEuJobsScraper(): Promise<void> {
  await apiFetch("/scraper/eu-jobs", { method: "POST" });
}

export async function runScholarshipScraper(): Promise<void> {
  await apiFetch("/scraper/scholarships", { method: "POST" });
}

export async function runProfessionScraper(): Promise<void> {
  await apiFetch("/scraper/profession", { method: "POST" });
}

export async function runCanary(): Promise<void> {
  await apiFetch("/scraper/canary", { method: "POST" });
}

export async function applyToJob(jobId: string): Promise<{ outcome: string; message: string }> {
  const data = await apiFetch<{ result: { outcome: string; message: string } }>(
    `/jobs/${jobId}/apply`,
    { method: "POST" },
  );
  return data.result;
}

export async function approveJob(jobId: string): Promise<{ outcome: string; message: string }> {
  const data = await apiFetch<{ result: { outcome: string; message: string } }>(
    `/jobs/${jobId}/approve`,
    { method: "POST" },
  );
  return data.result;
}

export interface AiHealth {
  ok: boolean;
  configured: boolean;
  model?: string;
  detail?: string;
}

export async function fetchAiHealth(): Promise<AiHealth> {
  return apiFetchPublic<AiHealth>("/ai/health");
}

export async function fetchDbHealth(): Promise<{ ok: boolean; jobs_count?: number }> {
  return apiFetchPublic("/db/health");
}

export interface AutomationRunEntry {
  at: string;
  kind: string;
  message: string;
  ok: boolean;
  details?: Record<string, unknown>;
}

export interface AutomationRuns {
  ok: boolean;
  runs: AutomationRunEntry[];
  cycles_completed: number;
  last_error: string;
}

export async function fetchAutomationRuns(limit = 50): Promise<AutomationRuns> {
  return apiFetch<AutomationRuns>(`/automation/runs?limit=${limit}`);
}

export interface AutomationStatus {
  enabled: boolean;
  thread_alive: boolean;
  apply_enabled: boolean;
  apply_max_per_day: number;
  poll_minutes: number;
  state: {
    last_eu_scrape_at: string | null;
    last_scholarship_scrape_at: string | null;
    applications_today_count: number;
    last_apply_message: string;
    last_error?: string;
    run_history?: AutomationRunEntry[];
  };
}

export async function fetchAutomationStatus(): Promise<AutomationStatus> {
  return apiFetch<AutomationStatus>("/automation/status");
}

export interface UrgencyStatus {
  urgency_active: boolean;
  permit_deadline: string | null;
  days_remaining: number | null;
  message: string;
  schedule: {
    check_cycle_minutes: number;
    linkedin_europe_hours: number;
    scholarships_hours: number;
    extra_sources_hours: number;
    apply_max_per_day: number;
    apply_min_interval_minutes: number;
  };
  sources: { id: string; name: string; kind: string }[];
}

export async function fetchUrgencyStatus(): Promise<UrgencyStatus> {
  return apiFetch<UrgencyStatus>("/urgency/status");
}

export async function runEuresScraper(): Promise<void> {
  await apiFetch("/scraper/eures", { method: "POST" });
}

export async function runAdzunaScraper(): Promise<void> {
  await apiFetch("/scraper/adzuna", { method: "POST" });
}

export async function runArbeitnowScraper(): Promise<void> {
  await apiFetch("/scraper/arbeitnow", { method: "POST" });
}

export async function runRemoteOkScraper(): Promise<void> {
  await apiFetch("/scraper/remoteok", { method: "POST" });
}

export async function triggerAutomation(): Promise<void> {
  await apiFetch("/automation/run?force_eu=true&force_scholarships=true", {
    method: "POST",
  });
}
