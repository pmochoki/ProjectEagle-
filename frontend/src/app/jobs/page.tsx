"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { StatusBadge, type JobStatus } from "@/components/StatusBadge";
import {
  fetchJobs,
  generateCoverLetter,
  updateJobStatus,
  type Job,
} from "@/lib/api";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [generatingId, setGeneratingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setJobs(await fetchJobs());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleGenerate(jobId: string) {
    setGeneratingId(jobId);
    setError(null);
    try {
      const letter = await generateCoverLetter(jobId);
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, cover_letter: letter } : j)),
      );
      setExpandedId(jobId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cover letter failed");
    } finally {
      setGeneratingId(null);
    }
  }

  async function handleStatus(jobId: string, status: JobStatus) {
    try {
      await updateJobStatus(jobId, status);
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, status } : j)),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Status update failed");
    }
  }

  return (
    <AppShell title="Jobs" connected={!error && !loading}>
      {error && (
        <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <div className="mb-4 text-sm text-zinc-400">
        External-apply jobs scraped from LinkedIn. Click a row to expand, generate
        a cover letter with AI, then open the company apply link.
      </div>

      {loading ? (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-8 text-center text-zinc-400">
          Loading jobs…
        </div>
      ) : jobs.length === 0 ? (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-8 text-center text-zinc-400">
          No external-apply jobs yet. Run the scraper from the Dashboard.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {jobs.map((job) => {
            const expanded = expandedId === job.id;
            return (
              <div
                key={job.id}
                className="rounded-2xl border border-white/10 bg-white/5"
              >
                <button
                  type="button"
                  onClick={() => setExpandedId(expanded ? null : job.id)}
                  className="flex w-full flex-col gap-2 p-4 text-left md:flex-row md:items-center md:justify-between"
                >
                  <div>
                    <div className="font-medium text-white">{job.title}</div>
                    <div className="text-sm text-zinc-300">
                      {job.company} · {job.location}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {job.cover_letter && (
                      <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300">
                        Cover letter
                      </span>
                    )}
                    <StatusBadge status={job.status as JobStatus} />
                  </div>
                </button>

                {expanded && (
                  <div className="border-t border-white/10 p-4">
                    <p className="line-clamp-4 text-sm text-zinc-300">
                      {job.description.slice(0, 500)}
                      {job.description.length > 500 ? "…" : ""}
                    </p>

                    <div className="mt-4 flex flex-wrap gap-2">
                      <a
                        href={job.external_apply_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded-xl bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-black hover:opacity-90"
                      >
                        Apply on company site
                      </a>
                      {job.linkedin_url && (
                        <a
                          href={job.linkedin_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded-xl border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5"
                        >
                          View on LinkedIn
                        </a>
                      )}
                      <button
                        type="button"
                        onClick={() => handleGenerate(job.id)}
                        disabled={generatingId === job.id}
                        className="rounded-xl border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-50"
                      >
                        {generatingId === job.id
                          ? "Generating…"
                          : job.cover_letter
                            ? "Regenerate cover letter"
                            : "Generate cover letter"}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleStatus(job.id, "applied")}
                        className="rounded-xl border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5"
                      >
                        Mark applied
                      </button>
                    </div>

                    {job.cover_letter && (
                      <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-4">
                        <div className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-400">
                          Cover letter
                        </div>
                        <pre className="whitespace-pre-wrap font-sans text-sm text-zinc-200">
                          {job.cover_letter}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
