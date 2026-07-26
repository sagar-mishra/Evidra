/**
 * Export utilities for the Evidra review package.
 * Generates CSV (traceability register) and PDF (review package).
 */

import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import Papa from "papaparse";
import type { ReviewItem } from "@/lib/types";

export interface ExportPackageMeta {
  projectName?: string;
  controller?: string;
  baseline?: string;
  revised?: string;
  soo?: string;
  exportedAt?: string;
  engineer?: string;
}

const DEFAULT_META = {
  projectName: "DC1 Cooling System",
  controller: "DC1_MEP_PLC01",
  baseline: "DC1_Cooling_Baseline_RevA.L5X",
  revised: "DC1_Cooling_Revised_RevB.L5X",
  soo: "DC1_Cooling_SOO_RevB",
};

const PRODUCT_NAME = "Evidra";
const PRODUCT_TAGLINE = "Every change, proven before production.";

function metaDefaults(meta?: ExportPackageMeta) {
  return {
    projectName: meta?.projectName ?? DEFAULT_META.projectName,
    controller: meta?.controller ?? DEFAULT_META.controller,
    baseline: meta?.baseline ?? DEFAULT_META.baseline,
    revised: meta?.revised ?? DEFAULT_META.revised,
    soo: meta?.soo ?? DEFAULT_META.soo,
    exportedAt: meta?.exportedAt ?? new Date().toISOString(),
    engineer: meta?.engineer ?? "Lead Controls Engineer (reviewer)",
  };
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

/** Flatten review items into CSV rows for the traceability register. */
export function buildCsvRows(items: ReviewItem[]) {
  return items.map((item) => ({
    review_id: item.id,
    status: item.status,
    classification: item.classification,
    severity: item.severity,
    change_class: item.change_class,
    location: item.location,
    equipment: item.equipment ?? "",
    tag_name: item.tag_name ?? "",
    baseline_evidence: item.baseline_evidence,
    revised_evidence: item.revised_evidence,
    requirement_id: item.requirement_id,
    requirement_text: item.requirement_text,
    requirement_source: item.requirement_source,
    test_id: item.test_plan.test_id,
    test_title: item.test_plan.title,
    prerequisites: item.test_plan.prerequisites.join(" | "),
    test_steps: item.test_plan.test_steps
      .map((s) => `${s.step_number}. ${s.action}`)
      .join(" || "),
    expected_result: item.test_plan.expected_result,
    reviewer_notes: item.reviewer_notes,
    updated_at: item.updated_at,
  }));
}

/** Download the CSV export package. */
export function exportCsv(
  items: ReviewItem[],
  filename = "evidra_traceability.csv"
): void {
  const csv = Papa.unparse(buildCsvRows(items));
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  downloadBlob(filename, blob);
}

/**
 * Load /logo.png as a data URL for embedding in jsPDF (browser only).
 */
async function loadLogoDataUrl(): Promise<string | null> {
  try {
    const res = await fetch("/logo.png");
    if (!res.ok) return null;
    const blob = await res.blob();
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

/** Download the PDF review package (async so logo can be embedded). */
export async function exportPdf(
  items: ReviewItem[],
  meta?: ExportPackageMeta,
  filename = "evidra_package.pdf"
): Promise<void> {
  const m = metaDefaults(meta);
  const doc = new jsPDF({ unit: "pt", format: "letter" });
  const margin = 40;
  let y = margin;

  const logoDataUrl = await loadLogoDataUrl();
  if (logoDataUrl) {
    try {
      // PNG logo in header — keep modest height for letter layout
      const logoW = 110;
      const logoH = 36;
      doc.addImage(logoDataUrl, "PNG", margin, y - 8, logoW, logoH);
      y += logoH + 10;
    } catch {
      // Fall through to text title if image embed fails
      doc.setFont("helvetica", "bold");
      doc.setFontSize(16);
      doc.text(PRODUCT_NAME, margin, y);
      y += 22;
    }
  } else {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(16);
    doc.text(PRODUCT_NAME, margin, y);
    y += 22;
  }

  const addTitle = (text: string, size = 14) => {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(size);
    doc.text(text, margin, y);
    y += size + 8;
  };

  const addLine = (text: string, size = 10) => {
    doc.setFont("helvetica", "normal");
    doc.setFontSize(size);
    const lines = doc.splitTextToSize(text, 532);
    doc.text(lines, margin, y);
    y += lines.length * (size + 3) + 4;
  };

  // Text product name under logo for accessibility / plain-text PDF readers
  addTitle(PRODUCT_NAME, 14);
  addLine(PRODUCT_TAGLINE);
  y += 4;
  addLine(`Project: ${m.projectName}`);
  addLine(`Controller: ${m.controller}`);
  addLine(`Baseline: ${m.baseline}`);
  addLine(`Revised: ${m.revised}`);
  addLine(`Governing SOO/FDS: ${m.soo}`);
  addLine(`Exported: ${m.exportedAt}`);
  addLine(`Reviewer: ${m.engineer}`);
  y += 6;
  addLine(
    `NOTICE: This ${PRODUCT_NAME} package is a human-reviewed, read-only audit aid. It does not approve a release. A qualified controls engineer must explicitly confirm or dismiss each finding.`
  );
  y += 10;

  const counts = {
    total: items.length,
    accepted: items.filter((i) => i.status === "Accepted").length,
    rejected: items.filter((i) => i.status === "Rejected").length,
    edited: items.filter((i) => i.status === "Edited").length,
    unresolved: items.filter(
      (i) => i.status === "Unresolved" || i.status === "Needs Investigation"
    ).length,
    pending: items.filter((i) => i.status === "Pending").length,
  };

  addTitle("Review Summary", 12);
  autoTable(doc, {
    startY: y,
    head: [["Total", "Pending", "Accepted", "Rejected", "Edited", "Unresolved"]],
    body: [
      [
        String(counts.total),
        String(counts.pending),
        String(counts.accepted),
        String(counts.rejected),
        String(counts.edited),
        String(counts.unresolved),
      ],
    ],
    margin: { left: margin, right: margin },
    styles: { fontSize: 9 },
  });
  const lastTable = (doc as unknown as { lastAutoTable?: { finalY: number } })
    .lastAutoTable;
  y = lastTable?.finalY != null ? lastTable.finalY + 16 : y + 40;

  for (const item of items) {
    if (y > 700) {
      doc.addPage();
      y = margin;
    }
    addTitle(`${item.id} — ${item.test_plan.title}`, 13);
    addLine(`Status: ${item.status}`);
    addLine(`Classification: ${item.classification}`);
    addLine(`Severity: ${item.severity}`);
    addLine(`Location: ${item.location}`);
    addLine(`Baseline: ${item.baseline_evidence}`);
    addLine(`Revised: ${item.revised_evidence}`);
    addLine(`Requirement: ${item.requirement_id} — ${item.requirement_text}`);
    addLine(`Citation: ${item.soo_page_or_section}`);
    if (item.required_behavior) {
      addLine(`Required behavior: ${item.required_behavior}`);
    }
    if (item.verified_code_change) {
      addLine(`Verified code change: ${item.verified_code_change}`);
    }
    if (item.predicted_revised_behavior) {
      addLine(`Predicted revised behavior: ${item.predicted_revised_behavior}`);
    }
    if (item.test_pass_condition) {
      addLine(`Test pass condition: ${item.test_pass_condition}`);
    }
    if (item.predicted_test_outcome) {
      addLine(`Predicted test outcome: ${item.predicted_test_outcome}`);
    }
    addLine(`Test ID: ${item.test_plan.test_id}`);
    addLine(`Purpose: ${item.test_plan.purpose}`);
    addLine(`Change: ${item.test_plan.change_summary}`);
    addLine(
      `Equipment: ${(item.test_plan.affected_equipment || []).join(", ") || "—"}`
    );
    addLine(
      `Prerequisites: ${(item.test_plan.prerequisites || []).join("; ")}`
    );
    addLine(
      `Steps: ${(item.test_plan.test_steps || [])
        .map((s) => `${s.step_number}. ${s.action}`)
        .join(" | ")}`
    );
    addLine(`Expected result: ${item.test_plan.expected_result}`);
    if (item.reviewer_notes) {
      y += 4;
      addTitle("Reviewer Notes", 11);
      addLine(item.reviewer_notes);
    }
  }

  doc.save(filename);
}

/** Export both CSV and PDF packages. */
export function exportPackage(items: ReviewItem[], meta?: ExportPackageMeta): void {
  const stamp = new Date().toISOString().slice(0, 10);
  exportCsv(items, `evidra_traceability_${stamp}.csv`);
  void exportPdf(items, meta, `evidra_package_${stamp}.pdf`);
}
