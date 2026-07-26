import { NextResponse } from "next/server";
import { readAdminSession, readUserSession } from "@/lib/auth/session";

/**
 * Prefer user session for product workspace checks.
 * (Previously admin was checked first, which blocked /dashboard after admin tests.)
 */
export async function GET() {
  const user = readUserSession();
  if (user) {
    return NextResponse.json({
      authenticated: true,
      kind: "user",
      username: user.username,
      role: user.role || "engineer",
    });
  }

  const admin = readAdminSession();
  if (admin) {
    return NextResponse.json({
      authenticated: true,
      kind: "admin",
      username: admin.username,
      role: "admin",
    });
  }

  return NextResponse.json({ authenticated: false }, { status: 401 });
}
