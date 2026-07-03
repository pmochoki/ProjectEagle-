import { AppShell } from "@/components/AppShell";

export default function SettingsPage() {
  return (
    <AppShell title="Settings">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-violet-500/20 bg-violet-500/5 p-4 md:col-span-2">
          <div className="text-sm font-medium text-violet-200">
            Claude API setup (you&apos;re here now)
          </div>
          <ol className="mt-3 list-inside list-decimal space-y-2 text-sm text-zinc-300">
            <li>
              On the console screen: click <strong className="text-white">Individual</strong>{" "}
              (solo builder — correct for JantaSearcher).
            </li>
            <li>Add a payment method when prompted (pay-as-you-go, cents per letter).</li>
            <li>
              Go to <strong className="text-white">API Keys</strong> → Create key → copy it.
            </li>
            <li>
              Paste into <code className="text-zinc-200">/Users/mokoro/Jantasearcher/.env</code>:
              <pre className="mt-2 overflow-x-auto rounded-lg bg-black/30 p-3 text-xs text-emerald-300">
                CLAUDE_API_KEY=sk-ant-api03-...
              </pre>
            </li>
            <li>Restart the backend, refresh the dashboard — Claude badge turns violet.</li>
          </ol>
          <p className="mt-3 text-xs text-zinc-500">
            Model: Sonnet 4 (best quality). ~$0.03 per cover letter. Official docs:{" "}
            <a
              href="https://platform.claude.com/docs/en/about-claude/pricing"
              className="text-violet-300 underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              Anthropic pricing
            </a>
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-sm font-medium text-white">Other credentials</div>
          <div className="mt-2 space-y-2 text-sm text-zinc-300">
            <p>
              All secrets live in the project root <code className="text-zinc-200">.env</code> file
              (never in the frontend).
            </p>
            <ul className="list-inside list-disc space-y-1 text-zinc-400">
              <li>SUPABASE_URL, SUPABASE_ANON_KEY (already set)</li>
              <li>LINKEDIN_EMAIL / LINKEDIN_PASSWORD (for scraper)</li>
              <li>TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (optional)</li>
            </ul>
            <p className="mt-2 text-zinc-400">
              Edit your applicant profile at <code className="text-zinc-200">data/profile.json</code>.
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-sm font-medium text-white">Job search</div>
          <div className="mt-2 space-y-2 text-sm text-zinc-300">
            <p>Configure search criteria via environment variables:</p>
            <ul className="list-inside list-disc space-y-1 text-zinc-400">
              <li>JOB_SEARCH_TITLE</li>
              <li>JOB_SEARCH_LOCATION</li>
              <li>SCRAPER_MAX_PAGES, SCRAPER_DELAY_MIN/MAX</li>
            </ul>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
