/**
 * User login credentials — shared CSV store.
 *
 * Local (default):
 *   frontend/data/users.csv  (or USERS_CSV_PATH)
 *
 * Deployed (shared across restarts / replicas):
 *   Same logical CSV in Azure Blob Storage when
 *   AZURE_STORAGE_CONNECTION_STRING is set.
 *   Container: USERS_CSV_CONTAINER (default evidra-auth)
 *   Blob:      USERS_CSV_BLOB (default users.csv)
 *
 * No default app users — admin creates all logins.
 * Admin credentials remain env ADMIN_USERNAME / ADMIN_PASSWORD.
 */

import fs from "fs";
import path from "path";
import {
  BlobServiceClient,
  type ContainerClient,
} from "@azure/storage-blob";

export type AppUserRole = "engineer" | "reviewer" | "viewer";

export interface AppUser {
  id: string;
  username: string;
  /** Plaintext for demo only — hash in production */
  password: string;
  role: AppUserRole;
  createdAt: string;
}

const CSV_HEADER = "id,username,password,role,createdAt";

// ---------------------------------------------------------------------------
// Path / blob config
// ---------------------------------------------------------------------------

function localCsvPath(): string {
  if (process.env.USERS_CSV_PATH?.trim()) {
    return path.resolve(process.env.USERS_CSV_PATH.trim());
  }
  // Docker production image uses WORKDIR /app
  if (
    process.env.NODE_ENV === "production" ||
    process.env.RUNNING_IN_CONTAINER === "true"
  ) {
    return "/app/data/users.csv";
  }
  return path.join(process.cwd(), "data", "users.csv");
}

function isAzureBlobEnabled(): boolean {
  return Boolean(process.env.AZURE_STORAGE_CONNECTION_STRING?.trim());
}

function blobContainerName(): string {
  return (process.env.USERS_CSV_CONTAINER || "evidra-auth").trim();
}

function blobName(): string {
  return (process.env.USERS_CSV_BLOB || "users.csv").trim();
}

async function getContainerClient(): Promise<ContainerClient> {
  const conn = process.env.AZURE_STORAGE_CONNECTION_STRING!.trim();
  const service = BlobServiceClient.fromConnectionString(conn);
  const container = service.getContainerClient(blobContainerName());
  await container.createIfNotExists();
  return container;
}

// ---------------------------------------------------------------------------
// CSV helpers
// ---------------------------------------------------------------------------

function csvEscape(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function parseCsvLine(line: string): string[] {
  const fields: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      fields.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  fields.push(cur);
  return fields;
}

function isValidRole(role: string): role is AppUserRole {
  return role === "engineer" || role === "reviewer" || role === "viewer";
}

function parseUsersCsv(raw: string): AppUser[] {
  const lines = raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
  if (lines.length === 0) return [];

  const start = lines[0].toLowerCase().startsWith("id,") ? 1 : 0;
  const users: AppUser[] = [];
  for (let i = start; i < lines.length; i++) {
    const cols = parseCsvLine(lines[i]);
    if (cols.length < 5) continue;
    const [id, username, password, role, createdAt] = cols;
    if (!id || !username || !password || !isValidRole(role)) continue;
    users.push({
      id: id.trim(),
      username: username.trim(),
      password,
      role,
      createdAt: createdAt.trim() || new Date().toISOString(),
    });
  }
  return users;
}

function serializeUsersCsv(users: AppUser[]): string {
  const lines = [
    CSV_HEADER,
    ...users.map((u) =>
      [
        csvEscape(u.id),
        csvEscape(u.username),
        csvEscape(u.password),
        csvEscape(u.role),
        csvEscape(u.createdAt),
      ].join(",")
    ),
  ];
  return lines.join("\n") + "\n";
}

// ---------------------------------------------------------------------------
// Local file I/O
// ---------------------------------------------------------------------------

function ensureLocalCsvFile(): string {
  const filePath = localCsvPath();
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, CSV_HEADER + "\n", "utf8");
  }
  return filePath;
}

function loadUsersFromFile(): AppUser[] {
  const filePath = ensureLocalCsvFile();
  const raw = fs.readFileSync(filePath, "utf8");
  return parseUsersCsv(raw);
}

function saveUsersToFile(users: AppUser[]): void {
  const filePath = ensureLocalCsvFile();
  fs.writeFileSync(filePath, serializeUsersCsv(users), "utf8");
}

