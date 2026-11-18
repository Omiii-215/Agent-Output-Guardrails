"use client";

import Link from "next/link";
import { useSession } from "@/app/providers";

export default function HowItWorks() {
  const { session } = useSession();

  return (
    <div className="space-y-8">
      {session && (
        <div>
          <Link
            href="/"
            className="btn btn-secondary text-xs inline-flex items-center gap-1.5"
            style={{ textDecoration: "none" }}
          >
            &larr; Back to overview
          </Link>
        </div>
      )}
      <header>
        <h1 className="page-title">How FinGuard works</h1>
        <p className="page-description mt-2">
          FinGuard is an evidence and control platform that sits between your AI tools and your financial operations.
          Every AI-generated output is checked, every human decision is recorded, and no payment moves without explicit
          approval from a qualified person.
        </p>
      </header>

      {/* ── Product workflow ─────────────────────────────────────── */}
      <section className="space-y-4">
        <h2 className="section-title">The workflow, step by step</h2>

        <ol className="space-y-3">
          <Step
            number={1}
            title="Invoice arrives"
            description="An operator uploads a PDF invoice or enters the data manually. If a document is attached, AI reads the fields (supplier, amount, dates, PO number), but every value it reads is marked unconfirmed."
          />
          <Step
            number={2}
            title="Human confirms every field"
            description="A person must open the source document and tick off each field to confirm it matches. They can also correct any value the AI got wrong. Every change is saved as a new version, with a reason."
          />
          <Step
            number={3}
            title="The rules are checked"
            description="The system checks the invoice against your published rules: is the amount within budget? Is there a PO number? Are the supplier’s bank details confirmed? Each rule gives a result: PASS, REVIEW or BLOCK."
          />
          <Step
            number={4}
            title="Results are reviewed"
            description="PASS needs no action. REVIEW has to be looked at by a qualified person, who writes down why it’s acceptable. BLOCK stops everything."
          />
          <Step
            number={5}
            title="A payment is requested"
            description="Once the checks pass, an operator asks for a payment with the exact amount, currency and payee. The request gets a digital fingerprint, so any later change is caught."
          />
          <Step
            number={6}
            title="An independent approver decides"
            description="A different person (the approver) looks at the exact payment and approves or rejects it, giving a reason. The person who asked for the payment can’t approve it (maker-checker)."
          />
          <Step
            number={7}
            title="The payment is made"
            description="Only after approval does the system send the payment. In this prototype the payment is simulated; a real setup would send it to your bank. The result (paid or failed) is recorded."
          />
          <Step
            number={8}
            title="Reconciliation"
            description="Bank statements and accounting records are imported. The system suggests pairs with the same reference, amount and currency. Anything that doesn’t match goes to a person to sort out."
          />
          <Step
            number={9}
            title="Full audit trail"
            description="Every action is recorded in an audit log that can’t be edited. Authorised people can export the full evidence for any cases: the document, every version, every check result, every decision and every approval."
          />
        </ol>
      </section>

      {/* ── Roles ────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <h2 className="section-title">Roles and what each one can do</h2>
        <p className="page-description">
          No role implies another. An administrator cannot approve payments, and an operator cannot sign off on their own work. This separation is enforced by the backend, not just the UI.
        </p>

        <div className="grid gap-4 sm:grid-cols-2">
          <RoleCard
            title="Finance Operator"
            tag="finance_operator"
            items={[
              "Upload invoice documents",
              "Enter or correct invoice fields",
              "Run the checks on an invoice",
              "Ask for payments once checks pass",
              "Request approval from a qualified approver",
              "Send approved payments",
              "Import bank/ledger records for reconciliation",
              "Accept or reject proposed matches",
            ]}
          />
          <RoleCard
            title="Finance Approver"
            tag="finance_approver"
            items={[
              "Approve or reject payment requests",
              "Can’t approve their own requests (maker-checker)",
              "Run the checks themselves",
              "Clear issues flagged for review",
              "Verify vendor bank accounts",
              "Activate the emergency stop on all payments",
              "Read and export audit logs",
            ]}
          />
          <RoleCard
            title="Compliance Reviewer"
            tag="compliance_reviewer"
            items={[
              "Review cases in read mode",
              "Clear issues flagged for review",
              "Read audit event logs",
              "Can’t create invoices, ask for payments or approve anything",
            ]}
          />
          <RoleCard
            title="Auditor"
            tag="auditor"
            items={[
              "Read all cases and their full history",
              "Read audit event logs",
              "Export evidence for chosen cases",
              "Read-only: can’t change anything",
            ]}
          />
          <RoleCard
            title="Policy Author"
            tag="policy_author"
            items={[
              "Write new rule drafts",
              "Edit the rules and their limits",
              "Test drafts against saved examples",
              "Can’t publish (a different person must)",
            ]}
          />
          <RoleCard
            title="Policy Publisher"
            tag="policy_publisher"
            items={[
              "Publish tested drafts so they take effect",
              "Must be a different person from the author (four-eyes)",
              "Gives a reason for every publish",
              "Can’t write or edit drafts",
            ]}
          />
          <RoleCard
            title="Organization Admin"
            tag="org_admin"
            items={[
              "Manage organization members and their roles",
              "View operational status and system health",
              "Activate the emergency stop on all payments",
              "Cannot create invoices, approve payments, or write policies",
            ]}
          />
        </div>
      </section>

      {/* ── Key principles ───────────────────────────────────────── */}
      <section className="space-y-4">
        <h2 className="section-title">Key principles</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <PrincipleCard
            title="Human in the loop"
            description="AI extracts data but never makes a decision. Every value must be confirmed by a person, every finding must be reviewed by a person, and every payment must be approved by a person."
          />
          <PrincipleCard
            title="Maker-checker separation"
            description="The person who proposes an action cannot be the one who approves it. This is enforced by the system, not by policy alone."
          />
          <PrincipleCard
            title="A log no one can edit"
            description="Every action is recorded. Nothing can be deleted or changed. Evidence can be exported for outside review."
          />
          <PrincipleCard
            title="AI with limits"
            description="The AI only reads documents and fills in a fixed form. It can’t start payments, approve anything or skip a check."
          />
          <PrincipleCard
            title="Rules written down"
            description="Business rules are written down, tested and versioned. One person writes a change and another publishes it (four-eyes), and old versions are kept."
          />
          <PrincipleCard
            title="Locked payment details"
            description="Each payment request gets a digital fingerprint. If the amount, payee or purpose changes after approval, the fingerprint no longer matches and the payment is stopped."
          />
        </div>
      </section>
    </div>
  );
}

/* ── Sub-components ─────────────────────────────────────────────────── */

function Step({ number, title, description }: { number: number; title: string; description: string }) {
  return (
    <li className="card flex gap-4 items-start">
      <span
        className="flex-shrink-0 flex items-center justify-center rounded-full font-semibold text-sm"
        style={{
          width: "2rem",
          height: "2rem",
          background: "var(--accent-subtle)",
          color: "var(--accent)",
        }}
      >
        {number}
      </span>
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="text-sm text-secondary mt-0.5" style={{ lineHeight: "1.6" }}>{description}</p>
      </div>
    </li>
  );
}

function RoleCard({ title, tag, items }: { title: string; tag: string; items: string[] }) {
  return (
    <div className="card space-y-2">
      <div>
        <h3 className="section-title">{title}</h3>
        <span className="mono" style={{ fontSize: "0.7rem" }}>{tag}</span>
      </div>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-secondary flex gap-2" style={{ lineHeight: "1.55" }}>
            <span className="flex-shrink-0 muted" aria-hidden>--</span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function PrincipleCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="card space-y-1">
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="text-sm text-secondary" style={{ lineHeight: "1.6" }}>{description}</p>
    </div>
  );
}
