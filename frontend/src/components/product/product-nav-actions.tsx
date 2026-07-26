"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Home, Loader2, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useReviewStore } from "@/lib/store";

/**
 * Home + Logout controls for the product (dashboard) screen.
 */
export function ProductNavActions({
  variant = "dark",
}: {
  variant?: "dark" | "light";
}) {
  const router = useRouter();
  const clearFindings = useReviewStore((s) => s.clearFindings);
  const [loggingOut, setLoggingOut] = useState(false);

  const outline =
    variant === "dark"
      ? "border-slate-600 bg-transparent text-slate-100 hover:bg-slate-800"
      : "border-slate-300 text-slate-800 hover:bg-slate-100";

  const onLogout = async () => {
    setLoggingOut(true);
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
      clearFindings();
      router.replace("/login");
      router.refresh();
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button size="sm" variant="outline" className={outline} asChild>
        <Link href="/">
          <Home className="mr-1.5 h-4 w-4" />
          Home
        </Link>
      </Button>
      <Button
        size="sm"
        variant="outline"
        className={outline}
        onClick={() => void onLogout()}
        disabled={loggingOut}
      >
        {loggingOut ? (
          <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
        ) : (
          <LogOut className="mr-1.5 h-4 w-4" />
        )}
        Logout
      </Button>
    </div>
  );
}
