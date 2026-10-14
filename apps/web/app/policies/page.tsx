"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useMe } from "@/components/Shell";
import { ErrorNote, Section, Status } from "@/components/ui";

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function Policies() {
  const qc = useQueryClient();
  const me = useMe();
  const can = (c: string) => me.data?.capabilities.includes(c) ?? false;
  const policies = useQuery({ queryKey: ["policies"], queryFn: () => api<any[]>("/v1/policies") });
  const [selected, setSelected] = useState<any>(null);
  const [draft, setDraft] = useState("");
  const act = useMutation({
    mutationFn: (fn: () => Promise<any>) => fn(),
    onSuccess: (p) => {
      if (p?.id) setSelected(p);
      qc.invalidateQueries({ queryKey: ["policies"] });
    },
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">Policies</h1>
        <p className="page-description mt-1">
          Policies select reviewed rules with bounded parameters. Drafts are validated against regression scenarios and need an independent publisher.
        </p>
      </div>
      <Section title="Versions">
        <div className="overflow-x-auto">
          <table className="text-sm">
            <thead>
              <tr>
                <th>Policy</th>
                <th>Version</th>
                <th>Lifecycle</th>
                <th>Author</th>
                <th>Publisher</th>
              </tr>
            </thead>
            <tbody>
              {(policies.data ?? []).map((p) => (
                <tr key={p.id}>
                  <td>
                    <button className="btn text-xs" onClick={() => { setSelected(p); setDraft(JSON.stringify(p.document, null, 2)); }}>
                      {p.policy_code}
                    </button>
                  </td>
                  <td className="tabular-nums">{p.version}</td>
                  <td>
                    <Status value={p.lifecycle === "PUBLISHED" ? "APPROVED" : p.lifecycle} />
                  </td>
                  <td className="text-secondary">{p.author_subject}</td>
                  <td className="text-secondary">{p.publisher_subject ?? "\u2014"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      {selected ? (
        <Section title={`${selected.policy_code} v${selected.version}`}>
          <p className="mono">{selected.digest}</p>
          {selected.validation_errors?.length ? <ErrorNote error={{ message: selected.validation_errors.join("; ") }} /> : null}
          <label className="block text-sm font-medium">
            Document {can("policy.author") ? "(edit to create a new draft)" : "(read-only)"}
            <textarea className="mono" rows={18} value={draft} readOnly={!can("policy.author")} onChange={(e) => setDraft(e.target.value)} />
          </label>
          <div className="flex flex-wrap gap-2">
            {can("policy.author") ? (
              <button className="btn" onClick={() => act.mutate(() => api("/v1/policies", { method: "POST", json: { document: JSON.parse(draft) } }))}>
                Save as new draft
              </button>
            ) : null}
            {can("policy.author") && selected.lifecycle === "DRAFT" ? (
              <button className="btn" onClick={() => act.mutate(() => api(`/v1/policies/${selected.id}/validate`, { method: "POST" }))}>
                Validate
              </button>
            ) : null}
            {can("policy.publish") && selected.lifecycle === "VALIDATED" ? (
              <button
                className="btn btn-primary"
                onClick={() => {
                  const reason = window.prompt("Reason for publishing (recorded)");
                  if (reason) act.mutate(() => api(`/v1/policies/${selected.id}/publish`, { method: "POST", json: { reason } }));
                }}
              >
                Publish
              </button>
            ) : null}
          </div>
          <ErrorNote error={act.error} />
        </Section>
      ) : null}
    </div>
  );
}
