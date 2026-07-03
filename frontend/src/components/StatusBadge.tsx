export type JobStatus =
  | "new"
  | "queued"
  | "applied"
  | "needs_answer"
  | "skipped"
  | "failed";

const styles: Record<JobStatus, { label: string; className: string }> = {
  new: {
    label: "New",
    className: "bg-sky-500/15 text-sky-200 border-sky-500/20",
  },
  queued: {
    label: "Queued",
    className: "bg-white/10 text-white border-white/10",
  },
  applied: {
    label: "Applied",
    className: "bg-emerald-500/15 text-emerald-200 border-emerald-500/20",
  },
  needs_answer: {
    label: "Needs answer",
    className: "bg-amber-500/15 text-amber-200 border-amber-500/20",
  },
  skipped: {
    label: "Skipped",
    className: "bg-zinc-500/15 text-zinc-300 border-zinc-500/20",
  },
  failed: {
    label: "Failed",
    className: "bg-rose-500/15 text-rose-200 border-rose-500/20",
  },
};

export function StatusBadge({ status }: { status: JobStatus }) {
  const s = styles[status];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${s.className}`}
    >
      {s.label}
    </span>
  );
}
