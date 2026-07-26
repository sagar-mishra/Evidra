import { NextResponse } from "next/server";
import { ADMIN_COOKIE, USER_COOKIE } from "@/lib/auth/session";

export async function POST() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(USER_COOKIE, "", { path: "/", maxAge: 0 });
  res.cookies.set(ADMIN_COOKIE, "", { path: "/", maxAge: 0 });
  return res;
}
