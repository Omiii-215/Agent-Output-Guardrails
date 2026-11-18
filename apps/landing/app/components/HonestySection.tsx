"use client";

import { useInView } from "@/lib/hooks";

export default function HonestySection() {
  const [ref, inView] = useInView(0.15);

  const GUARANTEES = [
    {
      title: "Each Company’s Data Stays Separate",
      code: "GUARANTEE 01",
      detail:
        "Every database query is limited to one company. Asking for another company’s data just returns ‘not found’.",
    },
    {
      title: "An Error Is Never a Yes",
      code: "GUARANTEE 02",
      detail:
        "If a check fails, times out or runs out of memory, the payment is held. In finance, a failure must never count as approval.",
    },
    {
      title: "Two People for Every Payment",
      code: "GUARANTEE 03",
      detail:
        "Whoever prepares or proposes a payment can’t approve it. The approver signs off on one exact, locked version of the payment.",
    },
    {
      title: "Never Paid Twice",
      code: "GUARANTEE 04",
      detail:
        "Money is set aside before a payment goes out. If the bank doesn’t reply, the payment is marked unknown and checked. It is never resent.",
    },
    {
      title: "A Record No One Can Quietly Change",
      code: "GUARANTEE 05",
      detail:
        "Every event, value read, comment and approval goes into a log that can only grow. Each entry is linked to the one before, so any edit shows.",
    },
    {
      title: "AI Has to Show Its Sources",
      code: "GUARANTEE 06",
      detail:
        "AI fills in a fixed form, and every amount, supplier name and line item is checked against the document before anyone sees it.",
    },
  ];

  return (
    <section
      ref={ref as React.RefObject<HTMLElement>}
      className="bg-bone perforated-top perforated-bottom py-24 md:py-32 lg:py-36 relative overflow-hidden"
      id="guarantees"
    >
      <div className="container-page relative z-10">
        {/* Big headline */}
        <div className="text-center mb-16">
          <span className="font-mono text-xs uppercase tracking-widest text-vermilion font-bold">
            Built for Real Money
          </span>
          <h2
            className={`font-display font-[900] display-2xl uppercase text-ink mt-3 transition-all duration-700 ${
              inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
            }`}
          >
            Not a Toy Demo.
            <br />
            A Working Financial System.
          </h2>
          <p className="font-accent italic text-xl md:text-2xl text-ink/75 max-w-2xl mx-auto mt-6">
            Finance can’t run on chatbot guesses. FinGuard is a set of firm controls that every payment has to pass.
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
                  WHAT WE PROMISE
                </span>
                <h3 className="font-display font-[900] text-3xl uppercase text-ink mt-1">
                  Six Things That Always Hold
                </h3>
              </div>
              <div className="font-mono text-xs text-ink/60 bg-bone px-3 py-1.5 rounded border border-ledger self-start md:self-auto">
                ENFORCED IN CODE
              </div>
            </div>

            {/* 6 Hard Guarantees Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
              {GUARANTEES.map((g) => (
                <div
                  key={g.code}
                  className="border-l-2 border-ink pl-4 py-1 hover:border-vermilion transition-colors duration-200"
                >
                  <span className="font-mono text-[11px] uppercase text-vermilion font-bold tracking-wider">
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
                Payments only move through checked, recorded steps. AI guesswork never reaches your bank.
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
