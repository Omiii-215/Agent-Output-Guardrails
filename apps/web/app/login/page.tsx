"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect, useRef, Suspense } from "react";
import { useSession } from "@/app/providers";
import { api } from "@/lib/api";
import { PERSONAS } from "@/lib/session";
import { ErrorNote } from "@/components/ui";

const PERSONA_ALIAS_MAP: Record<string, string> = {
  operator: "operator@acme.test",
  approver: "approver@acme.test",
  approver2: "approver2@acme.test",
  auditor: "auditor@acme.test",
  "policy-author": "author@acme.test",
  author: "author@acme.test",
  publisher: "publisher@acme.test",
  admin: "admin@acme.test",
  globex: "operator@globex.test",
  harbor: "operator@harbor.test",
};

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
      "Upload invoices and confirm what the AI read",
      "Run the checks on an invoice",
      "Ask for a payment",
      "Import bank and ledger records",
    ],
    restriction: "Can’t approve payments or publish rules",
  },
  "approver@acme.test": {
    role: "Finance Approver",
    roleTag: "finance_approver",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "Approve or reject payment requests",
      "Clear issues flagged for review",
      "Confirm supplier bank details",
      "Use the emergency stop on payments",
    ],
    restriction: "Can’t approve their own requests (maker-checker)",
  },
  "approver2@acme.test": {
    role: "Finance Approver (₹50k limit)",
    roleTag: "finance_approver",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "Approve payments under ₹50,000",
      "Read the check results",
      "See each supplier’s status",
    ],
    restriction: "Payments over ₹50,000 need a more senior approver",
  },
  "auditor@acme.test": {
    role: "Auditor",
    roleTag: "auditor",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "See every case’s full history and decisions",
      "Read the audit log",
      "Export evidence packs",
    ],
    restriction: "Read-only: can’t create or change anything",
  },
  "author@acme.test": {
    role: "Policy Author",
    roleTag: "policy_author",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "Write and edit business rules",
      "Test rule changes against saved examples",
    ],
    restriction: "Can’t make rules live (a publisher has to)",
  },
  "publisher@acme.test": {
    role: "Policy Publisher",
    roleTag: "policy_publisher",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "Check and publish rules",
      "Give a reason for every change",
    ],
    restriction: "Can’t write the rules they publish (four-eyes)",
  },
  "admin@acme.test": {
    role: "Organization Admin",
    roleTag: "org_admin",
    tenant: "Acme Corp (Primary)",
    canDo: [
      "Manage people and their roles",
      "Watch system health and work queues",
      "Stop all payments in an emergency",
    ],
    restriction: "Can’t create invoices or approve payments",
  },
  "operator@globex.test": {
    role: "Finance Operator",
    roleTag: "finance_operator",
    tenant: "Globex Corp (second company)",
    canDo: [
      "Works only on Globex’s data",
      "Upload and process Globex invoices",
    ],
    restriction: "Kept separate: can’t see Acme Corp data",
  },  "operator@harbor.test": {
    role: "Finance Operator",
    roleTag: "finance_operator",
    tenant: "Harbor Lane Supply Co. (Hugging Face dataset, USD)",
    canDo: [
      "Work through the 26 real dataset invoices and their checks",
      "Ask for payments on invoices that passed",
    ],
    restriction: "Cannot approve payments or see Acme and Globex data",
  },
  "approver@harbor.test": {
    role: "Finance Approver",
    roleTag: "finance_approver",
    tenant: "Harbor Lane Supply Co. (Hugging Face dataset, USD)",
    canDo: [
      "Approve payments up to $50,000",
      "Verify vendor bank details",
    ],
    restriction: "Cannot approve payments they proposed",
  },
  "approver2@harbor.test": {
    role: "Finance Approver (low limit)",
    roleTag: "finance_approver",
    tenant: "Harbor Lane Supply Co. (Hugging Face dataset, USD)",
    canDo: [
      "Approve payments up to $2,500",
    ],
    restriction: "Can’t approve anything over $2,500",
  },
  "controller@harbor.test": {
    role: "Financial Controller",
    roleTag: "finance_approver",
    tenant: "Harbor Lane Supply Co. (Hugging Face dataset, USD)",
    canDo: [
      "Approve payments up to $100,000",
      "Second approval on payments above $5,000",
    ],
    restriction: "Cannot approve payments they proposed",
  },
  "auditor@harbor.test": {
    role: "Auditor",
    roleTag: "auditor",
    tenant: "Harbor Lane Supply Co. (Hugging Face dataset, USD)",
    canDo: [
      "Read every case, finding and payment",
      "Export evidence packs",
    ],
    restriction: "Read-only: cannot change anything",
  },
};

