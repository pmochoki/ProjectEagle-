import { AppShell } from "@/components/AppShell";
import { StatCard } from "@/components/StatCard";
import { StatusBadge, type JobStatus } from "@/components/StatusBadge";

export default function Home() {
  const rows: Array<{
    company: string;
    role: string;
    location: string;
    appliedAt: string;
    status: JobStatus;
  }> = [
    {
      company: "Acme AI",
      role: "Full-Stack Engineer",
      location: "Remote (EU)",
      appliedAt: "2026-06-02",
      status: "applied",
    },
    {
      company: "Greenfield Labs",
      role: "Backend Engineer (Python)",
      location: "Berlin, DE",
      appliedAt: "2026-06-01",
      status: "queued",
    },
    {
      company: "Orbit Systems",
      role: "Platform Engineer",
      location: "Amsterdam, NL",
      appliedAt: "2026-06-01",
      status: "needs_answer",
    },
    {
      company: "Nimbus Corp",
      role: "Software Engineer",
      location: "Remote",
      appliedAt: "2026-05-31",
      status: "failed",
    },
  ];

  const totals = rows.reduce(
    (acc, r) => {
      acc.found += 1;
      if (r.status === "applied") acc.applied += 1;
      if (r.status === "queued" || r.status === "new") acc.queued += 1;
      if (r.status === "failed") acc.failed += 1;
      if (r.status === "needs_answer") acc.needsAnswer += 1;
      return acc;
    },
    { found: 0, applied: 0, queued: 0, failed: 0, needsAnswer: 0 },
  );

  return (
    <AppShell title="Dashboard">
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Jobs Found" value={totals.found} />
        <StatCard label="Applied" value={totals.applied} />
        <StatCard label="Queued" value={totals.queued} />
        <StatCard label="Failed" value={totals.failed} />
      </div>

      <div className="mt-6 rounded-2xl border border-white/10 bg-white/5">
        <div className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-medium text-white">Applications</div>
            <div className="mt-1 text-xs text-zinc-400">
              Dummy data for UI scaffolding. Next step: connect to API + Supabase.
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-zinc-300">
              Needs answer: {totals.needsAnswer}
            </span>
            <span className="inline-flex items-center rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-zinc-300">
              Today: {rows.filter((r) => r.appliedAt === "2026-06-02").length}
            </span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-t border-white/10 bg-black/20 text-xs uppercase tracking-wide text-zinc-400">
              <tr>
                <th className="px-4 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Location</th>
                <th className="px-4 py-3 font-medium">Date applied</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {rows.map((r) => (
                <tr key={`${r.company}-${r.role}`} className="hover:bg-white/5">
                  <td className="px-4 py-3 font-medium text-white">
                    {r.company}
                  </td>
                  <td className="px-4 py-3 text-zinc-200">{r.role}</td>
                  <td className="px-4 py-3 text-zinc-300">{r.location}</td>
                  <td className="px-4 py-3 text-zinc-400">{r.appliedAt}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={r.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}
