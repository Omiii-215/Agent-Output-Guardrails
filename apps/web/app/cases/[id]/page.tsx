"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, API_URL, idempotencyKey } from "@/lib/api";
import { useMe } from "@/components/Shell";
import { ErrorNote, Loading, Money, Section, SimulationTag, Status } from "@/components/ui";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Detail = Record<string, any>;

const EDITABLE = ["invoice_number", "invoice_date", "due_date", "currency", "total", "po_number"] as const;

export default function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const me = useMe();
  const can = (cap: string) => me.data?.capabilities.includes(cap) ?? false;
  const detail = useQuery({
    queryKey: ["case", id],
    queryFn: () => api<Detail>(`/v1/cases/${id}`),
    refetchInterval: (q) => {
      const s = q.state.data?.case?.status;
      return s === "EVALUATING" || s === "EXTRACTING" || s === "ACTION_PENDING" ? 1500 : false;
    },
    refetchIntervalInBackground: true,
  });
  const history = useQuery({ queryKey: ["history", id], queryFn: () => api<any[]>(`/v1/cases/${id}/history`) });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["case", id] });
    qc.invalidateQueries({ queryKey: ["history", id] });
  };

  if (detail.isLoading) return <Loading />;
  if (detail.error) return <ErrorNote error={detail.error} />;
  const d = detail.data!;
  const c = d.case;

  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-xl font-bold">{c.title}</h1>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="muted">Progress</span> <Status value={c.status} />
          <span className="muted">Latest outcome</span> <Status value={c.outcome} />
          <span className="muted">Revision {c.revision}</span>
        </div>
        {d.next_actions?.length ? (
          <p className="text-sm">
            Next: {d.next_actions.map((a: string) => a.replaceAll("_", " ").toLowerCase()).join(" · ")}
          </p>
        ) : null}
      </header>

      {d.invoice ? <InvoicePanel d={d} onChange={refresh} canWrite={can("case.write")} canEvaluate={can("evaluation.run")} /> : null}
      {d.evaluation ? <FindingsPanel d={d} onChange={refresh} canResolve={can("finding.resolve")} /> : null}
      {d.invoice ? <PaymentPanel d={d} onChange={refresh} can={can} /> : null}
      {d.exception ? <ExceptionPanel d={d} onChange={refresh} canResolve={can("reconciliation.match_approve")} /> : null}
      <Comments caseId={id} />
      <Section title="History">
        <ol className="space-y-1 text-sm">
          {(history.data ?? []).map((e) => (
            <li key={e.id}>
              <span className="muted">{new Date(e.occurred_at).toLocaleString()}</span> · <strong>{e.action}</strong> by{" "}
              {e.actor_id}
              {e.reason ? <> — {e.reason}</> : null}
              {e.simulated ? <> <SimulationTag /></> : null}
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
}

function InvoicePanel({ d, onChange, canWrite, canEvaluate }: { d: Detail; onChange: () => void; canWrite: boolean; canEvaluate: boolean }) {
  const inv = d.invoice;
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [verify, setVerify] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const save = useMutation({
    mutationFn: () =>
      api(`/v1/invoices/${inv.id}`, {
        method: "PATCH",
        json: { expected_revision: d.case.revision, fields: edits, verify, reason },
      }),
    onSuccess: () => {
      setEdits({});
      setVerify([]);
      setReason("");
      onChange();
    },
  });
  const evaluate = useMutation({
    mutationFn: () => api(`/v1/cases/${d.case.id}/evaluations`, { method: "POST", json: { expected_revision: d.case.revision } }),
    onSuccess: onChange,
  });
  const download = useMutation({
    mutationFn: () => api<{ download_url: string }>(`/v1/documents/${inv.document_version_id}/download-grants`, { method: "POST" }),
    onSuccess: (g) => window.open(`${API_URL}${g.download_url}`, "_blank", "noopener"),
  });
  const value = (name: string) => {
    if (name === "total") return inv.total?.formatted;
    if (name === "invoice_number") return inv.number;
    return inv[name];
  };
  const editable = canWrite && !["EVALUATING", "ACTION_PENDING", "RESOLVED", "CLOSED"].includes(d.case.status);

  return (
    <Section
      title="Invoice"
      actions={
        <div className="flex gap-2">
          {inv.document_version_id ? (
            <button className="btn text-sm" onClick={() => download.mutate()}>
              Open source document
            </button>
          ) : null}
          {canEvaluate && d.case.status === "READY_TO_EVALUATE" ? (
            <button className="btn btn-primary text-sm" onClick={() => evaluate.mutate()} disabled={evaluate.isPending}>
              Run checks
            </button>
          ) : null}
        </div>
      }
    >
      <p className="text-sm">
        Vendor <strong>{d.vendor.name}</strong> · version {inv.version} ({inv.source.toLowerCase()}) · payee{" "}
        {d.beneficiary ? (
          <>
            {d.beneficiary.account_holder} {d.beneficiary.account_masked} {d.beneficiary.ifsc} <Status value={d.beneficiary.verification_status} />
          </>
        ) : (
          "none on record"
        )}
      </p>
      <table>
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">Value</th>
            <th scope="col">Source</th>
            {editable ? <th scope="col">Correct</th> : null}
            {editable ? <th scope="col">Confirm</th> : null}
          </tr>
        </thead>
        <tbody>
          {EDITABLE.map((name) => {
            const st = inv.field_status?.[name];
            return (
              <tr key={name}>
                <th scope="row" className="font-normal">
                  {name.replaceAll("_", " ")}
                </th>
                <td>{value(name) ?? <span className="muted">missing</span>}</td>
                <td className="text-xs">{st ? `${st.status.toLowerCase()}${st.evidence_refs?.length ? " · cited" : ""}` : "—"}</td>
                {editable ? (
                  <td>
                    <input
                      aria-label={`Correct ${name}`}
                      value={edits[name] ?? ""}
                      placeholder={name === "total" ? "e.g. 5900.00" : ""}
                      onChange={(e) => setEdits({ ...edits, [name]: e.target.value })}
                    />
                  </td>
                ) : null}
                {editable ? (
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`Confirm ${name} matches the document`}
                      checked={verify.includes(name)}
                      onChange={(e) => setVerify(e.target.checked ? [...verify, name] : verify.filter((v) => v !== name))}
                      style={{ width: "auto" }}
                    />
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
      {inv.lines?.length ? (
        <details>
          <summary className="cursor-pointer text-sm">{inv.lines.length} line items</summary>
          <table className="mt-2 text-sm">
            <thead>
              <tr>
                <th>Description</th>
                <th>Qty</th>
                <th>Unit price</th>
                <th>Tax rate</th>
              </tr>
            </thead>
            <tbody>
              {inv.lines.map((l: any) => (
                <tr key={l.line_no}>
                  <td>{l.description}</td>
                  <td>{l.quantity}</td>
                  <td>{l.unit_price}</td>
                  <td>{l.tax_rate}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      ) : null}
      {editable && (Object.keys(edits).length > 0 || verify.length > 0) ? (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <label className="flex-1 text-sm">
            Reason (recorded in history)
            <input required minLength={3} value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
          <button className="btn btn-primary" disabled={save.isPending}>
            Save new version
          </button>
        </form>
      ) : null}
      <ErrorNote error={save.error ?? evaluate.error ?? download.error} />
    </Section>
  );
}

function FindingsPanel({ d, onChange, canResolve }: { d: Detail; onChange: () => void; canResolve: boolean }) {
  const ev = d.evaluation;
  const resolve = useMutation({
    mutationFn: (v: { id: string; code: string; reason: string }) =>
      api(`/v1/findings/${v.id}/resolutions`, { method: "POST", json: { resolution_code: v.code, reason: v.reason } }),
    onSuccess: onChange,
  });
  return (
    <Section title="Checks">
      <p className="text-sm">
        Outcome <Status value={ev.outcome} /> · policy version <span className="mono">{ev.policy_version_id.slice(0, 8)}</span> · inputs{" "}
        <span className="mono">{ev.input_digest.slice(0, 19)}…</span>
      </p>
      {ev.explanation ? (
        <p className="text-sm">
          <span className="muted">AI-generated summary of the findings below (advisory): </span>
          {ev.explanation}
        </p>
      ) : null}
      <ul className="space-y-2">
        {d.findings.map((f: any) => {
          const resolved = f.resolutions.length > 0;
          return (
            <li key={f.id} className="rounded border p-2" style={{ borderColor: "var(--border)" }}>
              <div className="flex flex-wrap items-center gap-2">
                <Status value={f.effect ?? f.result} />
                <strong className="text-sm">{f.title}</strong>
                <span className="mono muted">{f.reason_code}</span>
              </div>
              <p className="text-sm">{f.message}</p>
              {Object.keys(f.observed ?? {}).length ? (
                <p className="mono muted">observed {JSON.stringify(f.observed)}</p>
              ) : null}
              {f.evidence_ids.map((eid: string) => (
                <blockquote key={eid} className="muted mt-1 border-l-2 pl-2 text-xs" style={{ borderColor: "var(--border)" }}>
                  page {d.evidence[eid]?.locator?.page}: “{d.evidence[eid]?.excerpt}”
                </blockquote>
              ))}
              {f.resolutions.map((r: any, i: number) => (
                <p key={i} className="text-xs">
                  Resolved as {r.resolution_code} by {r.actor_subject}: {r.reason}
                </p>
              ))}
              {canResolve && f.effect === "REVIEW" && !resolved ? (
                <button
                  className="btn mt-1 text-xs"
                  onClick={() => {
                    const reason = window.prompt("Why is this acceptable? (recorded)");
                    if (reason) resolve.mutate({ id: f.id, code: "REVIEWED_ACCEPTABLE", reason });
                  }}
                >
                  Resolve after review
                </button>
              ) : null}
            </li>
          );
        })}
      </ul>
      <ErrorNote error={resolve.error} />
    </Section>
  );
}

function PaymentPanel({ d, onChange, can }: { d: Detail; onChange: () => void; can: (c: string) => boolean }) {
  const proposals: any[] = d.proposals ?? [];
  const intents: any[] = d.intents ?? [];
  const run = useMutation({ mutationFn: (fn: () => Promise<unknown>) => fn(), onSuccess: onChange });
  const propose = () =>
    api("/v1/action-proposals", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("proposal") },
      json: {
        case_id: d.case.id,
        expected_case_revision: d.case.revision,
        action_type: "PAYMENT",
        amount: { amount_minor: d.invoice.total.amount_minor, currency: d.invoice.total.currency },
        beneficiary_version_id: d.beneficiary.id,
        purpose: `Payment of invoice ${d.invoice.number}`,
        mode: "SIMULATED",
      },
    });

  return (
    <Section title="Payment (simulated)" actions={<SimulationTag />}>
      {d.next_actions?.includes("CREATE_PAYMENT_PROPOSAL") && can("proposal.create") ? (
        <button className="btn btn-primary" onClick={() => run.mutate(propose)} disabled={run.isPending}>
          Propose payment of <Money value={d.invoice.total} />
        </button>
      ) : null}
      {proposals.map((p) => {
        const intent = intents.find((i) => i.proposal_id === p.id);
        const approval = p.approval;
        return (
          <div key={p.id} className="space-y-2 rounded border p-3" style={{ borderColor: "var(--border)" }}>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Status value={p.state} /> <Money value={p.amount} /> proposed by {p.maker_subject}
              {p.maker_actor_type === "service" ? " (agent)" : ""}
            </div>
            {p.state_reason ? <p className="muted text-xs">{p.state_reason}</p> : null}
            <p className="mono muted">digest {p.digest}</p>
            {p.preflight?.findings
              ?.filter((f: any) => f.effect)
              .map((f: any) => (
                <p key={f.rule_code} className="text-sm">
                  <Status value={f.effect} /> {f.message}
                </p>
              ))}
            {approval ? (
              <div className="text-sm">
                Approval <Status value={approval.state} /> {approval.approved_count}/{approval.required_count} · expires{" "}
                {new Date(approval.expires_at).toLocaleString()}
                <ul className="text-xs">
                  {approval.decisions.map((x: any) => (
                    <li key={x.actor_subject}>
                      {x.decision} by {x.actor_subject}: {x.reason}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {p.state === "READY_FOR_APPROVAL" && can("approval.request") ? (
                <button className="btn" onClick={() => run.mutate(() => api("/v1/approval-requests", { method: "POST", json: { proposal_id: p.id } }))}>
                  Request approval
                </button>
              ) : null}
              {approval?.state === "PENDING" && can("approval.decide") ? (
                <>
                  <button
                    className="btn btn-primary"
                    onClick={() => {
                      const reason = window.prompt("Approval note (recorded)", "Evidence reviewed");
                      if (reason)
                        run.mutate(() =>
                          api(`/v1/approval-requests/${approval.id}/decisions`, {
                            method: "POST",
                            json: { decision: "APPROVE", reason, expected_revision: approval.revision },
                          }),
                        );
                    }}
                  >
                    Approve exact payload
                  </button>
                  <button
                    className="btn"
                    onClick={() => {
                      const reason = window.prompt("Reason for rejection");
                      if (reason)
                        run.mutate(() =>
                          api(`/v1/approval-requests/${approval.id}/decisions`, {
                            method: "POST",
                            json: { decision: "REJECT", reason, expected_revision: approval.revision },
                          }),
                        );
                    }}
                  >
                    Reject
                  </button>
                </>
              ) : null}
              {p.state === "APPROVED" && !intent && can("intent.create") ? (
                <button
                  className="btn btn-primary"
                  onClick={() =>
                    run.mutate(() =>
                      api("/v1/action-intents", {
                        method: "POST",
                        headers: { "Idempotency-Key": idempotencyKey("intent") },
                        json: { proposal_id: p.id, approval_request_id: approval.id },
                      }),
                    )
                  }
                >
                  Execute (simulated)
                </button>
              ) : null}
            </div>
            {intent ? <IntentView intent={intent} canOperate={can("case.read")} onChange={onChange} /> : null}
          </div>
        );
      })}
      <ErrorNote error={run.error} />
    </Section>
  );
}

function IntentView({ intent, canOperate, onChange }: { intent: any; canOperate: boolean; onChange: () => void }) {
  const advance = useMutation({
    mutationFn: (state: string) => api(`/v1/simulator/intents/${intent.id}/advance`, { method: "POST", json: { state } }),
    onSuccess: () => setTimeout(onChange, 1200),
  });
  return (
    <div className="space-y-1 text-sm">
      <div>
        Execution <Status value={intent.execution.state} /> {intent.execution.reason}
      </div>
      <div className="mono muted">provider key {intent.provider.idempotency_key}</div>
      <ul className="text-xs">
        {intent.provider.history.map((h: any, i: number) => (
          <li key={i}>
            {h.kind} → {h.outcome} ({h.code})
          </li>
        ))}
      </ul>
      {canOperate && intent.execution.state === "ACCEPTED" ? (
        <div className="flex gap-2">
          <span className="muted text-xs">Simulator console:</span>
          <button className="btn text-xs" onClick={() => advance.mutate("SETTLED")}>
            Provider settles
          </button>
          <button className="btn text-xs" onClick={() => advance.mutate("FAILED")}>
            Provider fails
          </button>
        </div>
      ) : null}
      <ErrorNote error={advance.error} />
    </div>
  );
}

function ExceptionPanel({ d, onChange, canResolve }: { d: Detail; onChange: () => void; canResolve: boolean }) {
  const [code, setCode] = useState("BANK_CHARGES");
  const [note, setNote] = useState("");
  const resolve = useMutation({
    mutationFn: () => api(`/v1/reconciliation/exceptions/${d.exception.id}/resolve`, { method: "POST", json: { resolution_code: code, note } }),
    onSuccess: onChange,
  });
  const row = (r: any) => (
    <tr key={r.id}>
      <td>{r.side}</td>
      <td>{r.external_id}</td>
      <td>{r.reference ?? "—"}</td>
      <td>{r.booked_on}</td>
      <td className="tabular-nums">{r.amount.formatted}</td>
      <td className="muted text-xs">
        batch row {r.lineage.row_number}
      </td>
    </tr>
  );
  return (
    <Section title={`Reconciliation exception: ${d.exception.kind.replaceAll("_", " ").toLowerCase()}`}>
      {d.exception.details?.hint ? <p className="text-sm">{d.exception.details.hint}</p> : null}
      <table className="text-sm">
        <thead>
          <tr>
            <th>Side</th>
            <th>ID</th>
            <th>Reference</th>
            <th>Date</th>
            <th>Amount</th>
            <th>Lineage</th>
          </tr>
        </thead>
        <tbody>{[d.transaction, ...d.counterparts].map(row)}</tbody>
      </table>
      {d.exception.state === "OPEN" && canResolve ? (
        <form
          className="grid gap-2 sm:grid-cols-3"
          onSubmit={(e) => {
            e.preventDefault();
            resolve.mutate();
          }}
        >
          <label className="text-sm">
            Disposition
            <select value={code} onChange={(e) => setCode(e.target.value)}>
              {["BANK_CHARGES", "TIMING_DIFFERENCE", "PARTIAL_PAYMENT", "REQUIRES_LEDGER_CORRECTION", "DUPLICATE_ENTRY", "FX_DIFFERENCE"].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label className="text-sm sm:col-span-2">
            Note
            <input required minLength={3} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <button className="btn btn-primary" disabled={resolve.isPending}>
            Record disposition
          </button>
        </form>
      ) : (
        <p className="text-sm">
          {d.exception.resolution_code} by {d.exception.resolved_by}: {d.exception.resolution_note}
        </p>
      )}
      <ErrorNote error={resolve.error} />
    </Section>
  );
}

function Comments({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const [body, setBody] = useState("");
  const comments = useQuery({ queryKey: ["comments", caseId], queryFn: () => api<any[]>(`/v1/cases/${caseId}/comments`) });
  const add = useMutation({
    mutationFn: () => api(`/v1/cases/${caseId}/comments`, { method: "POST", json: { body } }),
    onSuccess: () => {
      setBody("");
      qc.invalidateQueries({ queryKey: ["comments", caseId] });
    },
  });
  return (
    <Section title="Comments">
      <ul className="space-y-1 text-sm">
        {(comments.data ?? []).map((c) => (
          <li key={c.id}>
            <strong>{c.author_subject}</strong>: {c.body}
          </li>
        ))}
      </ul>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          add.mutate();
        }}
      >
        <label className="sr-only" htmlFor="comment">
          Comment
        </label>
        <input id="comment" value={body} onChange={(e) => setBody(e.target.value)} placeholder="Add a note for reviewers" />
        <button className="btn" disabled={!body || add.isPending}>
          Post
        </button>
      </form>
    </Section>
  );
}
