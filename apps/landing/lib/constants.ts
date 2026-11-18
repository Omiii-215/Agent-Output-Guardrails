export const DASHBOARD_URL =
  process.env.NEXT_PUBLIC_DASHBOARD_URL ?? "http://localhost:3000";

export const GITHUB_URL =
  "https://github.com/Omiii-215/Agent-Output-Guardrails";

export const PERSONAS = [
  {
    id: "operator",
    title: "Operator",
    description: "Upload invoices, have the AI read them, and track their progress.",
    color: "bg-bone text-ink",
  },
  {
    id: "approver",
    title: "Approver",
    description: "Review payment requests, then approve or reject them.",
    color: "bg-verify/10 text-ink",
  },
  {
    id: "auditor",
    title: "Auditor",
    description: "Read the sealed audit trail. Export evidence. Ask questions later.",
    color: "bg-ink text-bone",
  },
  {
    id: "policy-author",
    title: "Policy Author",
    description: "Write spend limits, approval chains, and expiry rules. Publish when ready.",
    color: "bg-vermilion/10 text-ink",
  },
  {
    id: "admin",
    title: "Admin",
    description: "Company settings, user roles and the emergency stop. The person with the off switch.",
    color: "bg-carbon text-bone",
  },
] as const;

export const PIPELINE_STAGES = [
  {
    id: "upload",
    label: "Upload",
    detail: "File is held for checking",
    icon: "↑",
  },
  {
    id: "verify",
    label: "Verify",
    detail: "Fingerprint, size, type, virus check",
    icon: "🔒",
  },
  {
    id: "extract",
    label: "AI Reads",
    detail: "Fills a fixed form, with sources",
    icon: "⚙",
  },
  {
    id: "confirm",
    label: "Human Confirms",
    detail: "A person reviews every field",
    icon: "👤",
  },
  {
    id: "snapshot",
    label: "Freeze",
    detail: "Details locked so they can’t change",
    icon: "❄",
  },
  {
    id: "policy",
    label: "Policy Check",
    detail: "Your rules applied; errors hold it",
    icon: "📋",
  },
  {
    id: "proposal",
    label: "Proposal",
    detail: "Payment request with a fingerprint",
    icon: "📝",
  },
  {
    id: "approval",
    label: "Approval",
    detail: "A different person approves",
    icon: "✓",
  },
  {
    id: "recheck",
    label: "Re-check",
    detail: "Checked again; money set aside",
    icon: "🔄",
  },
  {
    id: "simulate",
    label: "Simulate",
    detail: "Test run, no real money",
    icon: "▶",
  },
  {
    id: "reconcile",
    label: "Reconcile",
    detail: "No reply? Check, never resend",
    icon: "⚖",
  },
  {
    id: "webhook",
    label: "Confirmation",
    detail: "Signed message back from the bank",
    icon: "🔔",
  },
  {
    id: "settled",
    label: "Settled",
    detail: "Payment complete",
    icon: "✓",
  },
  {
    id: "audit",
    label: "Audit Export",
    detail: "A record no one can edit, ready to export",
    icon: "📦",
  },
] as const;

export interface FinancialModule {
  code: string;
  name: string;
  category: string;
  detail: string;
  checks: string[];
  status: "ACTIVE" | "PRODUCTION";
}

export const ALL_MODULES: FinancialModule[] = [
  {
    code: "M1",
    name: "Invoice Checks & File Hold",
    category: "Ingestion Security",
    detail: "Holds each file for checking, fingerprints it, makes sure every value matches the document, and catches hidden instructions.",
    checks: ["File unchanged", "Values match the page", "Hidden text scan", "Companies kept apart"],
    status: "ACTIVE",
  },
  {
    code: "M2",
    name: "Ledger Reconciliation Engine",
    category: "Bookkeeping Integrity",
    detail: "Matches bank and ledger records one to one, and flags bank fees, split payments and currency differences.",
    checks: ["One-to-one matching", "Currency difference limits", "Bank fee detection", "Exact sums"],
    status: "ACTIVE",
  },
  {
    code: "M3",
    name: "Anti-Money Laundering (AML)",
    category: "Compliance & Risk",
    detail: "Checks sanctions lists, spots unusually fast or split-up payments, and flags high-risk countries.",
    checks: ["Sanctions lists", "Split-up payments", "Unusually fast payments", "Politically exposed persons"],
    status: "ACTIVE",
  },
  {
    code: "M4",
    name: "Chargebacks & Dispute Safeguards",
    category: "Payment Defense",
    detail: "Stops the same payment going out twice, and builds the evidence pack when a customer disputes a charge.",
    checks: ["One-time payment IDs", "No double payments", "Evidence locked", "Proof for disputes"],
    status: "ACTIVE",
  },
  {
    code: "M5",
    name: "Payment Gateway & Rail Router",
    category: "Execution Rails",
    detail: "Sends payments over bank networks (ACH, wire, SEPA, instant), sets money aside first, and holds anything that errors.",
    checks: ["Standard bank format", "Money set aside", "Errors hold payments", "Several bank networks"],
    status: "ACTIVE",
  },
  {
    code: "M6",
    name: "Credit & Underwriting Guard",
    category: "Counterparty Exposure",
    detail: "Limits how much you owe or lend to any one company, and checks credit and spending caps.",
    checks: ["Limit per company", "Warning signs", "Cap per lender", "Past defaults"],
    status: "ACTIVE",
  },
  {
    code: "M7",
    name: "Regulatory Comms & Disclosure",
    category: "Audit & Governance",
    detail: "Signed notices and messages that show if anyone changed them, plus audit records ready for regulators.",
    checks: ["Linked, locked records", "Signed messages", "Permanent timestamps", "Edit-proof audit"],
    status: "ACTIVE",
  },
  {
    code: "M8",
    name: "KYC / KYB Beneficiary Verification",
    category: "Identity Verification",
    detail: "Confirms who you’re paying, checks the account number matches the bank code, and spots changed bank details.",
    checks: ["Account matches bank code", "Company register check", "Changed bank details alert", "Payee history"],
    status: "ACTIVE",
  },
];

