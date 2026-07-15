"use client";

import { FitProbabilityBadge } from "@/components/FitProbabilityBadge";
import { MatchScoreBadge } from "@/components/MatchScoreBadge";
import { SponsorshipBadge } from "@/components/SponsorshipBadge";
import { listingPreview } from "@/lib/listingText";
import type { Job } from "@/lib/api";

export function ListingExpandedPanel({
  job,
  loading,
  error,
}: {
  job: Job;
  loading: boolean;
  error: string | null;
}) {
  const body = listingPreview(job);

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <div className="mb-4 flex flex-wrap items-start gap-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">Profile match</div>
          <div className="mt-1">
            <MatchScoreBadge value={job.match_score} />
          </div>
          {job.match_reasons && job.match_reasons.length > 0 && (
            <ul className="mt-2 max-w-md space-y-1 text-xs text-zinc-400">
              {job.match_reasons.map((reason) => (
                <li key={reason}>• {reason}</li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">Claude fit</div>
          <div className="mt-1">
            <FitProbabilityBadge value={job.fit_probability} loading={loading} />
          </div>
          {job.fit_rationale && (
            <p className="mt-2 max-w-md text-sm text-zinc-300">{job.fit_rationale}</p>
          )}
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">Sponsorship</div>
          <div className="mt-1">
            <SponsorshipBadge
              status={job.sponsorship_status}
              offered={job.sponsorship_offered}
            />
            {!job.sponsorship_status && (
              <span className="text-xs text-zinc-500">Not mentioned in listing</span>
            )}
            {job.applicant_needs_sponsorship && job.sponsorship_offered === false && (
              <p className="mt-1 text-xs text-rose-300">
                Your profile indicates you need visa sponsorship.
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-400">
        Summary (English)
      </div>
      {loading ? (
        <p className="text-sm text-zinc-400">Analyzing listing with Claude…</p>
      ) : error ? (
        <p className="text-sm text-rose-300">{error}</p>
      ) : job.summary ? (
        <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-zinc-200">
          {job.summary}
        </pre>
      ) : (
        <p className="text-sm text-zinc-400">
          No summary yet — add CLAUDE_API_KEY on the server and complete your profile in Settings.
        </p>
      )}

      {body && (
        <details className="mt-4" open>
          <summary className="cursor-pointer text-sm text-zinc-400 hover:text-zinc-200">
            Full listing (English)
          </summary>
          <div className="mt-3 max-h-64 overflow-y-auto rounded-lg border border-white/10 bg-black/20 p-3">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">{body}</p>
          </div>
        </details>
      )}
    </div>
  );
}
