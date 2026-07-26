import { NextResponse } from "next/server";
import { readAdminSession } from "@/lib/auth/session";
import { deleteUser, updateUser, type AppUserRole } from "@/lib/auth/users-store";

function requireAdmin() {
  const session = readAdminSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return null;
}

export async function DELETE(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const denied = requireAdmin();
  if (denied) return denied;
  try {
    const ok = await deleteUser(params.id);
    if (!ok) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }
    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Delete failed" },
      { status: 500 }
    );
  }
}

export async function PATCH(
  req: Request,
  { params }: { params: { id: string } }
) {
  const denied = requireAdmin();
  if (denied) return denied;

  let body: { username?: string; password?: string; role?: AppUserRole };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  try {
    const user = await updateUser(params.id, body);
    if (!user) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }
    return NextResponse.json({ user });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Update failed" },
      { status: 400 }
    );
  }
}
