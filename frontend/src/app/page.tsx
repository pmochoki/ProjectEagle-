"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { StatCard } from "@/components/StatCard";
import { StatusBadge, type JobStatus } from "@/components/StatusBadge";
import {
  fetchJobs,
  fetchStats,
  fetchAiHealth,
  fetchDbHealth,
  fetchAutomationStatus,
  triggerAutomation,
  runScraper,
  runEuJobsScraper,
  runScholarshipScraper,
  runProfessionScraper,
  runCanary,
  type Job,
  type Stats,
} from "@/lib/api";

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [claudeReady, setClaudeReady] = useState(false);
  const [dbReady, setDbReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [euScraping, setEuScraping] = useState(false);
  const [scholarshipScraping, setScholarshipScraping] = useState(false);
  const [professionScraping, setProfessionScraping] = useState(false);
  const [canaryRunning, setCanaryRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [automation, setAutomation] = useState<string | null>(null);
  const [automationRunning, setAutomationRunning] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, j, ai, db, auto] = await Promise.all([
        fetchStats(),
        fetchJobs(),
        fetchAiHealth(),
        fetchDbHealth(),
        fetchAutomationStatus().catch(() => null),
      ]);
      setStats(s);
      setJobs(j.slice(0, 20));
      setClaudeReady(ai.configured);
      setDbReady(db.ok);
      if (auto?.enabled) {
        const parts = [
          auto.thread_alive ? "automation on" : "automation idle",
          `${auto.state.applications_today_count}/${auto.apply_max_per_day} applies today`,
        ];
        setAutomation(parts.join(" · "));
      } else {
        setAutomation("automation off (local backend only)");
      }
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

  async function handleEuScrape() {
    setEuScraping(true);
    setError(null);
    try {
      await runEuJobsScraper();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "EU scraper failed");
    } finally {
      setEuScraping(false);
    }
  }

  async function handleScholarshipScrape() {
    setScholarshipScraping(true);
    setError(null);
    try {
      await runScholarshipScraper();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scholarship scraper failed");
    } finally {
      setScholarshipScraping(false);
    }
  }

  async function handleProfessionScrape() {
    setProfessionScraping(true);
    setError(null);
    try {
      await runProfessionScraper();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Profession scraper failed");
    } finally {
      setProfessionScraping(false);
    }
  }

  async function handleCanary() {
    setCanaryRunning(true);
    setError(null);
    try {
      await runCanary();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Canary failed");
    } finally {
      setCanaryRunning(false);
    }
  }

  async function handleAutomationRun() {
    setAutomationRunning(true);
    setError(null);
    try {
      await triggerAutomation();
      setAutomation("Automation cycle started — check Telegram for progress");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Automation failed");
    } finally {
      setAutomationRunning(false);
    }
  }

  return (
    <AppShell title="Dashboard" connected={!error && !loading && dbReady}>
      <div className="mb-4 flex flex-wrap gap-2">
        <span
          className={`inline-flex items-center rounded-full border px-3 py-1 text-xs ${
            dbReady
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-white/10 bg-white/5 text-zinc-400"
          }`}
        >
          Supabase {dbReady ? "connected" : "offline"}
        </span>
        <span
          className={`inline-flex items-center rounded-full border px-3 py-1 text-xs ${
            claudeReady
              ? "border-violet-500/30 bg-violet-500/10 text-violet-300"
              : "border-amber-500/30 bg-amber-500/10 text-amber-300"
          }`}
        >
          Claude {claudeReady ? "ready" : "add CLAUDE_API_KEY in .env"}
        </span>
        {automation && (
          <span className="inline-flex items-center rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs text-sky-300">
            {automation}
          </span>
        )}
      </div>
      {error && (
        <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error} — check that Supabase keys are set in Vercel env vars (production)
          or the local backend is running on port 8000.
        </div>
      )}

      <p className="mb-4 text-sm text-zinc-400">
        Scans EU countries and Hungary for mechatronics roles, plus MSc scholarships.
        LinkedIn runs logged-in — verification prompts go to Telegram.
      </p>
      <div className="mb-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={handleAutomationRun}
          disabled={automationRunning}
          className="rounded-xl border border-sky-500/30 bg-sky-500/10 px-4 py-2 text-sm text-sky-200 hover:bg-sky-500/20 disabled:opacity-50"
        >
          {automationRunning ? "Starting automation…" : "Run automation cycle"}
        </button>
        <button
          type="button"
          onClick={handleEuScrape}
          disabled={euScraping}
          className="rounded-xl bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-black transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {euScraping ? "Scanning EU + Hungary…" : "Scan EU + Hungary jobs"}
        </button>
        <button
          type="button"
          onClick={handleScholarshipScrape}
          disabled={scholarshipScraping}
          className="rounded-xl border border-violet-500/30 bg-violet-500/10 px-4 py-2 text-sm text-violet-200 hover:bg-violet-500/20 disabled:opacity-50"
        >
          {scholarshipScraping ? "Scanning scholarships…" : "Scan scholarships"}
        </button>
        <button
          type="button"
          onClick={handleScrape}
          disabled={scraping}
          className="rounded-xl border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-50"
        >
          {scraping ? "Scraping LinkedIn…" : "LinkedIn (single search)"}
        </button>
        <button
          type="button"
          onClick={handleProfessionScrape}
          disabled={professionScraping}
          className="rounded-xl border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-50"
        >
          {professionScraping ? "Scraping profession.hu…" : "Scrape profession.hu"}
        </button>
        <button
          type="button"
          onClick={handleCanary}
          disabled={canaryRunning}
          className="rounded-xl border border-amber-500/30 px-4 py-2 text-sm text-amber-200 hover:bg-amber-500/10 disabled:opacity-50"
        >
          {canaryRunning ? "Running canary…" : "Run DOM canary"}
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-4 lg:grid-cols-6">
        <StatCard label="Jobs Found" value={stats?.found ?? "—"} />
        <StatCard label="Scholarships" value={stats?.scholarships ?? "—"} />
        <StatCard label="Applied OK" value={stats?.applications_successful ?? "—"} />
        <StatCard label="Apply failed" value={stats?.applications_failed ?? "—"} />
        <StatCard label="Pending review" value={stats?.applications_pending_review ?? "—"} />
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
