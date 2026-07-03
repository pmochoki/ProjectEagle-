const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type JobStatus =
  | "new"
  | "queued"
  | "applied"
  | "needs_answer"
  | "skipped"
  | "failed";

export interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  description: string;
  linkedin_url: string;
  external_apply_url: string;
  apply_url: string;
  is_easy_apply: boolean;
  status: JobStatus;
  cover_letter: string | null;
  scraped_at: string | null;
  applied_at: string | null;
}

export interface Stats {
  found: number;
  applied: number;
  pending: number;
  failed: number;
  needs_answer: number;
  with_cover_letter: number;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
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

export async function fetchStats(): Promise<Stats> {
  return apiFetch<Stats>("/stats");
}

export async function fetchJobs(status?: string): Promise<Job[]> {
  const query = status ? `?status=${status}` : "";
  const data = await apiFetch<{ jobs: Job[] }>(`/jobs${query}`);
  return data.jobs;
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
