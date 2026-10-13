"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, API_URL, uploadFile } from "@/lib/api";
import { ErrorNote, Section, Status } from "@/components/ui";
import { loadSession } from "@/lib/session";

/* eslint-disable @typescript-eslint/no-explicit-any */
const DEFAULT_MAPPING = {
  BANK: { external_id: "txn_id", booked_on: "date", amount: "amount", reference: "ref", description: "narration" },
  LEDGER: { external_id: "entry", booked_on: "posted", amount: "amount", reference: "ref", description: "memo" },
};

export default function Reconciliation() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["recon"] });
  const matches = useQuery({ queryKey: ["recon", "matches"], queryFn: () => api<any[]>("/v1/reconciliation/matches") });
  const exceptions = useQuery({ queryKey: ["recon", "exceptions"], queryFn: () => api<any[]>("/v1/reconciliation/exceptions") });
  const imports = useQuery({ queryKey: ["recon", "imports"], queryFn: () => api<any[]>("/v1/reconciliation/imports"), refetchInterval: 3000 });
  const [side, setSide] = useState<"BANK" | "LEDGER">("BANK");
  const [mapping, setMapping] = useState(JSON.stringify(DEFAULT_MAPPING.BANK, null, 1));
  const [file, setFile] = useState<File | null>(null);

  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a CSV file");
      const doc = await uploadFile(new File([await file.arrayBuffer()], file.name, { type: "text/csv" }));
      if (doc.status !== "CLEAN") throw new Error(`Upload rejected: ${doc.rejection_reason}`);
      return api("/v1/reconciliation/imports", { method: "POST", json: { document_version_id: doc.id, side, mapping: JSON.parse(mapping) } });
    },
    onSuccess: refresh,
  });
  const decide = useMutation({
    mutationFn: (v: { id: string; version: number; approve: boolean }) =>
      api(`/v1/reconciliation/matches/${v.id}/${v.approve ? "approve" : "reject"}`, {
        method: "POST",
        json: { expected_version: v.version, reason: v.approve ? "Same reference, amount and currency" : "Not the same transaction" },
      }),
    onSuccess: refresh,
  });

  async function downloadExport() {
    const s = loadSession();
    const res = await fetch(`${API_URL}/v1/reconciliation/export`, {
      headers: { "X-Dev-User": s?.subject ?? "", "X-Organization-Id": s?.organizationId ?? "" },
    });
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = "reconciliation-export.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Reconciliation</h1>
      <Section title="Import records" actions={<button className="btn text-sm" onClick={downloadExport}>Export approved results</button>}>
        <form
          className="grid gap-3 sm:grid-cols-3"
          onSubmit={(e) => {
            e.preventDefault();
            upload.mutate();
          }}
        >
          <label className="text-sm">
            Side
            <select
              value={side}
              onChange={(e) => {
                const s = e.target.value as "BANK" | "LEDGER";
                setSide(s);
                setMapping(JSON.stringify(DEFAULT_MAPPING[s], null, 1));
              }}
            >
              <option value="BANK">Bank statement</option>
              <option value="LEDGER">Accounting ledger</option>
            </select>
          </label>
          <label className="text-sm">
            CSV file
            <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          <label className="text-sm sm:row-span-2">
            Column mapping (JSON)
            <textarea rows={6} className="mono" value={mapping} onChange={(e) => setMapping(e.target.value)} />
          </label>
          <button className="btn btn-primary self-start" disabled={upload.isPending}>
            Import
          </button>
        </form>
        <ErrorNote error={upload.error} />
        <ul className="text-sm">
          {(imports.data ?? []).slice(0, 5).map((b) => (
            <li key={b.id}>
              {b.side} · <Status value={b.state === "IMPORTED" ? "CLEAN" : b.state} /> {b.imported_count} rows
              {b.errors.length ? <span className="muted"> · {b.errors.length} issues ({b.errors[0]})</span> : null}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Proposed exact matches">
        <p className="muted text-sm">Only one-to-one matches with the same reference, signed amount and currency are proposed.</p>
        <table className="text-sm">
          <thead>
            <tr>
              <th>Reference</th>
              <th>Bank</th>
              <th>Ledger</th>
              <th>Amount</th>
              <th>Decision</th>
            </tr>
          </thead>
          <tbody>
            {(matches.data ?? []).map((m) => {
              const bank = m.rows.find((r: any) => r.side === "BANK");
              const ledger = m.rows.find((r: any) => r.side === "LEDGER");
              return (
                <tr key={m.id}>
                  <td className="mono">{m.basis.reference}</td>
                  <td>
                    {bank?.external_id} · {bank?.description}
                  </td>
                  <td>
                    {ledger?.external_id} · {ledger?.description}
                  </td>
                  <td className="tabular-nums">{bank?.amount.formatted}</td>
                  <td className="flex gap-1">
                    <button className="btn text-xs" onClick={() => decide.mutate({ id: m.id, version: m.version, approve: true })}>
                      Accept
                    </button>
                    <button className="btn text-xs" onClick={() => decide.mutate({ id: m.id, version: m.version, approve: false })}>
                      Reject
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <ErrorNote error={decide.error} />
      </Section>

      <Section title="Exceptions needing review">
        <ul className="space-y-1 text-sm">
          {(exceptions.data ?? []).map((e) => (
            <li key={e.id}>
              <Link href={`/cases/${e.case_id}`}>{e.kind.replaceAll("_", " ").toLowerCase()}</Link> · {e.transaction.side}{" "}
              {e.transaction.external_id} · {e.transaction.amount.formatted}
            </li>
          ))}
          {exceptions.data?.length === 0 ? <li className="muted">No open exceptions.</li> : null}
        </ul>
      </Section>
    </div>
  );
}
