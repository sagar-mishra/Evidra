"use client";

import { ClassificationBadge } from "@/components/review/classification-badge";
import { StatusBadge } from "@/components/review/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { normalizeClassification } from "@/lib/classifications";
import { useReviewStore } from "@/lib/store";
import type { ReviewItem } from "@/lib/types";
import {
  Check,
  ClipboardList,
  RotateCcw,
  TriangleAlert,
  X,
} from "lucide-react";

/**
 * Right pane — strict regression test schema only:
 * Test Title, Prerequisites (bullets), Test Steps (numbered), Expected Result.
 */
export function TestPlanPane({ item }: { item: ReviewItem }) {
  const confirmFinding = useReviewStore((s) => s.confirmFinding);
  const dismissFinding = useReviewStore((s) => s.dismissFinding);
  const needsInvestigation = useReviewStore((s) => s.needsInvestigation);
  const updateTestPlan = useReviewStore((s) => s.updateTestPlan);
  const updateReviewerNotes = useReviewStore((s) => s.updateReviewerNotes);
  const resetItem = useReviewStore((s) => s.resetItem);

  const plan = item.test_plan;
  const classification = normalizeClassification(item.classification);

  const prerequisites = plan.prerequisites?.length
    ? plan.prerequisites
    : [
        "Run in simulation or an approved FAT environment — do not test on a live field PLC.",
      ];

  const steps = (plan.test_steps || [])
    .map((s) => s.action)
    .filter((a) => a && a.trim());

  const patchPrerequisites = (text: string) => {
    updateTestPlan(item.id, {
      ...plan,
      prerequisites: text
        .split("\n")
        .map((line) => line.replace(/^[-•*]\s*/, "").trim())
        .filter(Boolean),
    });
  };

  const patchSteps = (text: string) => {
    const lines = text
      .split("\n")
      .map((line) => line.replace(/^\d+[.)]\s*/, "").trim())
      .filter(Boolean);
    updateTestPlan(item.id, {
      ...plan,
      test_steps: lines.map((action, i) => ({
        step_number: i + 1,
        action,
        observation: null,
      })),
    });
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <ClipboardList className="h-4 w-4 text-slate-600" />
          <h3 className="text-sm font-semibold text-slate-900">
            Regression Test Plan
          </h3>
          <ClassificationBadge classification={classification} />
          <StatusBadge status={item.status} />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            className="border-emerald-300 text-emerald-800 hover:bg-emerald-50"
            onClick={() => confirmFinding(item.id)}
          >
            <Check className="mr-1 h-4 w-4" />
            Confirm Finding
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="border-red-300 text-red-800 hover:bg-red-50"
            onClick={() => dismissFinding(item.id)}
          >
            <X className="mr-1 h-4 w-4" />
            Dismiss Finding
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="border-violet-300 text-violet-800 hover:bg-violet-50"
            onClick={() => needsInvestigation(item.id)}
          >
            <TriangleAlert className="mr-1 h-4 w-4" />
            Needs Investigation
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => resetItem(item.id)}
            title="Reset to original draft"
          >
            <RotateCcw className="mr-1 h-4 w-4" />
            Reset
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-auto p-4 pt-5">
        {/* Test Title */}
        <Card className="shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Test title
            </CardTitle>
          </CardHeader>
          <CardContent>
            <input
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-900 outline-none ring-slate-900 focus:ring-2"
              value={plan.title}
              onChange={(e) =>
                updateTestPlan(item.id, { ...plan, title: e.target.value })
              }
            />
            {plan.test_id && (
              <p className="mt-1.5 font-mono text-[11px] text-slate-500">
                {plan.test_id}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Prerequisites — bulleted list */}
        <Card className="shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Prerequisites
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-slate-800">
              {prerequisites.map((p, i) => (
                <li key={`${i}-${p.slice(0, 24)}`}>{p}</li>
              ))}
            </ul>
            <Textarea
              rows={3}
              className="text-xs text-slate-600"
              value={prerequisites.join("\n")}
              onChange={(e) => patchPrerequisites(e.target.value)}
              placeholder="One prerequisite per line (simulation / FAT environment required)"
            />
          </CardContent>
        </Card>

        {/* Test Steps — numbered list */}
        <Card className="shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Test steps
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ol className="list-decimal space-y-2 pl-5 text-sm leading-relaxed text-slate-800">
              {steps.length > 0 ? (
                steps.map((step, i) => (
                  <li key={`${i}-${step.slice(0, 24)}`}>{step}</li>
                ))
              ) : (
                <li className="list-none text-slate-500">No steps defined.</li>
              )}
            </ol>
            <Textarea
              rows={5}
              className="text-xs text-slate-600"
              value={steps.join("\n")}
              onChange={(e) => patchSteps(e.target.value)}
              placeholder="One step per line"
            />
          </CardContent>
        </Card>

        {/* Expected Result */}
        <Card className="border-emerald-100 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Expected result
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              rows={4}
              className="border-emerald-200 bg-emerald-50/40 text-sm leading-relaxed text-slate-800"
              value={plan.expected_result}
              onChange={(e) =>
                updateTestPlan(item.id, {
                  ...plan,
                  expected_result: e.target.value,
                })
              }
            />
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Reviewer notes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              rows={3}
              value={item.reviewer_notes}
              onChange={(e) => updateReviewerNotes(item.id, e.target.value)}
              placeholder="Optional notes for the export package"
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
