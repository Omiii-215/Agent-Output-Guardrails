"use client";

import { useState } from "react";
import { useInView } from "@/lib/hooks";

const LAYERS = [
  {
    layerNumber: "LAYER 01",
    name: "Check What Comes In",
    tagline: "Before the AI’s output reaches your systems",
    icon: "🛡️",
    badge: "INCOMING FILES",
    color: "border-l-vermilion",
    items: [
      {
        title: "File Fingerprint and Virus Scan",
        description:
          "Every document is held apart first. We record its fingerprint and check its type, size and contents before anything reads it.",
      },
      {
        title: "A Fixed Form for the AI",
        description:
          "The AI can’t write whatever it likes. It can only fill in set fields, and each one is checked.",
      },
      {
        title: "Every Value Shows Its Source",
        description:
          "Each supplier name, tax ID, quantity and total has to point to the exact place it appears in the original document.",
      },
      {
        title: "Hidden Instruction Scanner",
        description:
          "Looks for white-on-white text, disguised fonts, and lines that try to give the AI orders.",
      },
    ],
  },
  {
    layerNumber: "LAYER 02",
    name: "Apply the Rules Exactly",
    tagline: "No AI in the decision",
    icon: "⚙️",
    badge: "ERRORS STOP PAYMENTS",
    color: "border-l-ink",
    items: [
      {
        title: "Exact Sums",
        description:
          "No rounding surprises. Line items, tax, currency conversions and balances are worked out exactly, to the cent.",
      },
      {
        title: "Locked Before Checking",
        description:
          "Before the rules run, the invoice is locked with a fingerprint. If anything changes after that, the check stops.",
      },
      {
        title: "An Error Is Never a Yes",
        description:
          "If a rule crashes, runs too long or runs out of memory, the payment is held. A failure never counts as approval.",
      },
      {
        title: "Clear Exceptions",
        description:
          "Bank and ledger records are matched one to one. A fee, a split payment or a currency difference is flagged for a person to review.",
      },
    ],
  },
  {
    layerNumber: "LAYER 03",
    name: "Approve and Pay Safely",
    tagline: "Two people involved, and nothing paid twice",
    icon: "🏛️",
    badge: "LOCKED APPROVALS",
    color: "border-l-verify",
    items: [
      {
        title: "Maker-Checker",
        description:
          "The person or AI that prepares a payment is blocked by the system from approving it.",
      },
      {
        title: "Approval Tied to the Details",
        description:
          "The approver signs off on one exact payment. Any quiet change to the amount, payee or bank details cancels the approval.",
      },
      {
        title: "Money Set Aside First",
        description:
          "Each payment reserves its money before it’s sent, so two payments at the same moment can’t overspend the budget.",
      },
      {
        title: "Check, Never Resend",
        description:
          "If the bank connection drops or the result is unknown, FinGuard asks the bank what happened. It never sends the payment a second time.",
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
      className="bg-bone py-24 md:py-32 border-b border-ledger relative"
      id="architecture"
    >
      <div className="container-page">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="font-mono text-xs uppercase tracking-widest text-vermilion font-bold">
            How It’s Built
          </span>
          <h2 className="font-display font-[900] display-xl uppercase text-ink mt-3">
            Three Layers of Firm Controls.
          </h2>
          <p className="font-accent italic text-xl text-ink/75 mt-4">
            How FinGuard puts firm checks around AI before any suggestion gets near your bank or accounting system.
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
