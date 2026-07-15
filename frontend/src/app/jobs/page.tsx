"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { FitProbabilityBadge } from "@/components/FitProbabilityBadge";
import { MatchScoreBadge } from "@/components/MatchScoreBadge";
import { SponsorshipBadge } from "@/components/SponsorshipBadge";
import { ListingExpandedPanel } from "@/components/ListingExpandedPanel";
import {
  ApplicationOutcomeBadge,
  OpportunityTypeBadge,
} from "@/components/ApplicationOutcomeBadge";
import { StatusBadge, type JobStatus } from "@/components/StatusBadge";
import { useAuth } from "@/contexts/AuthProvider";
import {
  fetchJobs,
  fetchJobAnalysis,
  generateCoverLetter,
  updateJobStatus,
  applyToJob,
  approveJob,
  type Job,
} from "@/lib/api";

type Filter = "all" | "jobs" | "scholarships" | "applied" | "failed";

export default function JobsPage() {
  return (
    <Suspense
      fallback={
        <AppShell title="Jobs & Scholarships" connected={false}>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-8 text-center text-zinc-400">
            Loading listings…
          </div>
        </AppShell>
      }
    >
      <JobsPageContent />
    </Suspense>
  );
}

function JobsPageContent() {
  const { session, loading: authLoading } = useAuth();
  const searchParams = useSearchParams();
  const highlightJobId = searchParams.get("job");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [summaryLoadingId, setSummaryLoadingId] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  const load = useCallback(async () => {
    if (!session) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setJobs(await fetchJobs());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    if (authLoading) {
      setLoading(true);
      return;
    }
    void load();
  }, [authLoading, load]);

  const filtered = jobs.filter((job) => {
    if (filter === "jobs") return job.opportunity_type !== "scholarship";
    if (filter === "scholarships") return job.opportunity_type === "scholarship";
    if (filter === "applied")
      return job.status === "applied" || job.application_outcome === "applied";
    if (filter === "failed")
      return job.status === "failed" || job.application_outcome === "failed";
    return true;
  });

  async function ensureAnalysis(job: Job) {
    if (job.summary && job.fit_probability != null && job.description_en) {
      return;
    }
    setSummaryLoadingId(job.id);
    try {
      const analysis = await fetchJobAnalysis(job.id);
      setJobs((prev) =>
        prev.map((j) =>
          j.id === job.id
            ? {
                ...j,
                summary: analysis.summary,
                description_en: analysis.description_en,
                fit_probability: analysis.fit_probability,
                fit_rationale: analysis.fit_rationale,
              }
            : j,
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setSummaryLoadingId(null);
    }
  }

  useEffect(() => {
    if (!highlightJobId || jobs.length === 0) return;
    const match = jobs.find(
      (j) => j.id === highlightJobId || j.id.startsWith(highlightJobId),
    );
    if (match) {
      setExpandedId(match.id);
      if (!match.summary || match.fit_probability == null) {
        void ensureAnalysis(match);
      }
    }
  }, [highlightJobId, jobs]);

  async function handleExpand(job: Job) {
    if (expandedId === job.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(job.id);
    if (!job.summary || job.fit_probability == null) {
      await ensureAnalysis(job);
    }
  }

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

  async function handleApply(jobId: string) {
    setApplyingId(jobId);
    setError(null);
    try {
      const result = await applyToJob(jobId);
      await load();
      if (result.outcome === "review_pending") {
        setError(`Form filled — approve in Telegram or dashboard: /approve ${jobId}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Apply failed");
    } finally {
      setApplyingId(null);
    }
  }

  async function handleApprove(jobId: string) {
    setApplyingId(jobId);
    setError(null);
    try {
      await approveJob(jobId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setApplyingId(null);
    }
  }

  async function handleStatus(jobId: string, status: JobStatus) {
    try {
      await updateJobStatus(jobId, status);
      setJobs((prev) =>
        prev.map((j) =>
          j.id === jobId
            ? {
                ...j,
                status,
                application_outcome: status === "applied" ? "applied" : j.application_outcome,
              }
            : j,
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Status update failed");
    }
  }

  const filters: { id: Filter; label: string }[] = [
    { id: "all", label: "All" },
    { id: "jobs", label: "Jobs" },
    { id: "scholarships", label: "Scholarships" },
    { id: "applied", label: "Applied" },
    { id: "failed", label: "Failed" },
  ];

  return (
    <AppShell title="Jobs & Scholarships" connected={!error && !loading}>
      {error && (
        <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        {filters.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilter(f.id)}
            className={`rounded-full border px-3 py-1 text-xs ${
              filter === f.id
                ? "border-[var(--color-accent)] bg-[var(--color-accent)]/20 text-white"
                : "border-white/10 text-zinc-400 hover:bg-white/5"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="mb-4 text-sm text-zinc-400">
        Click a listing for an AI summary before you apply. Application results show
        whether auto-apply succeeded, failed, or is waiting for your approval.
      </div>

      {loading ? (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-8 text-center text-zinc-400">
          Loading listings…
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-8 text-center text-zinc-400">
          No listings in this filter. Run a scan from the Dashboard.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((job) => {
            const expanded = expandedId === job.id;
            return (
              <div
                key={job.id}
                className="rounded-2xl border border-white/10 bg-white/5"
              >
                <button
                  type="button"
                  onClick={() => handleExpand(job)}
                  className="flex w-full flex-col gap-2 p-4 text-left md:flex-row md:items-center md:justify-between"
                >
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="font-medium text-white">{job.title}</div>
                      <OpportunityTypeBadge type={job.opportunity_type} />
                    </div>
                    <div className="text-sm text-zinc-300">
                      {job.company} · {job.location}
                    </div>
                    <div className="mt-1">
                      <SponsorshipBadge
                        status={job.sponsorship_status}
                        offered={job.sponsorship_offered}
                      />
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <MatchScoreBadge value={job.match_score} compact />
                    <FitProbabilityBadge
                      value={job.fit_probability}
                      loading={summaryLoadingId === job.id}
                      compact
                    />
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
                    <ApplicationOutcomeBadge
                      outcome={job.application_outcome}
                      message={
                        job.application_message ||
                        job.failure_reason ||
                        undefined
                      }
                    />

                    <ListingExpandedPanel
                      job={job}
                      loading={summaryLoadingId === job.id}
                      error={null}
                    />

                    <div className="mt-4 flex flex-wrap gap-2">
                      <a
                        href={job.external_apply_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded-xl bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-black hover:opacity-90"
                      >
                        {job.opportunity_type === "scholarship"
                          ? "Open programme link"
                          : "Apply on company site"}
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
                      {job.opportunity_type !== "scholarship" && (
                        <>
                          <button
                            type="button"
                            onClick={() => handleApply(job.id)}
                            disabled={applyingId === job.id}
                            className="rounded-xl bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
                          >
                            {applyingId === job.id ? "Applying…" : "Auto-apply (ATS)"}
                          </button>
                          {job.status === "queued" && (
                            <button
                              type="button"
                              onClick={() => handleApprove(job.id)}
                              disabled={applyingId === job.id}
                              className="rounded-xl border border-violet-500/40 px-4 py-2 text-sm text-violet-200 hover:bg-violet-500/10 disabled:opacity-50"
                            >
                              Approve submit
                            </button>
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
                        </>
                      )}
                      <button
                        type="button"
                        onClick={() => handleStatus(job.id, "applied")}
                        className="rounded-xl border border-emerald-500/30 px-4 py-2 text-sm text-emerald-200 hover:bg-emerald-500/10"
                      >
                        Mark applied manually
                      </button>
                      <button
                        type="button"
                        onClick={() => handleStatus(job.id, "failed")}
                        className="rounded-xl border border-rose-500/30 px-4 py-2 text-sm text-rose-200 hover:bg-rose-500/10"
                      >
                        Mark failed
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
