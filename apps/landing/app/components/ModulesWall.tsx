"use client";

import { useState } from "react";
import { useReducedMotion, useInView } from "@/lib/hooks";
import { ALL_MODULES, FinancialModule, DASHBOARD_URL } from "@/lib/constants";

function ShieldCheckIcon({ className }: { className?: string }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function ModuleCard({
  module,
}: {
  module: FinancialModule;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className={`border-l-4 border-verify bg-white rounded-r-xl p-6 shadow-sm transition-all duration-300 relative flex flex-col justify-between ${
        hovered
          ? "shadow-xl -translate-y-1 border-l-8 ring-1 ring-verify/30"
          : "hover:shadow-md"
      }`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Top Header */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <span className="font-display font-[900] text-3xl text-ink leading-none">
              {module.code}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-wider text-ink/40 bg-bone px-2 py-0.5 rounded border border-ledger">
              {module.category}
            </span>
          </div>
          <span className="inline-flex items-center gap-1.5 text-verify font-mono text-xs font-bold uppercase tracking-wider bg-verify/10 px-2.5 py-1 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-verify animate-pulse" />
            UNLOCKED
          </span>
        </div>

        {/* Title */}
        <h3 className="font-display font-bold text-xl text-ink uppercase leading-snug">
          {module.name}
        </h3>

        {/* Detail */}
        <p className="font-body text-xs text-ink/70 mt-2.5 leading-relaxed">
          {module.detail}
        </p>
      </div>

      {/* Invariant Verification Checks */}
      <div className="mt-5 pt-4 border-t border-ledger/40">
        <span className="font-mono text-[10px] text-ink/40 uppercase tracking-widest block mb-2">
          Deterministic Invariants
        </span>
        <div className="grid grid-cols-2 gap-1.5">
          {module.checks.map((check, i) => (
            <div
              key={i}
              className="flex items-center gap-1.5 font-mono text-[11px] text-ink/80"
            >
              <ShieldCheckIcon className="text-verify shrink-0 w-3.5 h-3.5" />
              <span className="truncate">{check}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function ModulesWall() {
  const prefersReduced = useReducedMotion();
  const [ref, inView] = useInView({ threshold: 0.1, once: true });
  const [activeFilter, setActiveFilter] = useState<string>("ALL");

  const categories = ["ALL", "Ingestion Security", "Bookkeeping Integrity", "Compliance & Risk", "Execution Rails"];

  const filteredModules =
    activeFilter === "ALL"
      ? ALL_MODULES
      : ALL_MODULES.filter(
          (m) =>
            m.category === activeFilter ||
            (activeFilter === "Compliance & Risk" && (m.category === "Compliance & Risk" || m.category === "Audit & Governance" || m.category === "Identity Verification"))
        );

  return (
    <section ref={ref} className="bg-bone py-24 md:py-32 px-6 border-b border-ledger/30" id="modules">
      <div className="max-w-6xl mx-auto">
        {/* Section number */}
        <div className="flex items-center justify-between">
          <span className="font-mono text-sm text-vermilion font-bold tracking-widest uppercase">
            Platform Capabilities // Revision 2026.11
          </span>
          <span className="font-mono text-xs text-verify font-bold bg-verify/10 px-3 py-1 rounded-full border border-verify/30">
            8 / 8 MODULES ACTIVE
          </span>
        </div>

        {/* Heading */}
        <div className="mt-4 flex flex-col md:flex-row md:items-end justify-between gap-6 pb-8 border-b-2 border-ledger">
          <div>
            <h2 className="font-display font-900 text-5xl sm:text-7xl md:text-8xl uppercase text-ink leading-[0.9]">
              The 8 Financial
              <br />
              <span className="text-verify">Guardrail Modules.</span>
            </h2>
            <p className="font-accent italic text-xl md:text-2xl text-ink/75 mt-4 max-w-2xl">
              Every critical failure point in enterprise financial operations is governed by a dedicated, deterministic evaluator. Zero locked contracts.
            </p>
          </div>

          {/* Metric Callout */}
          <div className="bg-white border-2 border-ink p-4 rounded-lg shadow-sm text-center min-w-[200px]">
            <span className="font-mono text-[10px] text-ink/50 uppercase tracking-widest block">
              EVALUATOR COVERAGE
            </span>
            <span className="font-display font-black text-4xl text-ink block mt-0.5">
              100%
            </span>
            <span className="font-mono text-[10px] text-verify font-bold uppercase tracking-wider">
              Full Runtime Suite
            </span>
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap gap-2 mt-8">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveFilter(cat)}
              className={`font-mono text-xs uppercase px-3 py-1.5 rounded-md font-bold transition-all cursor-pointer ${
                activeFilter === cat
                  ? "bg-ink text-bone shadow-sm"
                  : "bg-white text-ink/60 border border-ledger hover:text-ink hover:border-ink/40"
              }`}
            >
              {cat === "ALL" ? "All 8 Modules" : cat}
            </button>
          ))}
        </div>

        {/* All 8 Modules Grid - All Unlocked */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-8">
          {filteredModules.map((mod) => (
            <ModuleCard key={mod.code} module={mod} />
          ))}
        </div>

        {/* Bottom Guarantee Banner */}
        <div className="mt-12 bg-white border-2 border-ink rounded-xl p-6 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚡</span>
            <p className="font-body text-sm text-ink/80">
              <strong className="text-ink">Composable Financial Rails:</strong> Every module exposes standard gRPC & JSON APIs with PostgreSQL Row-Level Security. Plug them into existing ERPs, SAP, Netsuite, or modern payment flows.
            </p>
          </div>
          <a
            href={`${DASHBOARD_URL}/modules?persona=operator`}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-xs font-bold uppercase tracking-wider px-4 py-2.5 rounded bg-ink text-bone hover:bg-vermilion transition-colors whitespace-nowrap"
          >
            Open Live Modules →
          </a>
        </div>
      </div>
    </section>
  );
}
