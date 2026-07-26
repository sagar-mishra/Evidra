"use client";

import type { ReactNode } from "react";
import { ClassificationBadge } from "@/components/review/classification-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { normalizeClassification } from "@/lib/classifications";
import { useReviewStore } from "@/lib/store";
import type { LogicAnnotation, ReviewItem } from "@/lib/types";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Code2,
  FileText,
  GitCompareArrows,
  ListChecks,
  MapPin,
  XCircle,
  HelpCircle,
} from "lucide-react";

/**
 * Middle pane — behavioral evidence stack for YC demo accuracy layout.
 */
export function DiffPane({ item }: { item: ReviewItem }) {
  const plan = item.test_plan;
  const classification = normalizeClassification(item.classification);
  const confirmFinding = useReviewStore((s) => s.confirmFinding);
  const dismissFinding = useReviewStore((s) => s.dismissFinding);
  const needsInvestigation = useReviewStore((s) => s.needsInvestigation);

  const behavioralFields = [
    {
      key: "required_behavior",
      label: "1. Required behavior (SOO)",
      value: item.required_behavior,
    },
    {
      key: "verified_code_change",
      label: "2. Verified code change",
      value: item.verified_code_change,
    },
    {
      key: "predicted_revised_behavior",
      label: "3. Predicted revised behavior",
      value: item.predicted_revised_behavior,
    },
    {
      key: "test_pass_condition",
      label: "4. Test pass condition",
      value: item.test_pass_condition,
    },
    {
      key: "predicted_test_outcome",
      label: "5. Predicted test outcome",
      value: item.predicted_test_outcome,
    },
  ];

  return (
    <div className="box-border flex h-full min-h-0 flex-col gap-3 overflow-y-auto overflow-x-hidden px-4 pb-6 pt-6">
      <div className="flex flex-shrink-0 flex-wrap items-center gap-2">
        <GitCompareArrows className="h-4 w-4 text-slate-600" />
        <h3 className="text-sm font-semibold text-slate-900">
          Behavioral Evidence
        </h3>
        <ClassificationBadge classification={classification} />
        {(item.severity === "Critical" || item.severity === "High") && (
          <Badge
            variant="outline"
            className="border-red-300 bg-red-50 text-red-800"
          >
            {item.severity}
          </Badge>
        )}
        {item.uncertainty && (
          <Badge variant="outline" className="border-slate-300 text-slate-700">
            {item.uncertainty}
          </Badge>
        )}
      </div>

      {/* Disposition actions */}
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          className="bg-emerald-600 hover:bg-emerald-500"
          onClick={() => confirmFinding(item.id)}
        >
          <CheckCircle2 className="mr-1.5 h-4 w-4" />
          Confirm Finding
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="border-slate-300"
          onClick={() => dismissFinding(item.id)}
        >
          <XCircle className="mr-1.5 h-4 w-4" />
          Dismiss Finding
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="border-amber-300 text-amber-900"
          onClick={() => needsInvestigation(item.id)}
        >
          <HelpCircle className="mr-1.5 h-4 w-4" />
          Needs Investigation
        </Button>
      </div>

      {/* 5 behavioral fields */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <ListChecks className="h-4 w-4 text-slate-600" />
            Behavioral finding (5 fields)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {behavioralFields.map((f) => (
            <div key={f.key} className="rounded-md border border-slate-100 bg-slate-50/80 p-2.5">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                {f.label}
              </div>
              <p className="mt-1 text-sm leading-relaxed text-slate-900">
                {f.value || "—"}
              </p>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Requirement evidence */}
      <EvidenceBlock
        step={1}
        title="Requirement evidence"
        icon={<BookOpen className="h-3.5 w-3.5" />}
      >
        <dl className="grid grid-cols-1 gap-1.5 text-xs sm:grid-cols-2">
          <Meta label="Document" value={item.document_name || item.requirement_source} />
          <Meta label="Revision" value={item.document_revision || "—"} />
          <Meta label="Requirement ID" value={item.requirement_id} mono />
          <Meta
            label="Page"
            value={
              item.requirement_page && item.requirement_page > 0
                ? String(item.requirement_page)
                : item.soo_page_or_section
            }
          />
          <Meta
            label="Section"
            value={item.requirement_section || item.soo_page_or_section}
          />
        </dl>
        <p className="mt-2 rounded-md border border-slate-200 bg-white p-2 text-sm leading-relaxed text-slate-800">
          {item.requirement_text}
        </p>
      </EvidenceBlock>

      {/* Equipment details */}
      <EvidenceBlock
        step={2}
        title="Equipment details"
        icon={<MapPin className="h-3.5 w-3.5" />}
      >
        <dl className="grid grid-cols-1 gap-1.5 text-xs sm:grid-cols-2">
          <Meta
            label="Trigger equipment"
            value={(item.trigger_equipment || []).join(", ") || "—"}
          />
          <Meta
            label="Affected equipment"
            value={
              (item.affected_equipment || []).join(", ") ||
              item.equipment ||
              "—"
            }
          />
          <Meta
            label="Affected output"
            value={item.affected_output || item.tag_name || "—"}
            mono
          />
          <Meta label="System" value={item.system || "—"} />
          <Meta label="Routine" value={item.routine || item.location} mono />
          <Meta label="Rung" value={item.rung ?? "—"} mono />
        </dl>
      </EvidenceBlock>

      {/* Side-by-side logic comparison */}
      <EvidenceBlock
        step={3}
        title="Side-by-side logic comparison"
        icon={<Code2 className="h-3.5 w-3.5" />}
      >
        <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase text-emerald-800">
              Baseline
            </div>
            <LogicBlock
              text={item.baseline_evidence}
              annotations={item.logic_annotations}
              side="baseline"
            />
          </div>
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase text-amber-800">
              Revised
            </div>
            <LogicBlock
              text={item.revised_evidence}
              annotations={item.logic_annotations}
              side="revised"
            />
          </div>
        </div>
        {(item.logic_annotations?.length ?? 0) > 0 && (
          <ul className="mt-2 space-y-1 text-xs text-slate-700">
            {item.logic_annotations!.map((a, i) => (
              <li key={i} className="flex gap-2">
                <Badge
                  variant="outline"
                  className={
                    a.change === "added"
                      ? "border-amber-300 bg-amber-50 text-amber-900"
                      : "border-red-300 bg-red-50 text-red-900"
                  }
                >
                  {a.change}
                </Badge>
                <span>
                  <code className="font-mono text-[11px]">{a.token}</code>
                  {" — "}
                  {a.note}
                </span>
              </li>
            ))}
          </ul>
        )}
      </EvidenceBlock>

      {/* Why flagged */}
      <Card className="border-amber-200 bg-gradient-to-br from-amber-50 to-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm text-amber-950">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            Why this was flagged
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-slate-800">
            {plan.flag_rationale?.trim() ||
              item.predicted_revised_behavior ||
              "No flag rationale provided."}
          </p>
        </CardContent>
      </Card>

      {/* Expected result preview */}
      <EvidenceBlock
        step={4}
        title="Expected result (test)"
        icon={<FileText className="h-3.5 w-3.5" />}
      >
        <p className="text-sm text-slate-800">{plan.expected_result}</p>
      </EvidenceBlock>
    </div>
  );
}

function Meta({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="font-medium text-slate-500">{label}</dt>
      <dd className={mono ? "font-mono text-slate-900" : "text-slate-900"}>
        {value}
      </dd>
    </div>
  );
}

function LogicBlock({
  text,
  annotations,
  side,
}: {
  text: string;
  annotations?: LogicAnnotation[];
  side: "baseline" | "revised";
}) {
  const highlighted = highlightLogic(text, annotations || [], side);
  return (
    <pre
      className={
        side === "baseline"
          ? "overflow-x-auto whitespace-pre-wrap rounded-md border border-emerald-200 bg-emerald-50/70 p-2.5 font-mono text-[11px] leading-relaxed text-emerald-950"
          : "overflow-x-auto whitespace-pre-wrap rounded-md border border-amber-200 bg-amber-50/70 p-2.5 font-mono text-[11px] leading-relaxed text-amber-950"
      }
    >
      {highlighted}
    </pre>
  );
}

function highlightLogic(
  text: string,
  annotations: LogicAnnotation[],
  side: "baseline" | "revised"
): ReactNode {
  if (!annotations.length) return text;

  // Highlight tokens relevant to this side
  const tokens = annotations
    .filter((a) =>
      side === "revised" ? a.change === "added" : a.change === "removed"
    )
    .map((a) => a.token)
    .filter(Boolean);

  if (!tokens.length) return text;

  // Simple sequential split on first matching token
  let nodes: ReactNode[] = [text];
  for (const token of tokens) {
    const next: ReactNode[] = [];
    for (const node of nodes) {
      if (typeof node !== "string") {
        next.push(node);
        continue;
      }
      const parts = node.split(token);
      parts.forEach((part, i) => {
        if (part) next.push(part);
        if (i < parts.length - 1) {
          next.push(
            <mark
              key={`${token}-${i}`}
              className={
                side === "revised"
                  ? "rounded bg-amber-300/80 px-0.5 font-semibold text-amber-950"
                  : "rounded bg-red-300/70 px-0.5 font-semibold text-red-950 line-through"
              }
              title={
                annotations.find((a) => a.token === token)?.note || undefined
              }
            >
              {token}
            </mark>
          );
        }
      });
    }
    nodes = next;
  }
  return <>{nodes}</>;
}

function EvidenceBlock({
  step,
  title,
  icon,
  children,
  accent,
}: {
  step: number;
  title: string;
  icon: ReactNode;
  children: ReactNode;
  accent?: "emerald" | "amber";
}) {
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm text-slate-900">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-900 text-[10px] font-bold text-white">
            {step}
          </span>
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className={accent === "emerald" ? "" : ""}>{children}</CardContent>
    </Card>
  );
}
