"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";

const LINKS = [
  { href: "#how-it-works", label: "How it Works" },
  { href: "#capabilities", label: "Capabilities" },
  { href: "#trust", label: "Trust" },
  { href: "#team", label: "Team" },
];

export function SiteNav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex min-w-0 items-center gap-2.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo.png"
            alt="Evidra Logo"
            className="h-8 w-auto object-contain sm:h-9"
          />
          <div className="min-w-0 leading-tight">
            <div className="text-lg font-bold tracking-tight text-white sm:text-xl">
              EVIDRA
            </div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
              Engineer Handoff
            </div>
          </div>
        </Link>

        <nav className="hidden items-center gap-6 text-sm text-slate-300 lg:flex">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="transition hover:text-cyan-400"
            >
              {l.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2 sm:flex">
          <Link
            href="/login"
            className="rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
          >
            Sign In
          </Link>
        </div>

        <button
          type="button"
          className="rounded-md border border-slate-700 p-2 text-slate-200 lg:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div className="border-t border-slate-800 bg-slate-950 px-4 py-4 lg:hidden">
          <div className="flex flex-col gap-3 text-sm text-slate-300">
            {LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="py-1 hover:text-cyan-400"
              >
                {l.label}
              </a>
            ))}
            <div className="mt-2 flex flex-col gap-2 border-t border-slate-800 pt-3">
              <Link href="/login" className="text-slate-200">
                Sign In
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
