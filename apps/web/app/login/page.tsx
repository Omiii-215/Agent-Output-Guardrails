"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useSession } from "@/app/providers";
import { api } from "@/lib/api";
import { PERSONAS } from "@/lib/session";
import { ErrorNote } from "@/components/ui";

type Me = { memberships: { organization_id: string; organization_name: string; roles: string[] }[] };

const PERSONA_DETAILS: Record<
  string,
  {
    role: string;
    roleTag: string;
    tenant: string;
    canDo: string[];
    restriction: string;
  }
> = {
  "operator@acme.test": {
    role: "Finance Operator",
    roleTag: "finance_operator",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "Upload invoices & verify extracted fields",
      "Run policy checks on cases",
      "Draft payment proposals",
      "Import reconciliation records",
    ],
    restriction: "Cannot approve payment proposals or publish policies",
  },
  "approver@acme.test": {
    role: "Finance Approver",
    roleTag: "finance_approver",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "Review & decide payment proposals",
      "Resolve review-level findings",
      "Verify vendor beneficiaries",
      "Trigger payment emergency stop",
    ],
    restriction: "Cannot approve own proposals (maker-checker separation)",
  },
  "approver2@acme.test": {
    role: "Finance Approver (₹50k limit)",
    roleTag: "finance_approver",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "Approve payments under ₹50,000 threshold",
      "Examine policy evaluation findings",
      "Review vendor compliance status",
    ],
    restriction: "Requires tier escalation for payments above ₹50,000",
  },
  "auditor@acme.test": {
    role: "Auditor",
    roleTag: "auditor",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "Inspect complete case history & decisions",
      "Read immutable audit event stream",
      "Export tamper-evident evidence packages",
    ],
    restriction: "Read-only access; cannot create or mutate cases",
  },
  "author@acme.test": {
    role: "Policy Author",
    roleTag: "policy_author",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "Draft & update business rules (JSON)",
      "Run automated regression test suites",
    ],
    restriction: "Cannot publish policies into production (requires publisher)",
  },
  "publisher@acme.test": {
    role: "Policy Publisher",
    roleTag: "policy_publisher",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "Validate & publish active policies",
      "Record mandatory business justification",
    ],
    restriction: "Cannot author policy drafts (four-eyes segregation)",
  },
  "admin@acme.test": {
    role: "Organization Admin",
    roleTag: "org_admin",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "Manage organization members & roles",
      "Monitor operational health & queues",
      "Activate system-wide emergency halt",
    ],
    restriction: "Cannot create invoices or approve payments",
  },
  "operator@globex.test": {
    role: "Finance Operator",
    roleTag: "finance_operator",
    tenant: "Globex Corp (Second Tenant)",
    canDo: [
      "Isolated operator access for Globex",
      "Upload invoices & process Globex cases",
    ],
    restriction: "Tenant isolated: cannot access Acme Corp data",
  },
};

