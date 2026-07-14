"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { fetchProfileFull, saveProfile } from "@/lib/api";

export default function SettingsPage() {
  const [profileJson, setProfileJson] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const profile = await fetchProfileFull();
      setProfileJson(JSON.stringify(profile, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load profile");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const parsed = JSON.parse(profileJson) as Record<string, unknown>;
      await saveProfile(parsed);
      setMessage("Profile saved — cover letters and auto-apply will use this data.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed — check JSON is valid");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell title="Settings">
      <div className="grid gap-4">
        <div className="rounded-2xl border border-sky-500/20 bg-sky-500/5 p-4">
          <div className="text-sm font-medium text-sky-200">Your account profile</div>
          <p className="mt-2 text-sm text-zinc-300">
            Each signed-in user has a private profile (mechatronics BSc, skills, experience).
            Edit below — used for cover letters and ATS auto-fill. Your friend gets their own
            profile when they create an account.
          </p>
        </div>

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        )}
        {message && (
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
            {message}
          </div>
        )}

        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="mb-2 text-sm font-medium text-white">Profile JSON</div>
          {loading ? (
            <p className="text-sm text-zinc-400">Loading profile…</p>
          ) : (
            <textarea
              value={profileJson}
              onChange={(e) => setProfileJson(e.target.value)}
              rows={24}
              className="w-full rounded-xl border border-white/10 bg-black/30 p-3 font-mono text-xs text-zinc-200"
              spellCheck={false}
            />
          )}
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || loading}
            className="mt-3 rounded-xl bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-black hover:opacity-90 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save profile"}
          </button>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-zinc-400">
          <p className="font-medium text-white">Local automation (your Mac)</p>
          <p className="mt-2">
            Scrapers and Telegram still run on your machine. Set{" "}
            <code className="text-zinc-200">AUTOMATION_USER_ID</code> in{" "}
            <code className="text-zinc-200">.env</code> to your account UUID (Settings → copy from
            browser devtools after sign-in, or Supabase dashboard) so background scans attach to
            your account.
          </p>
        </div>
      </div>
    </AppShell>
  );
}
