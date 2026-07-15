export function SponsorshipBadge({
  status,
  offered,
}: {
  status?: string | null;
  offered?: boolean | null;
}) {
  if (offered === true || status === "offered") {
    return (
      <span className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-200">
        Visa sponsorship
      </span>
    );
  }
  if (offered === false || status === "not_offered") {
    return (
      <span className="inline-flex items-center rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-xs text-rose-200">
        No sponsorship
      </span>
    );
  }
  if (status === "unclear") {
    return (
      <span className="inline-flex items-center rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-200">
        Sponsorship unclear
      </span>
    );
  }
  return null;
}
