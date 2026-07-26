"use client";

import {
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useReviewStore } from "@/lib/store";
import {
  FileCode2,
  FileText,
  FolderOpen,
  Loader2,
  Play,
} from "lucide-react";

/**
 * Upload Baseline L5X, Revised L5X, and multi governing docs, then run analysis.
 */
export function UploadModal() {
  const runAnalysis = useReviewStore((s) => s.runAnalysis);
  const analyzing = useReviewStore((s) => s.analyzing);
  const analysisStage = useReviewStore((s) => s.analysisStage);
  const error = useReviewStore((s) => s.error);
  const loadMockFindings = useReviewStore((s) => s.loadMockFindings);

  const [baseline, setBaseline] = useState<File | null>(null);
  const [revised, setRevised] = useState<File | null>(null);
  const [governingDocs, setGoverningDocs] = useState<File[]>([]);
  const [localError, setLocalError] = useState<string | null>(null);

  const baselineRef = useRef<HTMLInputElement>(null);
  const revisedRef = useRef<HTMLInputElement>(null);
  const docsRef = useRef<HTMLInputElement>(null);

  const ready =
    Boolean(baseline && revised && governingDocs.length > 0) && !analyzing;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (!baseline || !revised || governingDocs.length === 0) {
      setLocalError(
        "Select baseline L5X, revised L5X, and at least one governing document."
      );
      return;
    }
    try {
      await runAnalysis({
        baseline_l5x: baseline,
        revised_l5x: revised,
        governing_docs: governingDocs,
        soo_pdf: governingDocs[0],
      });
    } catch {
      // store.error is set by runAnalysis
    }
  };

  return (
    <div className="flex min-h-0 flex-1 items-center justify-center bg-slate-100 p-6">
      <Card className="w-full max-w-xl border-slate-200 shadow-lg">
        <CardHeader className="space-y-2 border-b border-slate-100 bg-slate-900 text-slate-50 rounded-t-xl">
          <div className="flex flex-wrap items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/logo.png"
              alt="Evidra Logo"
              className="h-10 w-auto object-contain"
            />
            <CardTitle className="text-xl font-bold tracking-tight text-white">
              Evidra
            </CardTitle>
            <span className="text-slate-600" aria-hidden>
              |
            </span>
            <p className="text-xs leading-relaxed text-slate-300 sm:text-sm">
              Every change, proven before production.
            </p>
          </div>
          <p className="text-xs leading-relaxed text-slate-400">
            Upload baseline and revised PLC exports plus governing documents
            (SOO / FDS / IO / alarms — PDF, Word, or Excel).
          </p>
        </CardHeader>

        <CardContent className="space-y-5 p-6">
          {analyzing ? (
            <div className="space-y-4 py-6 text-center">
              <Loader2 className="mx-auto h-10 w-10 animate-spin text-slate-700" />
              <div>
                <p className="text-sm font-semibold text-slate-900">
                  Reviewing project files…
                </p>
                <p className="mt-2 text-sm text-slate-600">
                  {analysisStage || "Starting…"}
                </p>
              </div>
              <ul className="mx-auto max-w-sm space-y-1 text-left text-xs text-slate-500">
                <li>• Comparing current and proposed PLC programs</li>
                <li>• Ingesting governing documents (PDF / Excel / DOCX)</li>
                <li>• Building curated behavioral findings</li>
              </ul>
            </div>
          ) : (
            <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
              <FileField
                label="Current PLC program"
                hint="Approved export (.L5X)"
                icon={<FileCode2 className="h-4 w-4" />}
                accept=".l5x,.xml,.L5X"
                file={baseline}
                inputRef={baselineRef}
                onChange={(f) => setBaseline(f)}
              />
              <FileField
                label="Proposed revision"
                hint="Revised export with changes (.L5X)"
                icon={<FileCode2 className="h-4 w-4" />}
                accept=".l5x,.xml,.L5X"
                file={revised}
                inputRef={revisedRef}
                onChange={(f) => setRevised(f)}
              />
              <MultiFileField
                label="Governing documents"
                hint="SOO / FDS / IO / alarms (PDF, DOCX, XLSX, CSV) — multi-select"
                icon={<FileText className="h-4 w-4" />}
                accept=".pdf,.docx,.xlsx,.xls,.csv,.PDF,.DOCX,.XLSX,.CSV"
                files={governingDocs}
                inputRef={docsRef}
                onChange={setGoverningDocs}
              />

              {(localError || error) && (
                <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
                  {localError || error}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2 pt-2">
                <Button type="submit" disabled={!ready} className="gap-1.5">
                  <Play className="h-4 w-4" />
                  Run Analysis
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="gap-1.5"
                  onClick={() => void loadMockFindings()}
                >
                  <FolderOpen className="h-4 w-4" />
                  Load sample review
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function FileField({
  label,
  hint,
  icon,
  accept,
  file,
  inputRef,
  onChange,
}: {
  label: string;
  hint: string;
  icon: ReactNode;
  accept: string;
  file: File | null;
  inputRef: RefObject<HTMLInputElement | null>;
  onChange: (f: File | null) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="flex items-center gap-1.5 text-sm text-slate-800">
        {icon}
        {label}
      </Label>
      <p className="text-[11px] text-slate-500">{hint}</p>
      <input
        ref={inputRef as RefObject<HTMLInputElement>}
        type="file"
        accept={accept}
        className="block w-full text-xs text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white hover:file:bg-slate-800"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
      {file && (
        <p className="truncate font-mono text-[11px] text-emerald-700">
          {file.name} ({Math.round(file.size / 1024)} KB)
        </p>
      )}
    </div>
  );
}

function MultiFileField({
  label,
  hint,
  icon,
  accept,
  files,
  inputRef,
  onChange,
}: {
  label: string;
  hint: string;
  icon: ReactNode;
  accept: string;
  files: File[];
  inputRef: RefObject<HTMLInputElement | null>;
  onChange: (f: File[]) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="flex items-center gap-1.5 text-sm text-slate-800">
        {icon}
        {label}
      </Label>
      <p className="text-[11px] text-slate-500">{hint}</p>
      <input
        ref={inputRef as RefObject<HTMLInputElement>}
        type="file"
        multiple
        accept={accept}
        className="block w-full text-xs text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white hover:file:bg-slate-800"
        onChange={(e) => onChange(Array.from(e.target.files || []))}
      />
      {files.length > 0 && (
        <ul className="space-y-0.5">
          {files.map((f) => (
            <li
              key={f.name + f.size}
              className="truncate font-mono text-[11px] text-emerald-700"
            >
              {f.name} ({Math.round(f.size / 1024)} KB)
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
