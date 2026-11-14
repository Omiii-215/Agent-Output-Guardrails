"use client";

import { useState } from "react";
import { useInView } from "@/lib/hooks";

const LAYERS = [
  {
    layerNumber: "LAYER 01",
    name: "AI Boundary & Quarantine",
    tagline: "Before any token touches your application state",
    icon: "🛡️",
    badge: "INPUT HYGIENE",
    color: "border-l-vermilion",
    items: [
      {
        title: "SHA-256 Byte Fingerprinting & Antivirus",
        description:
          "Every document enters an isolated quarantine bucket. File hashes, MIME types, and binary structures are verified before parsing.",
      },
      {
        title: "Bounded Schema Extraction",
        description:
          "The model cannot produce open-ended output. Responses must conform strictly to typed Pydantic contracts with exact field validations.",
      },
      {
        title: "Coordinate-Mapped Citation Verification",
        description:
          "Every vendor name, tax ID, line-item quantity, and subtotal must cite its exact page and bounding-box coordinates in the original PDF.",
      },
      {
        title: "Adversarial Prompt-Injection Scanner",
        description:
          "Scans for white-on-white text, font manipulation, system-prompt override attempts, and instruction hijack tokens.",
      },
    ],
  },
  {
    layerNumber: "LAYER 02",
    name: "Deterministic Policy Engine",
    tagline: "Zero LLM code in the evaluation loop",
    icon: "⚙️",
    badge: "FAIL-CLOSED LOGIC",
    color: "border-l-ink",
    items: [
      {
        title: "Exact Decimal & Integer Math",
        description:
          "No floating-point errors. Line items, tax formulas, currency conversions, and ledger balances are calculated using exact decimal representations.",
      },
      {
        title: "Immutable SHA-256 Snapshot",
        description:
          "Before policy evaluation begins, the entire payload is frozen into a cryptographic digest. If anything changes upstream, evaluation aborts.",
      },
      {
        title: "Fail-Closed Execution (Crash ≠ Pass)",
        description:
          "If a policy rule script times out, exhausts memory, or throws an unhandled exception, the proposal is frozen. A failure is NEVER an approval.",
      },
      {
        title: "Deterministic Exception Matching",
        description:
          "Reconciliations match exact 1:1 records. Any fee difference, split payment, or currency variance produces an explicit flagged exception.",
      },
    ],
  },
  {
    layerNumber: "LAYER 03",
    name: "Maker-Checker & Execution Gateway",
    tagline: "Enforcing separation of duties and zero double-spend",
    icon: "🏛️",
    badge: "CRYPTOGRAPHIC CONTROL",
    color: "border-l-verify",
    items: [
      {
        title: "Enforced Maker-Checker Separation",
        description:
          "The operator or AI pipeline that extracts and proposes a payment is mathematically blocked by database row-level security from approving it.",
      },
      {
        title: "Server-Side Digest Locking",
        description:
          "The approver signs off on the exact frozen SHA-256 digest string. Any silent modification to amount, recipient, or bank details voids the sign-off.",
      },
      {
        title: "Spend Reservation Concurrency Locks",
        description:
          "Concurrent requests place a ledger hold before execution begins, mathematically eliminating overspend and balance-drain race conditions.",
      },
      {
        title: "Idempotent Reconcile Loop (Never Resend)",
        description:
          "When a bank connection drops or returns UNKNOWN, FinGuard probes the status via read-only channels. It NEVER fires a duplicate payment request.",
      },
    ],
  },
];

export default function ThreeLayers() {
  const [ref, inView] = useInView(0.15);
  const [activeLayer, setActiveLayer] = useState(0);

  return (
    <section
      ref={ref as React.RefObject<HTMLElement>}
      className="bg-bone py-24 md:py-32 px-6 border-b border-ledger relative"
      id="architecture"
    >
      <div className="max-w-6xl mx-auto">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="font-mono text-xs uppercase tracking-widest text-vermilion font-bold">
            The Unique Architectural Solution
          </span>
          <h2 className="font-display font-[900] text-5xl md:text-7xl uppercase text-ink mt-2 leading-[0.95]">
            The Three Layers of Deterministic Control.
          </h2>
          <p className="font-accent italic text-xl text-ink/75 mt-4">
            How FinGuard wraps untrusted AI inside mathematical guarantees
            before any recommendation touches your banking or ERP layer.
          </p>
        </div>

        {/* Layer Selector Tabs */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {LAYERS.map((layer, idx) => (
            <button
              key={layer.layerNumber}
              onClick={() => setActiveLayer(idx)}
              className={`p-5 rounded-xl border-2 text-left transition-all duration-200 ${
                activeLayer === idx
                  ? "bg-white border-ink shadow-xl scale-102"
                  : "bg-bone border-ledger text-ink/70 hover:border-ink/40"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-xs font-bold uppercase text-vermilion">
                  {layer.layerNumber}
                </span>
                <span className="text-2xl">{layer.icon}</span>
              </div>
              <h3 className="font-display font-bold text-xl uppercase text-ink leading-tight">
                {layer.name}
              </h3>
              <p className="font-body text-xs text-ink/60 mt-1">
                {layer.tagline}
              </p>
            </button>
          ))}
        </div>

        {/* Selected Layer Deep-Dive View */}
        <div className="bg-white border-2 border-ink rounded-xl p-8 md:p-12 shadow-2xl relative overflow-hidden transition-all duration-300">
          <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b-2 border-ledger gap-4">
            <div>
              <span className="font-mono text-xs font-bold uppercase text-vermilion">
                {LAYERS[activeLayer].layerNumber} // {LAYERS[activeLayer].badge}
              </span>
              <h3 className="font-display font-[900] text-3xl md:text-4xl uppercase text-ink mt-1">
                {LAYERS[activeLayer].name}
              </h3>
              <p className="font-accent italic text-lg text-ink/70 mt-1">
                {LAYERS[activeLayer].tagline}
              </p>
            </div>
            <div className="stamp stamp-verify text-xs font-bold self-start md:self-auto">
              ENFORCED IN CODE
            </div>
          </div>

          {/* 4 Invariant Features */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-8">
            {LAYERS[activeLayer].items.map((item, i) => (
              <div
                key={item.title}
                className="border-l-4 border-ink pl-5 py-2 hover:border-vermilion transition-colors duration-200"
              >
                <span className="font-mono text-xs text-ink/40 uppercase tracking-widest font-bold">
                  CHECK 0{i + 1}
                </span>
                <h4 className="font-display font-bold text-xl uppercase text-ink mt-1">
                  {item.title}
                </h4>
                <p className="font-body text-sm text-ink/70 mt-2 leading-relaxed">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
