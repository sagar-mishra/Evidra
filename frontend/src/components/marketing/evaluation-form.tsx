"use client";

import { useState, type FormEvent } from "react";
import { Loader2, Send } from "lucide-react";

const INDUSTRIES = [
  "Water/Wastewater",
  "Data Centers",
  "Mining",
  "Utilities",
  "Other",
] as const;

export function EvaluationForm() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    const form = new FormData(e.currentTarget);
    const payload = {
      fullName: String(form.get("fullName") || ""),
      company: String(form.get("company") || ""),
      email: String(form.get("email") || ""),
      role: String(form.get("role") || ""),
      industry: String(form.get("industry") || ""),
      rockwellStudio: String(form.get("rockwellStudio") || ""),
      upcomingRelease: String(form.get("upcomingRelease") || ""),
      artifactsAvailable: String(form.get("artifactsAvailable") || ""),
      notes: String(form.get("notes") || ""),
    };

    try {
      const res = await fetch("/api/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = (await res.json()) as { error?: string; message?: string };
      if (!res.ok) throw new Error(data.error || "Submission failed");
      setSuccess(data.message || "Request received.");
      e.currentTarget.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={(e) => void onSubmit(e)}
      className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-black/30 sm:p-6"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Full Name" name="fullName" required />
        <Field label="Company Name" name="company" required />
        <Field label="Work Email" name="email" type="email" required />
        <Field
          label="Role"
          name="role"
          placeholder="e.g. Controls Engineer, Systems Integrator"
          required
        />
      </div>

      <div>
        <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">
          Industry / Project Type
        </label>
        <select
          name="industry"
          required
          defaultValue=""
          className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 focus:ring-2"
        >
          <option value="" disabled>
            Select industry
          </option>
          {INDUSTRIES.map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </select>
      </div>

      <RadioGroup
        legend="Rockwell Studio 5000 used?"
        name="rockwellStudio"
        options={["Yes", "No"]}
      />
      <RadioGroup
        legend="Recent or upcoming PLC release?"
        name="upcomingRelease"
        options={["Yes", "No"]}
      />
      <RadioGroup
        legend="Sanitized or authorized artifacts available?"
        name="artifactsAvailable"
        options={["Yes", "No"]}
      />

      <div>
        <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">
          Optional Notes
        </label>
        <textarea
          name="notes"
          rows={3}
          className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 focus:ring-2"
          placeholder="Context on your release workflow, systems, or evaluation goals"
        />
      </div>

      {error && (
        <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}
      {success && (
        <p className="rounded-md border border-teal-500/30 bg-teal-500/10 px-3 py-2 text-sm text-teal-300">
          {success}
        </p>
      )}

      <button
        type="submit"
        disabled={loading}
        className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-60 sm:w-auto"
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Send className="h-4 w-4" />
        )}
        Request Technical Evaluation
      </button>
    </form>
  );
}

function Field({
  label,
  name,
  type = "text",
  required,
  placeholder,
}: {
  label: string;
  name: string;
  type?: string;
  required?: boolean;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </label>
      <input
        name={name}
        type={type}
        required={required}
        placeholder={placeholder}
        className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 focus:ring-2"
      />
    </div>
  );
}

function RadioGroup({
  legend,
  name,
  options,
}: {
  legend: string;
  name: string;
  options: string[];
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
        {legend}
      </legend>
      <div className="flex flex-wrap gap-4">
        {options.map((opt) => (
          <label
            key={opt}
            className="inline-flex cursor-pointer items-center gap-2 text-sm text-slate-200"
          >
            <input
              type="radio"
              name={name}
              value={opt}
              required
              className="border-slate-600 text-cyan-500 focus:ring-cyan-500"
            />
            {opt}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
