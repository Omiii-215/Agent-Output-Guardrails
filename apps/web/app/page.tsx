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
    <div className="space-y-5">
      <div>
        <h1 className="page-title">Overview</h1>
        <p className="page-description mt-1">Summary of active work across your organization.</p>
      </div>
      {controls.data?.halted ? (
        <div role="alert" className="notice-banner notice-banner--warning">
          <strong>Emergency stop active</strong>
          <span>{controls.data.reason}. No new payment executions will be claimed.</span>
        </div>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Open cases" value={items.length} href="/queue" />
        <Stat label="Approvals waiting" value={approvals.data?.length} href="/approvals" />
        <Stat label="Recon exceptions" value={recon.data?.open_exceptions} href="/reconciliation" />
      </div>
      <Section title="Open work by status">
        {cases.isLoading ? (
          <Loading />
        ) : (
          <ul className="flex flex-wrap gap-2">
            {Object.entries(byStatus).map(([status, n]) => (
              <li key={status} className="flex items-center gap-2">
                <Status value={status} /> <span className="tabular-nums text-sm font-medium">{n}</span>
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
    <Link href={href} className="stat-card">
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value">{value ?? "\u2014"}</div>
    </Link>
  );
}
