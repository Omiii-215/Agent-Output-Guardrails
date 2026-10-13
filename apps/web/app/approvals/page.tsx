"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ErrorNote, Loading, Money, SimulationTag, Status } from "@/components/ui";

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function Approvals() {
  const pending = useQuery({ queryKey: ["approvals", "PENDING"], queryFn: () => api<any[]>("/v1/approval-requests?state=PENDING") });
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Approvals waiting</h1>
      <p className="muted text-sm">
        Each request is bound to one exact payload digest. Changing amount, payee or purpose creates a new proposal that needs new approval.
      </p>
      <ErrorNote error={pending.error} />
      {pending.isLoading ? <Loading /> : null}
      <ul className="space-y-2">
        {(pending.data ?? []).map((r) => (
          <li key={r.id} className="card space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <Link href={`/cases/${r.case.id}`} className="font-semibold">
                {r.case.title}
              </Link>
              <Status value={r.state} />
              {r.proposal.simulated ? <SimulationTag /> : null}
            </div>
            <div className="text-sm">
              <Money value={r.proposal.amount} /> to {r.proposal.payload.beneficiary?.account_last4 ? `•••• ${r.proposal.payload.beneficiary.account_last4}` : "payee"} ·{" "}
              {r.approved_count}/{r.required_count} approvals · requested by {r.requested_by} · expires {new Date(r.expires_at).toLocaleString()}
            </div>
            <div className="mono muted">{r.action_digest}</div>
          </li>
        ))}
        {pending.data?.length === 0 ? <li className="muted text-sm">Nothing waiting.</li> : null}
      </ul>
    </div>
  );
}