// Backward compatibility aliases
export const BUILT_MODULES = ALL_MODULES.slice(0, 3);
export const GATED_MODULES = ALL_MODULES.slice(3);

export const AUDIT_LOG_LINES = [
  "2024-11-15T00:00:01Z INV-0042 QUARANTINE sha256:a3f8…c91d size:148KB type:pdf",
  "2024-11-15T00:00:02Z INV-0042 MALWARE_CLEAR hash:a3f8…c91d engine:clamav",
  "2024-11-15T00:00:03Z INV-0042 EXTRACT vendor:\"Acme Corp\" amount:12450.00 ccy:USD citations:[L12,L15,L23]",
  "2024-11-15T00:00:04Z INV-0042 CITATION_CHECK pass vendor_match:true amount_match:true",
  "2024-11-15T00:00:04Z INV-0042 INJECTION_SCAN clean no_embedded_instructions",
  "2024-11-15T00:00:05Z INV-0042 HUMAN_CONFIRM operator:jdoe@finguard.io fields_modified:0",
  "2024-11-15T00:00:06Z INV-0042 SNAPSHOT_FROZEN hash:b7e2…f103 immutable:true",
  "2024-11-15T00:00:07Z INV-0042 POLICY_CHECK rules:14 pass:14 fail:0 crash:0",
  "2024-11-15T00:00:08Z INV-0042 PROPOSAL digest:sha256:d4a1…8bc2 authority_limit:50000.00",
  "2024-11-15T00:00:09Z INV-0042 APPROVAL approver:mchen@finguard.io digest_match:true",
  "2024-11-15T00:00:10Z INV-0042 SPEND_RESERVED amount:12450.00 balance_after:287550.00",
  "2024-11-15T00:00:11Z INV-0042 SIMULATE status:SUCCESS gateway:stripe_sim ref:sim_9x8…w2k",
  "2024-11-15T00:00:12Z INV-0042 EXECUTE status:SETTLED ref:pay_7h3…q9r",
  "2024-11-15T00:00:13Z INV-0042 WEBHOOK_SIGNED dest:https://erp.acme.corp/hooks sig:hmac_sha256:e2f1…",
  "2024-11-15T00:00:14Z INV-0042 AUDIT_SEALED chain_hash:sha256:9c0d…4f17 prev:sha256:8b1a…3e09",
  "2024-11-15T00:00:15Z INV-0043 QUARANTINE sha256:f1b2…e834 size:92KB type:pdf",
  "2024-11-15T00:00:16Z INV-0043 INJECTION_DETECT line:47 embedded_instruction:\"ignore previous…\" flagged:true",
  "2024-11-15T00:00:17Z INV-0043 POLICY_CHECK rules:14 pass:12 fail:2 crash:0 BLOCKED",
  "2024-11-15T00:00:18Z INV-0044 QUARANTINE sha256:c3d4…a712 size:203KB type:pdf",
  "2024-11-15T00:00:19Z INV-0044 EXTRACT vendor:\"GlobalParts Ltd\" amount:8920.50 ccy:EUR citations:[L8,L11]",
  "2024-11-15T00:00:20Z INV-0044 RECONCILE status:UNKNOWN retry:false check_only:true",
  "2024-11-15T00:00:21Z INV-0044 RECONCILE_RESOLVED status:SETTLED dedup:confirmed",
];
