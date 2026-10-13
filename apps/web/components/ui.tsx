"use client";

import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";

// Status labels always carry text and an icon, never colour alone.
const TONES: Record<string, { color: string; icon: string }> = {
  PASS: { color: "var(--pass)", icon: "✓" },
  APPROVED: { color: "var(--pass)", icon: "✓" },
  SETTLED: { color: "var(--pass)", icon: "✓" },
  MATCHED: { color: "var(--pass)", icon: "✓" },
  RESOLVED: { color: "var(--pass)", icon: "✓" },
  CLEAN: { color: "var(--pass)", icon: "✓" },
  VERIFIED: { color: "var(--pass)", icon: "✓" },
  READY_FOR_APPROVAL: { color: "var(--pass)", icon: "→" },
  READY_FOR_ACTION: { color: "var(--pass)", icon: "→" },
  REVIEW: { color: "var(--review)", icon: "!" },
  NEEDS_REVIEW: { color: "var(--review)", icon: "!" },
  IN_REVIEW: { color: "var(--review)", icon: "!" },
  PENDING: { color: "var(--review)", icon: "…" },
  AWAITING_APPROVAL: { color: "var(--review)", icon: "…" },
  UNKNOWN: { color: "var(--indeterminate)", icon: "?" },
  INDETERMINATE: { color: "var(--indeterminate)", icon: "?" },
  NEEDS_INFORMATION: { color: "var(--indeterminate)", icon: "?" },
  UNVERIFIED: { color: "var(--indeterminate)", icon: "?" },
  BLOCK: { color: "var(--block)", icon: "✕" },
  BLOCKED: { color: "var(--block)", icon: "✕" },
  REJECTED: { color: "var(--block)", icon: "✕" },
  FAILED: { color: "var(--block)", icon: "✕" },
  STALE: { color: "var(--block)", icon: "⟲" },
  INVALIDATED: { color: "var(--block)", icon: "⟲" },
  EXPIRED: { color: "var(--block)", icon: "⌛" },
};

export function Status({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="muted">—</span>;
  const tone = TONES[value] ?? { color: "var(--muted)", icon: "•" };
  return (
    <span
      style={{ color: tone.color, borderColor: tone.color }}
      className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-semibold"
    >
      <span aria-hidden>{tone.icon}</span>
      {value.replaceAll("_", " ")}
    </span>
  );
}

export function SimulationTag() {
  return (
    <span className="rounded border border-dashed px-1.5 py-0.5 text-xs font-semibold" style={{ borderColor: "var(--indeterminate)", color: "var(--indeterminate)" }}>
      SIMULATION — no money moves
    </span>
  );
}

export function Section({ title, children, actions }: { title: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="card space-y-3" aria-labelledby={title}>
      <div className="flex items-center justify-between gap-2">
        <h2 id={title} className="text-base font-semibold">
          {title}
        </h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error as ApiError;
  return (
    <p role="alert" className="text-sm" style={{ color: "var(--block)" }}>
      {e.code ? <strong>{e.code}: </strong> : null}
      {e.message ?? String(error)}
    </p>
  );
}

export function Loading() {
  return <p className="muted text-sm">Loading…</p>;
}

export function Money({ value }: { value?: { formatted?: string } | null }) {
  return <span className="tabular-nums">{value?.formatted ?? "—"}</span>;
}
