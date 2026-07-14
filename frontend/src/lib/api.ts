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

export async function fetchJobs(status?: string): Promise<Job[]> {
  const query = status ? `?status=${status}` : "";
  const data = await apiFetch<{ jobs: Job[] }>(`/jobs${query}`);
  return data.jobs;
}

export async function fetchJobSummary(jobId: string): Promise<string> {
  const data = await apiFetch<{ summary: string }>(`/jobs/${jobId}/summary`, {
    method: "POST",
  });
  return data.summary;
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
  detail?: string;
}

export async function fetchAiHealth(): Promise<AiHealth> {
  return apiFetch<AiHealth>("/ai/health");
}

export async function fetchDbHealth(): Promise<{ ok: boolean; jobs_count?: number }> {
  return apiFetch("/db/health");
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

export async function triggerAutomation(): Promise<void> {
  await apiFetch("/automation/run?force_eu=true&force_scholarships=true", {
    method: "POST",
  });
}
