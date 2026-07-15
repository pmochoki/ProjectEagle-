"use client";

import { Fragment, useState } from "react";
import { FitProbabilityBadge } from "@/components/FitProbabilityBadge";
import { ListingExpandedPanel } from "@/components/ListingExpandedPanel";
import { MatchScoreBadge } from "@/components/MatchScoreBadge";
import { SponsorshipBadge } from "@/components/SponsorshipBadge";
import { OpportunityTypeBadge } from "@/components/ApplicationOutcomeBadge";
import { StatusBadge, type JobStatus } from "@/components/StatusBadge";
import { fetchJobAnalysis, type Job } from "@/lib/api";

function listingUrl(job: Job): string | null {
  const url =
    job.external_apply_url?.trim() ||
    job.apply_url?.trim() ||
    job.linkedin_url?.trim() ||
    "";
  return url || null;
}

function linkLabel(job: Job): string {
  if (job.opportunity_type === "scholarship") return "Programme";
  if (job.external_apply_url) return "Apply";
  if (job.linkedin_url) return "LinkedIn";
  return "Open";
}

type JobListTableProps = {
  jobs: Job[];
  loading?: boolean;
  emptyMessage?: string;
  onJobUpdate?: (jobId: string, patch: Partial<Job>) => void;
};

export function JobListTable({
  jobs,
  loading = false,
  emptyMessage = "No listings yet. Run a scan from the buttons above.",
  onJobUpdate,
}: JobListTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  async function ensureAnalysis(job: Job) {
    if (job.summary && job.fit_probability != null && job.description_en) return;
    setAnalyzingId(job.id);
    setAnalyzeError(null);
    try {
      const analysis = await fetchJobAnalysis(job.id);
      onJobUpdate?.(job.id, {
        summary: analysis.summary,
        description_en: analysis.description_en,
        fit_probability: analysis.fit_probability,
        fit_rationale: analysis.fit_rationale,
      });
    } catch (e) {
      setAnalyzeError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setAnalyzingId(null);
    }
  }

  async function toggleRow(job: Job) {
    if (expandedId === job.id) {
      setExpandedId(null);
      setAnalyzeError(null);
      return;
    }
    setExpandedId(job.id);
    setAnalyzeError(null);
    await ensureAnalysis(job);
  }

  const colCount = 8;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-t border-white/10 bg-black/20 text-xs uppercase tracking-wide text-zinc-400">
          <tr>
            <th className="px-4 py-3 font-medium">Company</th>
            <th className="px-4 py-3 font-medium">Role</th>
            <th className="px-4 py-3 font-medium">Location</th>
            <th className="px-4 py-3 font-medium">Match</th>
            <th className="px-4 py-3 font-medium">Claude fit</th>
            <th className="px-4 py-3 font-medium">Link</th>
            <th className="px-4 py-3 font-medium">Scraped</th>
            <th className="px-4 py-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/10">
          {loading ? (
            <tr>
              <td colSpan={colCount} className="px-4 py-8 text-center text-zinc-400">
                Loading…
              </td>
            </tr>
          ) : jobs.length === 0 ? (
            <tr>
              <td colSpan={colCount} className="px-4 py-8 text-center text-zinc-400">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            jobs.map((job) => {
              const expanded = expandedId === job.id;
              const url = listingUrl(job);
              const isAnalyzing = analyzingId === job.id;
              return (
                <Fragment key={job.id}>
                  <tr
                    onClick={() => toggleRow(job)}
                    className={`cursor-pointer transition-colors hover:bg-white/5 ${
                      expanded ? "bg-white/[0.07]" : ""
                    }`}
                    aria-expanded={expanded}
                  >
                    <td className="px-4 py-3 font-medium text-white">{job.company}</td>
                    <td className="px-4 py-3 text-zinc-200">
                      <div className="flex flex-wrap items-center gap-2">
                        <span>{job.title}</span>
                        {job.opportunity_type === "scholarship" && (
                          <OpportunityTypeBadge type={job.opportunity_type} />
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-zinc-300">
                      <div className="flex flex-col gap-1">
                        <span>{job.location || "—"}</span>
                        <SponsorshipBadge
                          status={job.sponsorship_status}
                          offered={job.sponsorship_offered}
                        />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <MatchScoreBadge value={job.match_score} compact />
                    </td>
                    <td className="px-4 py-3">
                      <FitProbabilityBadge
                        value={job.fit_probability}
                        loading={isAnalyzing}
                        compact
                      />
                    </td>
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      {url ? (
                        <a
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 rounded-lg border border-sky-500/30 bg-sky-500/10 px-2.5 py-1 text-xs font-medium text-sky-200 hover:bg-sky-500/20"
                        >
                          {linkLabel(job)} ↗
                        </a>
                      ) : (
                        <span className="text-xs text-zinc-500">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-zinc-400">
                      {job.scraped_at?.slice(0, 10) ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={job.status as JobStatus} />
                    </td>
                  </tr>
                  {expanded && (
                    <tr className="bg-black/30">
                      <td colSpan={colCount} className="px-4 py-4">
                        <ListingExpandedPanel
                          job={job}
                          loading={isAnalyzing}
                          error={expandedId === job.id ? analyzeError : null}
                        />
                        <div className="mt-4 flex flex-wrap gap-2">
                          {url && (
                            <a
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="rounded-xl bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-black hover:opacity-90"
                            >
                              {job.opportunity_type === "scholarship"
                                ? "Open programme"
                                : "Open listing"}
                            </a>
                          )}
                          {job.linkedin_url && job.linkedin_url !== url && (
                            <a
                              href={job.linkedin_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="rounded-xl border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5"
                            >
                              LinkedIn
                            </a>
                          )}
                          <a
                            href={`/jobs?job=${job.id}`}
                            className="rounded-xl border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5"
                          >
                            Full details & apply
                          </a>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })
          )}
        </tbody>
      </table>
      {!loading && jobs.length > 0 && (
        <p className="border-t border-white/10 px-4 py-2 text-xs text-zinc-500">
          Click a row to expand · Match % uses your profile · Claude fit % runs on first expand
        </p>
      )}
    </div>
  );
}
