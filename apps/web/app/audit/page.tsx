"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, API_URL } from "@/lib/api";
import { loadSession } from "@/lib/session";
import { ErrorNote, Section, SimulationTag, Status } from "@/components/ui";

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function Audit() {
  const [action, setAction] = useState("");
  const events = useQuery({
    queryKey: ["audit", action],
    queryFn: () => api<any[]>(`/v1/audit/events?limit=200${action ? `&action=${encodeURIComponent(action)}` : ""}`),
  });
  const [caseIds, setCaseIds] = useState("");
  const [purpose, setPurpose] = useState("");
  const [exportId, setExportId] = useState<string | null>(null);
  const status = useQuery({
    queryKey: ["export", exportId],
    queryFn: () => api<any>(`/v1/audit-exports/${exportId}`),
    enabled: !!exportId,
    refetchInterval: (q) => (q.state.data?.state === "READY" ? false : 1500),
  });
  const request = useMutation({
    mutationFn: () =>
      api<any>("/v1/audit-exports", {
        method: "POST",
        json: { purpose, case_ids: caseIds.split(/[\s,]+/).filter(Boolean) },
      }),
    onSuccess: (r) => setExportId(r.id),
  });

  async function download() {
    const s = loadSession();
    const res = await fetch(`${API_URL}/v1/audit-exports/${exportId}/download`, {
      headers: { "X-Dev-User": s?.subject ?? "", "X-Organization-Id": s?.organizationId ?? "" },
    });
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-export-${exportId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Audit</h1>
      <Section title="Evidence export">
        <form
          className="grid gap-2 sm:grid-cols-3"
          onSubmit={(e) => {
            e.preventDefault();
            request.mutate();
          }}
        >
          <label className="text-sm sm:col-span-2">
            Case IDs (comma or space separated)
            <input value={caseIds} onChange={(e) => setCaseIds(e.target.value)} />
          </label>
          <label className="text-sm">
            Purpose
            <input required minLength={5} value={purpose} onChange={(e) => setPurpose(e.target.value)} />
          </label>
          <button className="btn btn-primary">Request export</button>
        </form>
        {status.data ? (
          <p className="text-sm">
            <Status value={status.data.state === "READY" ? "CLEAN" : status.data.state} /> {status.data.case_count} cases · digest{" "}
            <span className="mono">{status.data.bundle_digest}</span>{" "}
            {status.data.state === "READY" ? (
              <button className="btn text-xs" onClick={download}>
                Download
              </button>
            ) : null}
          </p>
        ) : null}
        <ErrorNote error={request.error ?? status.error} />
      </Section>
      <Section title="Audit events">
        <label className="text-sm">
          Filter by action
          <input value={action} onChange={(e) => setAction(e.target.value)} placeholder="e.g. approval.approved" />
        </label>
        <ErrorNote error={events.error} />
        <table className="text-sm">
          <thead>
            <tr>
              <th>When</th>
              <th>Actor</th>
              <th>Action</th>
              <th>Object</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {(events.data ?? []).map((e) => (
              <tr key={e.id}>
                <td className="muted">{new Date(e.occurred_at).toLocaleString()}</td>
                <td>{e.actor_id}</td>
                <td>
                  {e.action} {e.simulated ? <SimulationTag /> : null}
                </td>
                <td className="mono">
                  {e.object_type} {e.object_id?.slice(0, 8)}
                </td>
                <td>{e.reason ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  );
}
