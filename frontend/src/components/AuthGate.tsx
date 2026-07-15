"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/contexts/AuthProvider";

/** Client-side auth redirect — replaces Edge middleware for Vercel services deploy. */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isLogin = pathname === "/login";

  useEffect(() => {
    if (loading) return;
    if (!session && !isLogin) {
      const next = pathname === "/" ? "" : `?next=${encodeURIComponent(pathname)}`;
      router.replace(`/login${next}`);
      return;
    }
    if (session && isLogin) {
      router.replace("/");
    }
  }, [loading, session, isLogin, pathname, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-zinc-400">
        Loading…
      </div>
    );
  }

  if (!session && !isLogin) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-zinc-400">
        Redirecting to sign in…
      </div>
    );
  }

  return <>{children}</>;
}
