"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/AuthProvider";

function NavItem({
  href,
  label,
}: {
  href: string;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="rounded-xl px-3 py-2 text-sm text-zinc-300 hover:bg-white/5 hover:text-white transition-colors"
    >
      {label}
    </Link>
  );
}

export function AppShell({
  title,
  children,
  connected = false,
}: {
  title: string;
  children: React.ReactNode;
  connected?: boolean;
}) {
  const { user, signOut } = useAuth();
  const email = user?.email ?? "Signed in";

  async function handleSignOut() {
    await signOut();
    window.location.href = "/login";
  }

  return (
    <div className="min-h-screen">
      <div className="mx-auto flex w-full max-w-6xl gap-6 px-4 py-6">
        <aside className="hidden w-60 shrink-0 md:block">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center justify-between">
              <div className="text-base font-semibold tracking-tight text-white">
                ProjectEagle
              </div>
              <div className="text-[10px] uppercase tracking-wider text-zinc-500">
                EU jobs & MSc
              </div>
              <div className="h-2.5 w-2.5 rounded-full bg-[var(--color-accent)]" />
            </div>
            <div className="mt-4 flex flex-col gap-1">
              <NavItem href="/" label="Dashboard" />
              <NavItem href="/jobs" label="Jobs & Scholarships" />
              <NavItem href="/settings" label="Settings" />
              <NavItem href="/logs" label="Logs" />
            </div>
            <div className="mt-4 border-t border-white/10 pt-4">
              <div className="truncate text-xs text-zinc-400">{email}</div>
              <button
                type="button"
                onClick={handleSignOut}
                className="mt-2 w-full rounded-xl border border-white/10 px-3 py-2 text-xs text-zinc-300 hover:bg-white/5"
              >
                Sign out
              </button>
            </div>
          </div>
          <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4 text-xs text-zinc-400">
            VPN reminder: run automation behind a VPN and keep daily caps low.
          </div>
        </aside>

        <main className="min-w-0 flex-1">
          <header className="flex items-center justify-between">
            <div>
              <div className="text-sm text-zinc-400">ProjectEagle</div>
              <h1 className="text-2xl font-semibold tracking-tight text-white">
                {title}
              </h1>
            </div>
            <div className="hidden items-center gap-2 md:flex">
              <span
                className={`inline-flex items-center rounded-full border px-3 py-1 text-xs ${
                  connected
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                    : "border-white/10 bg-white/5 text-zinc-300"
                }`}
              >
                {connected ? "API connected" : "API offline"}
              </span>
            </div>
          </header>

          <div className="mt-6">{children}</div>
        </main>
      </div>
    </div>
  );
}

