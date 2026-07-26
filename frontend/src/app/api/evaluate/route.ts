import { NextResponse } from "next/server";

/**
 * Evaluation request intake — logs payload for demo; swap for CRM/email later.
 */
export async function POST(req: Request) {
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const required = ["fullName", "company", "email", "role", "industry"];
  for (const key of required) {
    if (!body[key] || String(body[key]).trim() === "") {
      return NextResponse.json(
        { error: `Missing required field: ${key}` },
        { status: 400 }
      );
    }
  }

  // Demo persistence: console + in-memory ring buffer
  const store = globalThis as unknown as { __evidraLeads?: unknown[] };
  if (!store.__evidraLeads) store.__evidraLeads = [];
  const lead = { ...body, receivedAt: new Date().toISOString() };
  store.__evidraLeads.unshift(lead);
  if (store.__evidraLeads.length > 200) store.__evidraLeads.pop();
  console.info("[Evidra evaluation request]", lead);

  return NextResponse.json({
    ok: true,
    message: "Thank you. We will follow up on your technical evaluation request.",
  });
}
