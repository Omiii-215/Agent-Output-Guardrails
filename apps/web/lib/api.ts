import type { paths } from "./api-types";
import { loadSession } from "./session";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: unknown,
  ) {
    super(message);
  }
}

function headers(extra?: HeadersInit): Headers {
  const h = new Headers(extra);
  const session = loadSession();
  if (session) {
    h.set("X-Dev-User", session.subject);
    if (session.organizationId) h.set("X-Organization-Id", session.organizationId);
  }
  return h;
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init;
  const h = headers(rest.headers);
  if (json !== undefined) h.set("Content-Type", "application/json");
  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: h,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (!res.ok) {
    let body: { error?: { code?: string; message?: string; details?: unknown }; detail?: unknown } = {};
    try {
      body = await res.json();
    } catch {
      /* non-JSON error */
    }
    const err = body.error;
    throw new ApiError(
      res.status,
      err?.code ?? (res.status === 422 ? "INVALID_INPUT" : "HTTP_" + res.status),
      err?.message ?? (body.detail ? JSON.stringify(body.detail) : res.statusText),
      err?.details ?? body.detail,
    );
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

/** Unique key per retriable mutation, so a double-click converges on one operation. */
export function idempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export async function sha256(data: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", data);
  return "sha256:" + Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Upload a file through the quarantine flow and return the verified document version. */
export async function uploadFile(file: File): Promise<{ id: string; status: string; rejection_reason: string | null }> {
  const bytes = await file.arrayBuffer();
  const created = await api<{ document_version_id: string; upload_url: string }>("/v1/uploads", {
    method: "POST",
    json: {
      filename: file.name,
      media_type: file.type || "application/octet-stream",
      size: bytes.byteLength,
      declared_sha256: await sha256(bytes),
    },
  });
  await fetch(`${API_URL}${created.upload_url}`, { method: "PUT", body: bytes });
  return api(`/v1/uploads/${created.document_version_id}/complete`, { method: "POST" });
}

export type Schemas = paths;
