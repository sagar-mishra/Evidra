import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  FileSearch,
  GitCompareArrows,
  Link2,
  ShieldCheck,
  TestTube2,
  UserCheck,
} from "lucide-react";
import { SiteNav } from "@/components/marketing/site-nav";

const CAPABILITIES = [
  {
    icon: FileSearch,
    title: "Deterministic change analysis",
    body: "Identify logic, tag, AOI, alarm, interlock and configuration changes before AI interpretation.",
  },
  {
    icon: Link2,
    title: "Operational impact tracing",
    body: "Connect PLC changes to equipment, sequences, requirements, alarms and I/O evidence.",
  },
  {
    icon: TestTube2,
    title: "Focused regression testing",
    body: "Recommend the tests most relevant to the affected behavior.",
  },
  {
    icon: UserCheck,
    title: "Engineer-controlled review",
    body: "Inspect source evidence, accept or reject findings, and retain final release authority.",
  },
];

const TRUST_POINTS = [
  "Deterministic PLC changes are separated from AI-assisted interpretation.",
  "Every material finding links back to source evidence.",
  "Uncertainty and unsupported cases are exposed.",
  "Qualified engineers retain final approval.",
  "EVIDRA does not modify, download or deploy PLC code.",
];

const STEPS = [
  {
    n: "01",
    title: "Analyze the release",
    body: "Upload baseline and revised Rockwell Studio 5000 L5X files with available requirements, alarm lists, I/O lists, or test documents.",
  },
  {
    n: "02",
    title: "Trace the impact",
    body: "EVIDRA identifies deterministic changes and maps them to potentially affected equipment, sequences, requirements, alarms, and I/O.",
  },
  {
    n: "03",
    title: "Review the evidence",
    body: "Engineers inspect source-linked findings, accept or reject conclusions, and review recommended regression tests before deployment.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <SiteNav />

      {/* HERO */}
      <section className="relative overflow-hidden border-b border-slate-900">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(14,165,233,0.12),_transparent_55%)]" />
        <div className="relative mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24 lg:py-28">
          <p className="mb-4 font-mono text-[11px] font-semibold uppercase tracking-[0.2em] text-cyan-400">
            Industrial Controls Release Assurance
          </p>
          <h1 className="max-w-3xl text-balance text-4xl font-bold tracking-tight text-white sm:text-5xl lg:text-6xl">
            Know what a PLC change affects before deployment.
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-relaxed text-slate-300 sm:text-lg">
            EVIDRA compares Rockwell L5X releases, traces changes to equipment
            and engineering requirements, and recommends evidence-backed
            regression tests for controls-engineer review.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/login"
              className="inline-flex items-center gap-2 rounded-md bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
            >
              Sign in to workspace
              <ArrowRight className="h-4 w-4" />
            </Link>
            <a
              href="#how-it-works"
              className="inline-flex items-center gap-2 rounded-md border border-slate-700 px-5 py-2.5 text-sm font-medium text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
            >
              See how it works
            </a>
          </div>
          <div className="mt-12 flex flex-wrap gap-6 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <GitCompareArrows className="h-3.5 w-3.5 text-teal-400" />
              Rockwell L5X first
            </span>
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-teal-400" />
              Engineer-approved only
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-amber-400" />
              Source-linked evidence
            </span>
          </div>
        </div>
      </section>

      {/* PROBLEM */}
      <section className="border-b border-slate-900 bg-slate-950">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
          <div className="max-w-3xl">
            <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              A code comparison is only the beginning.
            </h2>
            <p className="mt-4 text-base leading-relaxed text-slate-300 sm:text-lg">
              Existing comparison tools show what changed in the PLC program.
              Senior controls engineers must still determine which equipment,
              sequences, alarms, permissives, requirements, and tests may be
              affected. That work is commonly spread across Rockwell comparison
              tools, Excel files, engineering documents, and manual review.
            </p>
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section
        id="how-it-works"
        className="scroll-mt-20 border-b border-slate-900 bg-slate-900/40"
      >
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            How it works
          </h2>
          <p className="mt-2 max-w-2xl text-slate-400">
            From L5X upload to engineer-ready evidence in three steps.
          </p>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {STEPS.map((step) => (
              <div
                key={step.n}
                className="rounded-xl border border-slate-800 bg-slate-950/80 p-6 transition hover:border-cyan-500/40"
              >
                <div className="font-mono text-sm font-semibold text-cyan-400">
                  {step.n}
                </div>
                <h3 className="mt-3 text-lg font-semibold text-white">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">
                  {step.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CAPABILITIES */}
      <section
        id="capabilities"
        className="scroll-mt-20 border-b border-slate-900 bg-slate-950"
      >
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Capabilities
          </h2>
          <div className="mt-10 grid gap-5 sm:grid-cols-2">
            {CAPABILITIES.map((cap) => (
              <div
                key={cap.title}
                className="rounded-xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-6 shadow-lg shadow-black/20"
              >
                <cap.icon className="h-6 w-6 text-teal-400" />
                <h3 className="mt-4 text-lg font-semibold text-white">
                  {cap.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">
                  {cap.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* TRUST */}
      <section
        id="trust"
        className="scroll-mt-20 border-b border-slate-900 bg-slate-900/40"
      >
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
          <div className="grid gap-10 lg:grid-cols-2 lg:items-start">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                Built for engineer review, not autonomous control.
              </h2>
              <p className="mt-4 text-slate-400">
                EVIDRA is designed as a handoff surface for qualified controls
                engineers, not a black-box release bot.
              </p>
            </div>
            <ul className="space-y-3">
              {TRUST_POINTS.map((point) => (
                <li
                  key={point}
                  className="flex gap-3 rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm text-slate-300"
                >
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-teal-400" />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* INITIAL CUSTOMER */}
      <section className="border-b border-slate-900 bg-slate-950">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
          <h2 className="max-w-3xl text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Starting where release review is frequent and artifacts are
            accessible.
          </h2>
          <p className="mt-4 max-w-3xl text-base leading-relaxed text-slate-300 sm:text-lg">
            EVIDRA initially supports Rockwell Studio 5000 L5X projects for
            controls integrators serving water and wastewater systems and
            mission-critical data centers. We are starting with these segments
            because Rahul has direct controls experience in both and integrators
            can more readily obtain authorization for the engineering artifacts
            required for a structured evaluation.
          </p>
        </div>
      </section>

      {/* TEAM */}
      <section
        id="team"
        className="scroll-mt-20 border-b border-slate-900 bg-slate-900/40"
      >
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Built by controls, product and AI engineers.
          </h2>
          <p className="mt-4 max-w-3xl text-base leading-relaxed text-slate-300 sm:text-lg">
            Rahul has more than five years of industrial-controls experience
            across PLC programming, SCADA, FAT, commissioning, mining, utilities,
            industrial processing and mission-critical data centers. Sagar builds
            the L5X analysis, backend, AI, evaluation and deployment systems. Arun
            owns technical product requirements, release quality, testing and
            evaluation delivery. Abhijna owns customer research, outbound and
            acquisition operations.
          </p>
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { name: "Rahul", role: "Controls & domain" },
              { name: "Sagar", role: "Platform, AI & deploy" },
              { name: "Arun", role: "Product & quality" },
              { name: "Abhijna", role: "GTM & research" },
            ].map((m) => (
              <div
                key={m.name}
                className="rounded-lg border border-slate-800 bg-slate-950/70 px-4 py-3"
              >
                <div className="font-semibold text-white">{m.name}</div>
                <div className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
                  {m.role}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer className="bg-slate-950">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div className="flex items-center gap-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo.png" alt="" className="h-6 w-auto opacity-80" />
            <span className="font-semibold text-slate-400">EVIDRA</span>
            <span className="text-slate-700">|</span>
            <span>Every change, proven before production.</span>
          </div>
          <div>© {new Date().getFullYear()} Evidra. All rights reserved.</div>
        </div>
      </footer>
    </div>
  );
}
