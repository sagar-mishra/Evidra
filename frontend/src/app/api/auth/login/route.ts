import { NextResponse } from "next/server";
import {
  USER_COOKIE,
  createSessionToken,
  sessionCookieOptions,
} from "@/lib/auth/session";
import { findUser } from "@/lib/auth/users-store";

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
      { error: "Username and password are required" },
      { status: 400 }
    );
  }

  try {
    const user = await findUser(username);
    if (!user || user.password !== password) {
      return NextResponse.json(
        { error: "Invalid username or password" },
        { status: 401 }
      );
    }

    const token = createSessionToken("user", user.username, user.role);
    const res = NextResponse.json({
      ok: true,
      username: user.username,
      role: user.role,
      redirectTo: "/dashboard",
    });
    res.cookies.set(USER_COOKIE, token, sessionCookieOptions(req));
    return res;
  } catch (err) {
    console.error("[auth/login] user store error", err);
    return NextResponse.json(
      {
        error:
          err instanceof Error
            ? `Login storage error: ${err.message}`
            : "Login storage error",
      },
      { status: 500 }
    );
  }
}
