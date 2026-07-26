import { NextResponse } from "next/server";
import { readAdminSession } from "@/lib/auth/session";
import {
  createUser,
  getUsersStorageInfo,
  listUsers,
  type AppUserRole,
} from "@/lib/auth/users-store";

function requireAdmin() {
  const session = readAdminSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return null;
}

export async function GET() {
  const denied = requireAdmin();
  if (denied) return denied;
  try {
    const users = await listUsers();
    return NextResponse.json({
      users,
      storage: getUsersStorageInfo(),
    });
  } catch (err) {
    return NextResponse.json(
      {
        error:
          err instanceof Error ? err.message : "Failed to load users",
      },
      { status: 500 }
    );
  }
}

export async function POST(req: Request) {
  const denied = requireAdmin();
  if (denied) return denied;

  let body: { username?: string; password?: string; role?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const role = (body.role || "engineer") as AppUserRole;
  if (!["engineer", "reviewer", "viewer"].includes(role)) {
    return NextResponse.json({ error: "Invalid role" }, { status: 400 });
  }

  try {
    const user = await createUser({
      username: body.username || "",
      password: body.password || "",
      role,
    });
    return NextResponse.json({ user }, { status: 201 });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Create failed" },
      { status: 400 }
    );
  }
}
