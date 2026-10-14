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
        <h1 className="page-title" style={{ fontSize: "1.5rem" }}>How FinGuard works</h1>
        <p className="page-description mt-2">
          FinGuard is an evidence and control platform that sits between your AI tools and your financial operations.
          Every AI-generated output is checked, every human decision is recorded, and no payment moves without explicit
          approval from a qualified person.
        </p>
      </header>

      {/* ── Product workflow ─────────────────────────────────────── */}
      <section className="space-y-4">
        <h2 className="section-title" style={{ fontSize: "1.1rem" }}>The workflow, step by step</h2>

        <ol className="space-y-3">
          <Step
            number={1}
            title="Invoice arrives"
            description="An operator uploads a PDF invoice or enters the data manually. If a document is attached, AI extracts the fields (vendor, amount, dates, PO number) -- but every extracted value is marked as unverified."
          />
          <Step
            number={2}
            title="Human confirms every field"
            description="A person must open the source document and tick off each field to confirm it matches. They can also correct any value the AI got wrong. Every change is versioned and recorded with a reason."
          />
          <Step
            number={3}
            title="Policy checks run"
            description="The system evaluates the invoice against a published rule set: is the amount within budget? Does the PO number exist? Is the vendor's bank account verified? Each rule produces a finding -- PASS, REVIEW, or BLOCK."
          />
          <Step
            number={4}
            title="Findings are reviewed"
            description="PASS findings need no action. REVIEW findings must be examined and resolved by a qualified reviewer who records why the item is acceptable. BLOCK findings stop the process entirely."
          />
          <Step
            number={5}
            title="Payment is proposed"
            description="Once checks pass, an operator creates a payment proposal with the exact amount, currency, and payee. The proposal is cryptographically hashed so any change to the payload is detectable."
          />
          <Step
            number={6}
            title="An independent approver decides"
            description="A different person (the approver) reviews the exact payload and either approves or rejects it with a recorded reason. The person who proposed the payment cannot approve it (maker-checker separation)."
          />
          <Step
            number={7}
            title="Payment executes"
            description="Only after approval does the system create an execution intent. In this prototype the payment is simulated, but in production this would call the actual payment provider. The result (settled or failed) is recorded."
          />
          <Step
            number={8}
            title="Reconciliation"
            description="Bank statements and accounting ledger records are imported. The system proposes one-to-one matches based on reference, amount, and currency. Unmatched or mismatched items become exceptions that a person must resolve."
          />
          <Step
            number={9}
            title="Full audit trail"
            description="Every action across the entire workflow is recorded in an append-only audit log. Authorized users can export complete evidence bundles for any set of cases, including the document, every version, every finding, every decision, and every approval."
          />
        </ol>
      </section>

      {/* ── Roles ────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <h2 className="section-title" style={{ fontSize: "1.1rem" }}>Roles and what each one can do</h2>
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
              "Run policy checks on a case",
              "Propose payments after checks pass",
              "Request approval from a qualified approver",
              "Execute approved payments",
              "Import bank/ledger records for reconciliation",
              "Accept or reject proposed matches",
            ]}
          />
          <RoleCard
            title="Finance Approver"
            tag="finance_approver"
            items={[
              "Review and approve or reject payment proposals",
              "Cannot approve their own proposals (maker-checker)",
              "Run policy checks independently",
              "Resolve findings flagged for review",
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
              "Resolve findings flagged for review",
              "Read audit event logs",
              "Cannot create invoices, propose payments, or approve anything",
            ]}
          />
          <RoleCard
            title="Auditor"
            tag="auditor"
            items={[
              "Read all cases and their full history",
              "Read audit event logs",
              "Export evidence bundles for specific cases",
              "Strictly read-only -- cannot change any data",
            ]}
          />
          <RoleCard
            title="Policy Author"
            tag="policy_author"
            items={[
              "Create new policy drafts",
              "Edit the rule document (JSON) with parameters",
              "Validate drafts against regression scenarios",
              "Cannot publish a policy (needs a separate publisher)",
            ]}
          />
          <RoleCard
            title="Policy Publisher"
            tag="policy_publisher"
            items={[
              "Publish validated policy drafts to make them active",
              "Must be a different person from the author (four-eyes)",
              "Records a reason for every publication",
              "Cannot author or edit policy drafts",
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
        <h2 className="section-title" style={{ fontSize: "1.1rem" }}>Key principles</h2>
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
            title="Immutable audit trail"
            description="Every action is recorded in an append-only log. Nothing can be deleted or overwritten. Evidence bundles can be exported for external review."
          />
          <PrincipleCard
            title="Bounded AI"
            description="AI extraction is limited to structured data from documents. The AI cannot initiate payments, approve transactions, or bypass any check."
          />
          <PrincipleCard
            title="Policy as code"
            description="Business rules are defined as versioned, validated rule sets. Changes go through author then publisher (four-eyes), and old versions are retained."
          />
          <PrincipleCard
            title="Cryptographic integrity"
            description="Payment proposals are hashed. Any change to amount, payee, or purpose after approval creates a mismatch that blocks execution."
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
