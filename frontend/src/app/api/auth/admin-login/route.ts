import { NextResponse } from "next/server";
import {
  ADMIN_COOKIE,
  createSessionToken,
  getAdminCredentials,
  sessionCookieOptions,
} from "@/lib/auth/session";

export async function POST(req: Request) {
  let body: { username?: string; password?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const username = (body.username || "").trim();
  const password = body.password || "";
  if (!username || !password) {
    return NextResponse.json(
      { error: "Admin username and password are required" },
      { status: 400 }
    );
  }

  const admin = getAdminCredentials();
  if (username !== admin.username || password !== admin.password) {
    return NextResponse.json(
      { error: "Invalid admin credentials" },
      { status: 401 }
    );
  }

  const token = createSessionToken("admin", username, "admin");
  const res = NextResponse.json({
    ok: true,
    username,
    role: "admin",
    redirectTo: "/admin/dashboard",
  });
  res.cookies.set(ADMIN_COOKIE, token, sessionCookieOptions(req));
  return res;
}
