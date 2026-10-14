"use client";

import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";

// Status tones with semantic grouping. Text-only icons (no emoji).
const TONES: Record<string, { tone: string; icon: string }> = {
  PASS: { tone: "pass", icon: "\u2713" },
  APPROVED: { tone: "pass", icon: "\u2713" },
  SETTLED: { tone: "pass", icon: "\u2713" },
  MATCHED: { tone: "pass", icon: "\u2713" },
  RESOLVED: { tone: "pass", icon: "\u2713" },
  CLEAN: { tone: "pass", icon: "\u2713" },
  VERIFIED: { tone: "pass", icon: "\u2713" },
  READY_FOR_APPROVAL: { tone: "pass", icon: "\u2192" },
  READY_FOR_ACTION: { tone: "pass", icon: "\u2192" },
  REVIEW: { tone: "review", icon: "!" },
  NEEDS_REVIEW: { tone: "review", icon: "!" },
  IN_REVIEW: { tone: "review", icon: "!" },
  PENDING: { tone: "review", icon: "\u2026" },
  AWAITING_APPROVAL: { tone: "review", icon: "\u2026" },
  UNKNOWN: { tone: "indeterminate", icon: "?" },
  INDETERMINATE: { tone: "indeterminate", icon: "?" },
  NEEDS_INFORMATION: { tone: "indeterminate", icon: "?" },
  UNVERIFIED: { tone: "indeterminate", icon: "?" },
  BLOCK: { tone: "block", icon: "\u2715" },
  BLOCKED: { tone: "block", icon: "\u2715" },
  REJECTED: { tone: "block", icon: "\u2715" },
  FAILED: { tone: "block", icon: "\u2715" },
  STALE: { tone: "block", icon: "\u21bb" },
  INVALIDATED: { tone: "block", icon: "\u21bb" },
  EXPIRED: { tone: "block", icon: "\u231b" },
};

export function Status({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="muted">&mdash;</span>;
  const t = TONES[value] ?? { tone: "neutral", icon: "\u00b7" };
  return (
    <span className={`status-badge status-${t.tone}`}>
      <span aria-hidden>{t.icon}</span>
      {value.replaceAll("_", " ")}
    </span>
  );
}

export function SimulationTag() {
  return (
    <span className="simulation-tag">
      SIMULATION &mdash; no money moves
    </span>
  );
}

export function Section({ title, children, actions }: { title: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="card space-y-3" aria-labelledby={title}>
      <div className="flex items-center justify-between gap-2">
        <h2 id={title} className="section-title">
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
    <div role="alert" className="notice-banner notice-banner--warning">
      {e.code ? <strong>{e.code}:</strong> : null}
      <span>{e.message ?? String(error)}</span>
    </div>
  );
}

export function Loading() {
  return <p className="loading-spinner">Loading</p>;
}

export function Money({ value }: { value?: { formatted?: string } | null }) {
  return <span className="tabular-nums">{value?.formatted ?? "\u2014"}</span>;
}