function LoginForm() {
  const { setSession } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [subject, setSubject] = useState(PERSONAS[0].subject);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  const selectedDetails = PERSONA_DETAILS[subject] ?? PERSONA_DETAILS["operator@acme.test"];

  // Sign in once per ?persona= link (from the website's buttons).
  const autoSignedIn = useRef<string | null>(null);
  useEffect(() => {
    const personaParam = searchParams.get("persona");
    if (!personaParam || autoSignedIn.current === personaParam) return;
    autoSignedIn.current = personaParam;
    const targetSubject = PERSONA_ALIAS_MAP[personaParam.toLowerCase()] ?? personaParam;
    if (targetSubject) {
      setSubject(targetSubject);
      (async () => {
        setLoading(true);
        try {
          setSession({ subject: targetSubject, organizationId: null });
          const me = await api<Me>("/v1/me");
          if (me.memberships.length > 0) {
            setSession({ subject: targetSubject, organizationId: me.memberships[0].organization_id });
            router.push("/");
          }
        } catch {
          setSession(null);
        } finally {
          setLoading(false);
        }
      })();
    }
  }, [searchParams, router, setSession]);

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
          className="ink-panel lg:col-span-7 xl:col-span-7 flex flex-col justify-between px-5 py-10 sm:p-10 lg:p-14 border-t lg:border-t-0 lg:border-r"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="space-y-8">
            {/* Header branding */}
            <div className="flex items-center gap-3">
              <span className="wordmark" style={{ fontSize: "1.6rem" }}>
                FIN<span>GUARD</span>
              </span>
              <span className="stamp">Control &amp; Evidence</span>
            </div>

            {/* Hero statement */}
            <div className="space-y-3 max-w-2xl">
              <h1
                className="font-display uppercase"
                style={{
                  fontSize: "clamp(2.6rem, 5.2vw, 4.4rem)",
                  fontWeight: 900,
                  lineHeight: 0.95,
                  color: "var(--text)",
                }}
              >
                Your AI can read the invoice.{" "}
                <span className="block" style={{ color: "var(--accent)" }}>It can&rsquo;t move the money.</span>
              </h1>
              <p
                className="text-sm leading-relaxed"
                style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}
              >
                FinGuard sits between AI that reads your documents and the money you pay out. A person confirms every value the AI reads, your rules are checked automatically, and no payment goes out until a second person approves it.
              </p>
            </div>

            {/* Architecture pillar cards */}
            <div className="grid gap-3 sm:grid-cols-3 pt-2">
              <div
                className="card space-y-2 p-4"
                style={{ background: "var(--surface)" }}
              >
                <div
                  className="text-xs uppercase tracking-wider"
                  style={{ color: "var(--accent-text)" }}
                >
                  Pillar 1
                </div>
                <h2 className="section-title" style={{ fontSize: "1.05rem" }}>
                  A Person Checks
                </h2>
                <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
                  What the AI reads is only a draft. A person confirms each value before anything else happens.
                </p>
              </div>

              <div
                className="card space-y-2 p-4"
                style={{ background: "var(--surface)" }}
              >
                <div
                  className="text-xs uppercase tracking-wider"
                  style={{ color: "var(--accent-text)" }}
                >
                  Pillar 2
                </div>
                <h2 className="section-title" style={{ fontSize: "1.05rem" }}>
                  Maker-Checker
                </h2>
                <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
                  The system won’t let the person who asks for a payment approve it too.
                </p>
              </div>

              <div
                className="card space-y-2 p-4"
                style={{ background: "var(--surface)" }}
              >
                <div
                  className="text-xs uppercase tracking-wider"
                  style={{ color: "var(--accent-text)" }}
                >
                  Pillar 3
                </div>
                <h2 className="section-title" style={{ fontSize: "1.05rem" }}>
                  A Record You Can Trust
                </h2>
                <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
                  Every step is saved in a log that can’t be edited. Export the evidence whenever you need it.
                </p>
              </div>
            </div>
          </div>

          {/* Bottom metadata badges */}
          <div
            className="pt-8 mt-8 border-t border-dashed flex flex-wrap items-center gap-4 text-xs uppercase tracking-wider"
            style={{ borderColor: "var(--border-subtle)", color: "var(--muted)" }}
          >
            <span className="flex items-center gap-1.5">
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{ background: "var(--pass)", boxShadow: "0 0 0 3px var(--pass-bg)" }}
              />
              Sample data only
            </span>
            <span>&bull;</span>
            <span>7 roles</span>
            <span>&bull;</span>
            <span>Versioned rules</span>
            <span>&bull;</span>
            <span>Nothing paid without approval</span>
          </div>
        </section>

        {/* Right column: Interactive Persona Sign-In Console */}
        <section
          className="order-first lg:order-none lg:col-span-5 xl:col-span-5 flex flex-col justify-center px-5 py-8 sm:p-10 lg:p-12"
          style={{ background: "var(--bg)" }}
        >
          <div className="w-full max-w-md mx-auto space-y-6">
            <span className="wordmark lg:hidden" style={{ fontSize: "1.5rem" }}>
              FIN<span>GUARD</span>
            </span>
            <div>
              <h2 className="page-title" style={{ fontSize: "2.1rem" }}>
                Development sign-in
              </h2>
              <p
                className="mt-1 text-xs"
                style={{ color: "var(--text-secondary)", lineHeight: "1.5" }}
              >
                Pick a person to sign in as. Each one can do different things.
              </p>
            </div>

            <form onSubmit={signIn} className="space-y-4">
              <div className="space-y-1.5">
                <label
                  className="block text-xs font-medium uppercase tracking-wider"
                  style={{ color: "var(--muted)" }}
                  htmlFor="persona"
                >
                  Sign in as
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
                      style={{ color: "var(--muted)", fontSize: "0.72rem" }}
                    >
                      Can do
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
                Test sign-in only. A real deployment would use your company’s sign-in.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center">Loading workspace...</div>}>
      <LoginForm />
    </Suspense>
  );
}
