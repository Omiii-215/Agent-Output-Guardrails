export const DASHBOARD_URL =
  process.env.NEXT_PUBLIC_DASHBOARD_URL ?? "http://localhost:3000";

export const GITHUB_URL =
  "https://github.com/Omiii-215/Agent-Output-Guardrails";

export const PERSONAS = [
  {
    id: "operator",
    title: "Operator",
    description: "Upload invoices, trigger extraction, monitor the pipeline.",
    color: "bg-bone text-ink",
  },
  {
    id: "approver",
    title: "Approver",
    description: "Review proposals, verify digests, approve or reject payments.",
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
    description: "Tenant config, user roles, emergency stop. The person with the kill switch.",
    color: "bg-carbon text-bone",
  },
] as const;

export const PIPELINE_STAGES = [
  {
    id: "upload",
    label: "Upload",
    detail: "File enters quarantine",
    icon: "↑",
  },
  {
    id: "verify",
    label: "Verify",
    detail: "Hash, size, type, malware check",
    icon: "🔒",
  },
  {
    id: "extract",
    label: "AI Extract",
    detail: "Bounded extraction with citations",
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
    detail: "Immutable snapshot created",
    icon: "❄",
  },
  {
    id: "policy",
    label: "Policy Check",
    detail: "Deterministic rules, crash ≠ pass",
    icon: "📋",
  },
  {
    id: "proposal",
    label: "Proposal",
    detail: "Digest generated server-side",
    icon: "📝",
  },
  {
    id: "approval",
    label: "Approval",
    detail: "Independent maker-checker sign-off",
    icon: "✓",
  },
  {
    id: "recheck",
    label: "Re-check",
    detail: "Locked re-verification & spend hold",
    icon: "🔄",
  },
  {
    id: "simulate",
    label: "Simulate",
    detail: "Dry-run execution",
    icon: "▶",
  },
  {
    id: "reconcile",
    label: "Reconcile",
    detail: "UNKNOWN? Check, never resend",
    icon: "⚖",
  },
  {
    id: "webhook",
    label: "Webhook",
    detail: "Signed delivery confirmation",
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
    detail: "Sealed, append-only, chained hashes",
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
    name: "Invoice Preflight & Quarantine",
    category: "Ingestion Security",
    detail: "Byte-level quarantine, hash tracking, OCR coordinate validation, and embedded prompt-injection defenses.",
    checks: ["Byte integrity", "Coordinate bounding", "Adversarial text scan", "Tenant isolation RLS"],
    status: "ACTIVE",
  },
  {
    code: "M2",
    name: "Ledger Reconciliation Engine",
    category: "Bookkeeping Integrity",
    detail: "Exact 1:1 settlement matching with tolerance limits for bank fee splits, FX fluctuation, and multi-line disbursements.",
    checks: ["1:1 Settlement", "FX variance bounds", "Fee split parsing", "Zero drift math"],
    status: "ACTIVE",
  },
  {
    code: "M3",
    name: "Anti-Money Laundering (AML)",
    category: "Compliance & Risk",
    detail: "Continuous sanction list cross-checks, velocity tripwires, structuring detection, and high-risk jurisdiction flags.",
    checks: ["OFAC/Sanction lists", "Structuring alerts", "Velocity limits", "Politically exposed persons"],
    status: "ACTIVE",
  },
  {
    code: "M4",
    name: "Chargebacks & Dispute Safeguards",
    category: "Payment Defense",
    detail: "State-machine idempotency locks preventing duplicate wire submissions and automated evidence pack generation for disputes.",
    checks: ["Idempotency keys", "Double-spend lock", "Evidence freeze", "Dispute counter-proofs"],
    status: "ACTIVE",
  },
  {
    code: "M5",
    name: "Payment Gateway & Rail Router",
    category: "Execution Rails",
    detail: "Multi-rail payment orchestration (ACH, Wire, SEPA, RTP) with spend holds, simulated sandboxes, and fail-closed state machines.",
    checks: ["ISO-20022 payload", "Spend reservation", "Fail-closed holds", "Multi-rail routing"],
    status: "ACTIVE",
  },
  {
    code: "M6",
    name: "Credit & Underwriting Guard",
    category: "Counterparty Exposure",
    detail: "Autonomous policy limits on cumulative vendor exposure, credit capacity checks, and corporate spending ceilings.",
    checks: ["Exposure caps", "Solvency signals", "Single-creditor ceiling", "Historical default curves"],
    status: "ACTIVE",
  },
  {
    code: "M7",
    name: "Regulatory Comms & Disclosure",
    category: "Audit & Governance",
    detail: "Tamper-evident cryptographically signed disclosures, webhook payloads, and exportable regulatory audit trails.",
    checks: ["Chained hash ledger", "HMAC webhook signing", "Immutable event stamps", "Zero-alteration audit"],
    status: "ACTIVE",
  },
  {
    code: "M8",
    name: "KYC / KYB Beneficiary Verification",
    category: "Identity Verification",
    detail: "Validates beneficiary corporate entities, matches IBAN to BIC bank records, and detects unauthorized payee account changes.",
    checks: ["IBAN/BIC pairing", "Corporate registry match", "Payee change tamper alert", "Beneficiary provenance"],
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
