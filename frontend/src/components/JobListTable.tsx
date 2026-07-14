"use client";

import { Fragment, useState } from "react";
import { StatusBadge, type JobStatus } from "@/components/StatusBadge";
import { OpportunityTypeBadge } from "@/components/ApplicationOutcomeBadge";
import { fetchJobSummary, type Job } from "@/lib/api";

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
  const [summaryLoadingId, setSummaryLoadingId] = useState<string | null>(null);

  async function ensureSummary(job: Job) {
    if (job.summary) return;
    setSummaryLoadingId(job.id);
    try {
      const summary = await fetchJobSummary(job.id);
      onJobUpdate?.(job.id, { summary });
    } finally {
      setSummaryLoadingId(null);
    }
  }

  async function toggleRow(job: Job) {
    if (expandedId === job.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(job.id);
    if (!job.summary) {
      await ensureSummary(job);
    }
  }

  const colCount = 6;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-t border-white/10 bg-black/20 text-xs uppercase tracking-wide text-zinc-400">
          <tr>
            <th className="px-4 py-3 font-medium">Company</th>
            <th className="px-4 py-3 font-medium">Role</th>
            <th className="px-4 py-3 font-medium">Location</th>
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
                    <td className="px-4 py-3 text-zinc-300">{job.location || "—"}</td>
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
                        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                            <OpportunityTypeBadge type={job.opportunity_type} />
                            {job.search_location && (
                              <span>Searched in: {job.search_location}</span>
                            )}
                          </div>

                          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-400">
                            Summary
                          </div>
                          {summaryLoadingId === job.id ? (
                            <p className="text-sm text-zinc-400">Generating summary…</p>
                          ) : job.summary ? (
                            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-zinc-200">
                              {job.summary}
                            </pre>
                          ) : (
                            <p className="text-sm text-zinc-400">Could not load summary.</p>
                          )}

                          {job.description && (
                            <details className="mt-4">
                              <summary className="cursor-pointer text-sm text-zinc-400 hover:text-zinc-200">
                                Full listing text
                              </summary>
                              <p className="mt-2 max-h-48 overflow-y-auto text-sm text-zinc-400">
                                {job.description.slice(0, 3000)}
                                {job.description.length > 3000 ? "…" : ""}
                              </p>
                            </details>
                          )}

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
          Click a row to expand · Use the link column to open the listing in a new tab
        </p>
      )}
    </div>
  );
}
