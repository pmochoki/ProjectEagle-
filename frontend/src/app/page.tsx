"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { StatCard } from "@/components/StatCard";
import { StatusBadge, type JobStatus } from "@/components/StatusBadge";
import {
  fetchJobs,
  fetchStats,
  runScraper,
  type Job,
  type Stats,
} from "@/lib/api";

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, j] = await Promise.all([fetchStats(), fetchJobs()]);
      setStats(s);
      setJobs(j.slice(0, 20));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleScrape() {
    setScraping(true);
    setError(null);
    try {
      await runScraper();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scraper failed");
    } finally {
      setScraping(false);
    }
  }

  return (
    <AppShell title="Dashboard" connected={!error && !loading}>
      {error && (
        <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error} — make sure the backend is running on port 8000 and Supabase
          keys are set in `.env`.
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={handleScrape}
          disabled={scraping}
          className="rounded-xl bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-black transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {scraping ? "Scraping LinkedIn…" : "Run scraper"}
        </button>
        <button
          type="button"
          onClick={load}
          className="rounded-xl border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5"
        >
          Refresh
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Jobs Found" value={stats?.found ?? "—"} />
        <StatCard label="Applied" value={stats?.applied ?? "—"} />
        <StatCard label="Pending" value={stats?.pending ?? "—"} />
        <StatCard label="Cover letters" value={stats?.with_cover_letter ?? "—"} />
      </div>

      <div className="mt-6 rounded-2xl border border-white/10 bg-white/5">
        <div className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-medium text-white">Recent jobs</div>
            <div className="mt-1 text-xs text-zinc-400">
              External-apply roles only (company website links).
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-zinc-300">
              Needs answer: {stats?.needs_answer ?? 0}
            </span>
            <span className="inline-flex items-center rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-zinc-300">
              Failed: {stats?.failed ?? 0}
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
                <th className="px-4 py-3 font-medium">Scraped</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-zinc-400">
                    Loading…
                  </td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-zinc-400">
                    No jobs yet. Run the scraper to find external-apply roles.
                  </td>
                </tr>
              ) : (
                jobs.map((r) => (
                  <tr key={r.id} className="hover:bg-white/5">
                    <td className="px-4 py-3 font-medium text-white">
                      {r.company}
                    </td>
                    <td className="px-4 py-3 text-zinc-200">{r.title}</td>
                    <td className="px-4 py-3 text-zinc-300">{r.location}</td>
                    <td className="px-4 py-3 text-zinc-400">
                      {r.scraped_at?.slice(0, 10) ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={r.status as JobStatus} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}
