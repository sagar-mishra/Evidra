/**
 * Cookie-based session helpers for user + admin auth (demo-grade).
 */

import { cookies } from "next/headers";

export const USER_COOKIE = "evidra_user_session";
export const ADMIN_COOKIE = "evidra_admin_session";

export type SessionKind = "user" | "admin";

export interface SessionPayload {
  kind: SessionKind;
  username: string;
  role?: string;
  exp: number;
}

const TTL_MS = 1000 * 60 * 60 * 12; // 12 hours

function encode(payload: SessionPayload): string {
  return Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
}

function decode(raw: string | undefined): SessionPayload | null {
  if (!raw) return null;
  try {
    // Next may URL-encode cookie values; normalize first
    const value = decodeURIComponent(raw);
    const json = Buffer.from(value, "base64url").toString("utf8");
    const data = JSON.parse(json) as SessionPayload;
    if (!data?.username || !data?.kind || !data?.exp) return null;
    if (Date.now() > data.exp) return null;
    return data;
  } catch {
    try {
      // Fallback if value was not URI-encoded
      const json = Buffer.from(raw, "base64url").toString("utf8");
      const data = JSON.parse(json) as SessionPayload;
      if (!data?.username || !data?.kind || !data?.exp) return null;
      if (Date.now() > data.exp) return null;
      return data;
    } catch {
      return null;
    }
  }
}

export function createSessionToken(
  kind: SessionKind,
  username: string,
  role?: string
): string {
  return encode({
    kind,
    username,
    role,
    exp: Date.now() + TTL_MS,
  });
}

export function readUserSession(): SessionPayload | null {
  const jar = cookies();
  const data = decode(jar.get(USER_COOKIE)?.value);
  return data?.kind === "user" ? data : null;
}

export function readAdminSession(): SessionPayload | null {
  const jar = cookies();
  const data = decode(jar.get(ADMIN_COOKIE)?.value);
  return data?.kind === "admin" ? data : null;
}

/**
 * Cookie options for Set-Cookie.
 * Avoid secure=true on plain HTTP (local / some demos) — browsers will drop the cookie
 * and login appears to "do nothing".
 */
export function sessionCookieOptions(req?: Request, maxAgeSec = 60 * 60 * 12) {
  const forwarded = req?.headers.get("x-forwarded-proto") || "";
  const host = req?.headers.get("host") || "";
  const isHttps =
    process.env.COOKIE_SECURE === "true" ||
    forwarded.split(",")[0]?.trim() === "https" ||
    // Never force secure on localhost / 127.0.0.1
    (process.env.NODE_ENV === "production" &&
      !host.includes("localhost") &&
      !host.startsWith("127.0.0.1") &&
      forwarded !== "http");

  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: Boolean(isHttps),
    path: "/",
    maxAge: maxAgeSec,
  };
}

export function getAdminCredentials(): { username: string; password: string } {
  return {
    username: (process.env.ADMIN_USERNAME || "admin").trim(),
    password: process.env.ADMIN_PASSWORD || "admin",
  };
}
