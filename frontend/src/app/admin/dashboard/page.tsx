"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  Loader2,
  LogOut,
  Plus,
  Shield,
  Trash2,
  UserCog,
} from "lucide-react";

interface SafeUser {
  id: string;
  username: string;
  role: string;
  createdAt: string;
}

interface StorageInfo {
  mode: string;
  detail: string;
}

export default function AdminDashboardPage() {
  const router = useRouter();
  const [users, setUsers] = useState<SafeUser[]>([]);
  const [storage, setStorage] = useState<StorageInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("engineer");

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/users");
      if (res.status === 401) {
        router.replace("/admin/login");
        return;
      }
      const data = (await res.json()) as {
        users?: SafeUser[];
        storage?: StorageInfo;
        error?: string;
      };
      if (!res.ok) throw new Error(data.error || "Failed to load users");
      setUsers(data.users || []);
      setStorage(data.storage || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setFormError(null);
    try {
      const res = await fetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, role }),
      });
      const data = (await res.json()) as { error?: string };
      if (!res.ok) throw new Error(data.error || "Create failed");
      setUsername("");
      setPassword("");
      setRole("engineer");
      await loadUsers();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setCreating(false);
    }
  };

  const onDelete = async (id: string) => {
    if (!confirm("Delete this user?")) return;
    const res = await fetch(`/api/users/${id}`, { method: "DELETE" });
    if (res.ok) await loadUsers();
  };

  const signOut = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/admin/login");
    router.refresh();
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/80">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo.png" alt="Evidra Logo" className="h-8 w-auto" />
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-white">Evidra</span>
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
                  <Shield className="h-3 w-3" />
                  Admin
                </span>
              </div>
              <p className="text-[11px] text-slate-500">User management</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
            >
              Home
            </Link>
            <button
              type="button"
              onClick={() => void signOut()}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
            >
              <LogOut className="h-3.5 w-3.5" />
              Sign Out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-8 px-4 py-8 sm:px-6">
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
          <div className="mb-4 flex items-center gap-2">
            <Plus className="h-5 w-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">Add New User</h2>
          </div>
          <form
            onSubmit={(e) => void onCreate(e)}
            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
          >
            <div>
              <label className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400">
                New Username
              </label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-500/40 focus:ring-2"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400">
                New Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-500/40 focus:ring-2"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400">
                Role
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-500/40 focus:ring-2"
              >
                <option value="engineer">Engineer</option>
                <option value="reviewer">Reviewer</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={creating}
                className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-60"
              >
                {creating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <UserCog className="h-4 w-4" />
                )}
                Create user
              </button>
            </div>
          </form>
          {formError && (
            <p className="mt-3 text-sm text-red-300">{formError}</p>
          )}
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
            <h2 className="text-lg font-semibold text-white">Users</h2>
            {storage && (
              <p className="font-mono text-[10px] text-slate-500">
                Store: {storage.mode} → {storage.detail}
              </p>
            )}
          </div>
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading users…
            </div>
          ) : error ? (
            <p className="text-sm text-red-300">{error}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-[11px] uppercase tracking-wide text-slate-500">
                    <th className="px-2 py-2 font-medium">Username</th>
                    <th className="px-2 py-2 font-medium">Role</th>
                    <th className="px-2 py-2 font-medium">Created</th>
                    <th className="px-2 py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr
                      key={u.id}
                      className="border-b border-slate-800/80 text-slate-200"
                    >
                      <td className="px-2 py-2.5 font-mono text-xs">{u.username}</td>
                      <td className="px-2 py-2.5 capitalize">{u.role}</td>
                      <td className="px-2 py-2.5 text-xs text-slate-400">
                        {new Date(u.createdAt).toLocaleString()}
                      </td>
                      <td className="px-2 py-2.5">
                        <button
                          type="button"
                          onClick={() => void onDelete(u.id)}
                          className="inline-flex items-center gap-1 rounded border border-red-500/30 px-2 py-1 text-xs text-red-300 hover:bg-red-500/10"
                        >
                          <Trash2 className="h-3 w-3" />
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr>
                      <td
                        colSpan={4}
                        className="px-2 py-6 text-center text-slate-500"
                      >
                        No users yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