export default function LoginPage() {
  const { setSession } = useSession();
  const router = useRouter();
  const [subject, setSubject] = useState(PERSONAS[0].subject);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  const selectedDetails = PERSONA_DETAILS[subject] ?? PERSONA_DETAILS["operator@acme.test"];

  async function signIn(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      setSession({ subject, organizationId: null });
      const me = await api<Me>("/v1/me");
      if (me.memberships.length === 0) throw new Error("This identity has no active membership.");
      setSession({ subject, organizationId: me.memberships[0].organization_id });
      router.push("/");
    } catch (err) {
      setSession(null);
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      className="min-h-screen"
      style={{ background: "var(--bg)", color: "var(--text)" }}
    >
      <div className="min-h-screen grid lg:grid-cols-12">
        {/* Left column: Product context & value propositions */}
        <section
          className="lg:col-span-7 xl:col-span-7 flex flex-col justify-between p-6 sm:p-10 lg:p-14 border-b lg:border-b-0 lg:border-r"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="space-y-8">
            {/* Header branding */}
            <div className="flex items-center gap-3">
              <span
                className="font-bold tracking-tight"
                style={{ fontSize: "1.35rem", color: "var(--text)" }}
              >
                FinGuard
              </span>
              <span
                className="text-xs px-2.5 py-0.5 rounded font-medium"
                style={{
                  background: "var(--accent-subtle)",
                  color: "var(--accent)",
                  border: "1px solid var(--border)",
                }}
              >
                Control &amp; Evidence Platform
              </span>
            </div>

            {/* Hero statement */}
            <div className="space-y-3 max-w-2xl">
              <h1
                className="font-semibold tracking-tight"
                style={{
                  fontSize: "2rem",
                  lineHeight: "1.25",
                  color: "var(--text)",
                }}
              >
                Autonomous AI guardrails for financial operations.
              </h1>
              <p
                className="text-sm leading-relaxed"
                style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}
              >
                FinGuard bridges AI document intelligence and financial execution. Every extracted field is human-confirmed, every rule is enforced via policy-as-code, and no payment moves without cryptographically verified maker-checker sign-off.
              </p>
            </div>

            {/* Architecture pillar cards */}
            <div className="grid gap-3 sm:grid-cols-3 pt-2">
              <div
                className="card space-y-2 p-4"
                style={{ background: "var(--surface)" }}
              >
                <div
                  className="text-xs font-semibold uppercase tracking-wider"
                  style={{ color: "var(--accent)" }}
                >
                  Pillar 1
                </div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>
                  Human in the Loop
                </h2>
                <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
                  AI model output is strictly provisional. Extracted data requires operator verification before moving forward.
                </p>
              </div>

              <div
                className="card space-y-2 p-4"
                style={{ background: "var(--surface)" }}
              >
                <div
                  className="text-xs font-semibold uppercase tracking-wider"
                  style={{ color: "var(--accent)" }}
                >
                  Pillar 2
                </div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>
                  Maker-Checker
                </h2>
                <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
                  Segregation of duties is hardcoded at the API boundary. The operator proposing a payment cannot approve it.
                </p>
              </div>

              <div
                className="card space-y-2 p-4"
                style={{ background: "var(--surface)" }}
              >
                <div
                  className="text-xs font-semibold uppercase tracking-wider"
                  style={{ color: "var(--accent)" }}
                >
                  Pillar 3
                </div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>
                  Cryptographic Audit
                </h2>
                <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
                  Append-only event ledger with SHA-256 state digests. Export tamper-evident evidence packages on demand.
                </p>
              </div>
            </div>
          </div>

          {/* Bottom metadata badges */}
          <div
            className="pt-8 mt-8 border-t flex flex-wrap items-center gap-4 text-xs"
            style={{ borderColor: "var(--border-subtle)", color: "var(--muted)" }}
          >
            <span className="flex items-center gap-1.5">
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{ background: "var(--pass)" }}
              />
              Synthetic Sandbox Active
            </span>
            <span>&bull;</span>
            <span>7 Distinct RBAC Roles</span>
            <span>&bull;</span>
            <span>Versioned Policy Engine</span>
            <span>&bull;</span>
            <span>Zero-Trust Execution</span>
          </div>
        </section>

        {/* Right column: Interactive Persona Sign-In Console */}
        <section
          className="lg:col-span-5 xl:col-span-5 flex flex-col justify-center p-6 sm:p-10 lg:p-12"
          style={{ background: "var(--bg)" }}
        >
          <div className="w-full max-w-md mx-auto space-y-6">
            <div>
              <h2
                className="font-semibold tracking-tight"
                style={{ fontSize: "1.35rem", color: "var(--text)" }}
              >
                Development Sign-In
              </h2>
              <p
                className="mt-1 text-xs"
                style={{ color: "var(--text-secondary)", lineHeight: "1.5" }}
              >
                Choose an identity below to test role-specific capabilities, policy checks, and approvals.
              </p>
            </div>

            <form onSubmit={signIn} className="space-y-4">
              <div className="space-y-1.5">
                <label
                  className="block text-xs font-medium uppercase tracking-wider"
                  style={{ color: "var(--muted)" }}
                  htmlFor="persona"
                >
                  Active Persona
                </label>
                <select
                  id="persona"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full text-sm"
                  style={{ background: "var(--surface)" }}
                >
                  {PERSONAS.map((p) => (
                    <option key={p.subject} value={p.subject}>
                      {p.label} &mdash; {p.subject}
                    </option>
                  ))}
                </select>
              </div>

              {/* Dynamic Persona Inspector Card */}
              {selectedDetails && (
                <div
                  className="card p-4 space-y-3"
                  style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold" style={{ color: "var(--text)" }}>
                        {selectedDetails.role}
                      </div>
                      <div className="mono text-xs" style={{ color: "var(--muted)", fontSize: "0.72rem" }}>
                        {selectedDetails.roleTag}
                      </div>
                    </div>
                    <span
                      className="text-xs px-2 py-0.5 rounded"
                      style={{
                        background: "var(--surface-hover)",
                        color: "var(--text-secondary)",
                        border: "1px solid var(--border-subtle)",
                        fontSize: "0.7rem",
                      }}
                    >
                      {selectedDetails.tenant}
                    </span>
                  </div>

                  <div className="space-y-1.5 pt-1">
                    <div
                      className="text-xs font-medium uppercase tracking-wider"
                      style={{ color: "var(--muted)", fontSize: "0.68rem" }}
                    >
                      Granted Capabilities
                    </div>
                    <ul className="space-y-1 text-xs" style={{ color: "var(--text-secondary)" }}>
                      {selectedDetails.canDo.map((item, idx) => (
                        <li key={idx} className="flex items-start gap-1.5">
                          <span
                            className="flex-shrink-0 font-bold"
                            style={{ color: "var(--pass)" }}
                          >
                            &bull;
                          </span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div
                    className="pt-2 border-t text-xs flex items-start gap-1.5"
                    style={{ borderColor: "var(--border-subtle)", color: "var(--review)" }}
                  >
                    <span className="flex-shrink-0 font-bold">&bull;</span>
                    <span>{selectedDetails.restriction}</span>
                  </div>
                </div>
              )}

              <ErrorNote error={error} />

              <button
                type="submit"
                className="btn btn-primary w-full py-2.5 font-medium"
                disabled={loading}
              >
                {loading ? "Signing in\u2026" : "Continue to workspace"}
              </button>
            </form>

            <div className="pt-2 space-y-3">
              <Link
                href="/how-it-works"
                className="btn btn-secondary w-full block text-center py-2 text-xs"
                style={{ textDecoration: "none" }}
              >
                How our product works &amp; roles guide &rarr;
              </Link>

              <p
                className="text-center text-xs"
                style={{ color: "var(--muted)", fontSize: "0.72rem" }}
              >
                Development authentication stub. Production deploys authenticate against OIDC / SAML identity providers.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
