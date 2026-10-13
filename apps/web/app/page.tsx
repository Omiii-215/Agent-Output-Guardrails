"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Loading, Section, Status } from "@/components/ui";

type CaseRow = { id: string; title: string; module: string; status: string; outcome: string | null; updated_at: string };

export default function Overview() {
  const cases = useQuery({
    queryKey: ["cases", "open"],
    queryFn: () => api<{ items: CaseRow[] }>("/v1/cases?open_only=true&limit=200"),
  });
  const approvals = useQuery({ queryKey: ["approvals", "PENDING"], queryFn: () => api<unknown[]>("/v1/approval-requests") });
  const recon = useQuery({
    queryKey: ["recon-summary"],
    queryFn: () => api<{ open_exceptions: number }>("/v1/reconciliation/summary"),
  });
  const controls = useQuery({ queryKey: ["controls"], queryFn: () => api<{ halted: boolean; reason: string | null }>("/v1/actions/controls") });

  const items = cases.data?.items ?? [];
  const byStatus = items.reduce<Record<string, number>>((acc, c) => {
    acc[c.status] = (acc[c.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Overview</h1>
      {controls.data?.halted ? (
        <p role="alert" className="card" style={{ color: "var(--block)" }}>
          Emergency stop active: {controls.data.reason}. No new payment executions will be claimed.
        </p>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Open cases" value={items.length} href="/queue" />
        <Stat label="Approvals waiting" value={approvals.data?.length} href="/approvals" />
        <Stat label="Open reconciliation exceptions" value={recon.data?.open_exceptions} href="/reconciliation" />
      </div>
      <Section title="Open work by status">
        {cases.isLoading ? (
          <Loading />
        ) : (
          <ul className="flex flex-wrap gap-2">
            {Object.entries(byStatus).map(([status, n]) => (
              <li key={status} className="flex items-center gap-2">
                <Status value={status} /> <span className="tabular-nums">{n}</span>
              </li>
            ))}
            {items.length === 0 ? <li className="muted text-sm">Nothing open.</li> : null}
          </ul>
        )}
      </Section>
    </div>
  );
}

function Stat({ label, value, href }: { label: string; value: number | undefined; href: string }) {
  return (
    <Link href={href} className="card block no-underline" style={{ color: "var(--text)" }}>
      <div className="muted text-sm">{label}</div>
      <div className="text-2xl font-bold tabular-nums">{value ?? "—"}</div>
    </Link>
  );
}
