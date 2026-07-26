"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Loader2 } from "lucide-react";

/**
 * Client-side auth guard for /dashboard.
 * Middleware is primary; this blocks flash of protected UI if cookie is missing/expired.
 */
export function RequireUserSession({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/auth/me", { credentials: "include" });
        if (!res.ok) {
          router.replace("/login?next=/dashboard");
          return;
        }
        const data = (await res.json()) as {
          authenticated?: boolean;
          kind?: string;
        };
        if (!data.authenticated || data.kind !== "user") {
          router.replace("/login?next=/dashboard");
          return;
        }
        if (!cancelled) setReady(true);
      } catch {
        router.replace("/login?next=/dashboard");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-300">
        <div className="flex items-center gap-2 text-sm">
          <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
          Checking session…
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
