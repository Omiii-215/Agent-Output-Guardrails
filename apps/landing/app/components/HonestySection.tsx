"use client";

import { useInView } from "@/lib/hooks";

export default function HonestySection() {
  const [ref, inView] = useInView(0.15);

  const GUARANTEES = [
    {
      title: "Tenant Isolation with RLS",
      code: "GUARANTEE 01",
      detail:
        "Every database query runs under PostgreSQL Row-Level Security. Attempted cross-tenant access returns an immediate HTTP 404. Zero cross-tenant data leaks.",
    },
    {
      title: "Fail-Closed Execution (Crash ≠ Pass)",
      code: "GUARANTEE 02",
      detail:
        "If a policy evaluator throws an exception, times out, or runs out of memory, the payment is held. In financial infrastructure, a failure is never an approval.",
    },
    {
      title: "Cryptographic Maker-Checker",
      code: "GUARANTEE 03",
      detail:
        "The actor who proposes or extracts an invoice is mathematically forbidden from approving it. Approvers sign off on an immutable server-side SHA-256 digest.",
    },
    {
      title: "Zero Double-Spend State Machine",
      code: "GUARANTEE 04",
      detail:
        "Concurreny holds reserve ledger balance before execution. If a bank API times out, status is marked UNKNOWN and probed. Retries are strictly forbidden.",
    },
    {
      title: "Tamper-Evident Chained Audit",
      code: "GUARANTEE 05",
      detail:
        "Every event, field extraction, user comment, and approval is written to an append-only ledger with cryptographic hash chaining (prev_hash → current_hash).",
    },
    {
      title: "Bounded Schema with Citations",
      code: "GUARANTEE 06",
      detail:
        "AI output is schema-validated and every extracted dollar amount, vendor name, and line item is checked against source text coordinates before being shown.",
    },
  ];

  return (
    <section
      ref={ref as React.RefObject<HTMLElement>}
      className="bg-bone perforated-top perforated-bottom py-24 md:py-32 lg:py-36 relative overflow-hidden"
      id="guarantees"
    >
      <div className="max-w-6xl mx-auto px-4 md:px-8 relative z-10">
        {/* Big headline */}
        <div className="text-center mb-16">
          <span className="font-mono text-xs uppercase tracking-widest text-vermilion font-bold">
            Deterministic Financial Engineering
          </span>
          <h2
            className={`font-display font-[900] text-5xl sm:text-7xl md:text-8xl lg:text-9xl uppercase text-ink mt-2 leading-[0.9] transition-all duration-700 ${
              inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
            }`}
          >
            Not a Toy Demo.
            <br />
            A Working Financial Runtime.
          </h2>
          <p className="font-accent italic text-xl md:text-2xl text-ink/75 max-w-2xl mx-auto mt-6">
            Finance cannot run on probabilistic chat prompts. FinGuard is built as
            an enforceable, deterministic control plane for enterprise money.
          </p>
        </div>

        {/* Legal Seal Box */}
        <div
          className={`relative max-w-4xl mx-auto transition-all duration-700 delay-200 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
        >
          <div className="border-4 border-ink bg-white p-8 md:p-12 shadow-2xl relative">
            <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b-2 border-ledger gap-4">
              <div>
                <span className="font-mono text-xs text-ink/40 uppercase tracking-widest">
                  ENGINE SPECIFICATION // REVISION 2026.11
                </span>
                <h3 className="font-display font-[900] text-3xl uppercase text-ink mt-1">
                  The FinGuard Invariant Guarantees
                </h3>
              </div>
              <div className="font-mono text-xs text-ink/60 bg-bone px-3 py-1.5 rounded border border-ledger self-start md:self-auto">
                STATUS: PRODUCTION RUNTIME
              </div>
            </div>

            {/* 6 Hard Guarantees Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
              {GUARANTEES.map((g) => (
                <div
                  key={g.code}
                  className="border-l-2 border-ink pl-4 py-1 hover:border-vermilion transition-colors duration-200"
                >
                  <span className="font-mono text-[10px] uppercase text-vermilion font-bold tracking-wider">
                    {g.code}
                  </span>
                  <h4 className="font-display font-bold text-lg uppercase text-ink mt-0.5">
                    {g.title}
                  </h4>
                  <p className="font-body text-xs text-ink/70 mt-1 leading-relaxed">
                    {g.detail}
                  </p>
                </div>
              ))}
            </div>

            {/* Bottom Statement */}
            <div className="mt-8 pt-6 border-t-2 border-ledger flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <p className="font-body text-xs text-ink/60 max-w-lg">
                Payments and ledger movements execute through verified,
                tamper-evident state machines. Zero probabilistic drift reaches
                your banking layer.
              </p>
              <span className="font-mono text-xs text-verify font-bold uppercase tracking-wider whitespace-nowrap">
                ✓ ALL CONTROLS VERIFIED
              </span>
            </div>

            {/* Official Green Stamp */}
            <div className="stamp stamp-verify absolute -top-4 -right-4 md:-top-6 md:-right-6 rotate-12 select-none shadow-lg text-sm md:text-base font-[900] bg-white">
              VERIFIED ARCHITECTURE
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