// ---------------------------------------------------------------------------
// Azure Blob I/O (shared CSV post-deployment)
// ---------------------------------------------------------------------------

async function loadUsersFromBlob(): Promise<AppUser[]> {
  const container = await getContainerClient();
  const blob = container.getBlockBlobClient(blobName());
  const exists = await blob.exists();
  if (!exists) {
    const empty = CSV_HEADER + "\n";
    await blob.upload(empty, Buffer.byteLength(empty), {
      blobHTTPHeaders: { blobContentType: "text/csv" },
    });
    return [];
  }
  const download = await blob.download(0);
  const chunks: Buffer[] = [];
  const stream = download.readableStreamBody;
  if (!stream) return [];
  for await (const chunk of stream) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  return parseUsersCsv(raw);
}

async function saveUsersToBlob(users: AppUser[]): Promise<void> {
  const container = await getContainerClient();
  const blob = container.getBlockBlobClient(blobName());
  const body = serializeUsersCsv(users);
  // Full-file overwrite so every replica shares the same users.csv content
  await blob.uploadData(Buffer.from(body, "utf8"), {
    blobHTTPHeaders: { blobContentType: "text/csv" },
  });
}

// ---------------------------------------------------------------------------
// Public API (async — always prefer these)
// ---------------------------------------------------------------------------

export function getUsersStorageInfo(): {
  mode: "azure-blob" | "local-file";
  detail: string;
} {
  if (isAzureBlobEnabled()) {
    return {
      mode: "azure-blob",
      detail: `${blobContainerName()}/${blobName()}`,
    };
  }
  return { mode: "local-file", detail: localCsvPath() };
}

export async function loadUsers(): Promise<AppUser[]> {
  if (isAzureBlobEnabled()) {
    return loadUsersFromBlob();
  }
  return loadUsersFromFile();
}

async function saveUsers(users: AppUser[]): Promise<void> {
  if (isAzureBlobEnabled()) {
    await saveUsersToBlob(users);
    return;
  }
  saveUsersToFile(users);
}

export async function listUsers(): Promise<Omit<AppUser, "password">[]> {
  const users = await loadUsers();
  return users.map((u) => ({
    id: u.id,
    username: u.username,
    role: u.role,
    createdAt: u.createdAt,
  }));
}

export async function findUser(
  username: string
): Promise<AppUser | undefined> {
  const users = await loadUsers();
  return users.find(
    (u) => u.username.toLowerCase() === username.trim().toLowerCase()
  );
}

export async function createUser(input: {
  username: string;
  password: string;
  role: AppUserRole;
}): Promise<Omit<AppUser, "password">> {
  const username = input.username.trim();
  if (!username || !input.password) {
    throw new Error("Username and password are required");
  }
  const list = await loadUsers();
  if (list.some((u) => u.username.toLowerCase() === username.toLowerCase())) {
    throw new Error("Username already exists");
  }
  const user: AppUser = {
    id: `user-${Date.now().toString(36)}`,
    username,
    password: input.password,
    role: input.role,
    createdAt: new Date().toISOString(),
  };
  list.push(user);
  await saveUsers(list);
  return {
    id: user.id,
    username: user.username,
    role: user.role,
    createdAt: user.createdAt,
  };
}

export async function deleteUser(id: string): Promise<boolean> {
  const list = await loadUsers();
  const next = list.filter((u) => u.id !== id);
  if (next.length === list.length) return false;
  await saveUsers(next);
  return true;
}

export async function updateUser(
  id: string,
  patch: Partial<Pick<AppUser, "username" | "password" | "role">>
): Promise<Omit<AppUser, "password"> | null> {
  const list = await loadUsers();
  const user = list.find((u) => u.id === id);
  if (!user) return null;
  if (patch.username) {
    const name = patch.username.trim();
    const clash = list.find(
      (u) => u.id !== id && u.username.toLowerCase() === name.toLowerCase()
    );
    if (clash) throw new Error("Username already exists");
    user.username = name;
  }
  if (patch.password) user.password = patch.password;
  if (patch.role) user.role = patch.role;
  await saveUsers(list);
  return {
    id: user.id,
    username: user.username,
    role: user.role,
    createdAt: user.createdAt,
  };
}
