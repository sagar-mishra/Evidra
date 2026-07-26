import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const USER_COOKIE = "evidra_user_session";
const ADMIN_COOKIE = "evidra_admin_session";

/** Edge-safe base64url → UTF-8 (avoid Node Buffer in middleware). */
function decodeBase64Url(raw: string): string {
  try {
    const base64 = raw.replace(/-/g, "+").replace(/_/g, "/");
    const pad =
      base64.length % 4 === 0 ? "" : "=".repeat(4 - (base64.length % 4));
    const binary = atob(base64 + pad);
    // Prefer TextDecoder when available (Edge)
    if (typeof TextDecoder !== "undefined") {
      const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
      return new TextDecoder().decode(bytes);
    }
    return binary;
  } catch {
    return "";
  }
}

function isValidSession(
  raw: string | undefined,
  kind: "user" | "admin"
): boolean {
  if (!raw || !raw.trim()) return false;
  try {
    // Cookie values may arrive URL-encoded from the browser
    let token = raw.trim();
    try {
      token = decodeURIComponent(token);
    } catch {
      /* keep raw */
    }
    const json = decodeBase64Url(token);
    if (!json) return false;
    const data = JSON.parse(json) as { kind?: string; exp?: number };
    if (data.kind !== kind) return false;
    if (typeof data.exp !== "number" || Date.now() > data.exp) return false;
    return true;
  } catch {
    return false;
  }
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Protect product workspace
  if (pathname === "/dashboard" || pathname.startsWith("/dashboard/")) {
    const ok = isValidSession(req.cookies.get(USER_COOKIE)?.value, "user");
    if (!ok) {
      const url = req.nextUrl.clone();
      url.pathname = "/login";
      url.searchParams.set("next", pathname);
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  // Protect admin area
  if (
    pathname === "/admin/dashboard" ||
    pathname.startsWith("/admin/dashboard/")
  ) {
    const ok = isValidSession(req.cookies.get(ADMIN_COOKIE)?.value, "admin");
    if (!ok) {
      const url = req.nextUrl.clone();
      url.pathname = "/admin/login";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  // Explicit matchers so bare /dashboard is always covered
  matcher: [
    "/dashboard",
    "/dashboard/:path*",
    "/admin/dashboard",
    "/admin/dashboard/:path*",
  ],
};
