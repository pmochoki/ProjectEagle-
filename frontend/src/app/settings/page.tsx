import { AppShell } from "@/components/AppShell";

export default function SettingsPage() {
  return (
    <AppShell title="Settings">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-sm font-medium text-white">Credentials</div>
          <div className="mt-2 space-y-2 text-sm text-zinc-300">
            <p>
              All secrets live in the project root <code className="text-zinc-200">.env</code> file
              (never in the frontend).
            </p>
            <ul className="list-inside list-disc space-y-1 text-zinc-400">
              <li>SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (backend only)</li>
              <li>LINKEDIN_EMAIL / LINKEDIN_PASSWORD</li>
              <li>CLAUDE_API_KEY</li>
              <li>TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID</li>
            </ul>
            <p className="mt-2 text-zinc-400">
              Edit your applicant profile at <code className="text-zinc-200">data/profile.json</code> in the project root.
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
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4 md:col-span-2">
          <div className="text-sm font-medium text-white">Telegram bot setup</div>
          <div className="mt-2 text-sm text-zinc-300">
            <ol className="list-inside list-decimal space-y-2 text-zinc-400">
              <li>Message <strong className="text-zinc-200">@BotFather</strong> on Telegram and create a bot.</li>
              <li>Copy the bot token into <code className="text-zinc-200">TELEGRAM_BOT_TOKEN</code>.</li>
              <li>Start a chat with your bot, then visit{" "}
                <code className="text-zinc-200">
                  https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates
                </code>{" "}
                to find your <code className="text-zinc-200">chat_id</code>.
              </li>
              <li>Set <code className="text-zinc-200">TELEGRAM_CHAT_ID</code> and restart the backend.</li>
            </ol>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
