export function MatchScoreBadge({
  value,
  compact = false,
}: {
  value?: number | null;
  compact?: boolean;
}) {
  if (value == null || Number.isNaN(value)) {
    return (
      <span
        className="inline-flex items-center rounded-full border border-white/10 px-2 py-0.5 text-xs text-zinc-500"
        title="Profile match score — save your profile in Settings"
      >
        —
      </span>
    );
  }

  const tone =
    value >= 70
      ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-200"
      : value >= 40
        ? "border-amber-500/40 bg-amber-500/15 text-amber-200"
        : "border-rose-500/40 bg-rose-500/15 text-rose-200";

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 font-medium ${tone} ${
        compact ? "text-xs" : "text-sm"
      }`}
      title="Profile match score (0–100) from your skills, education, and listing text"
    >
      {value}%
    </span>
  );
}
