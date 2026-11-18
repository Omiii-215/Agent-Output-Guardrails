"use client";

import { useState } from "react";
import { useInView } from "@/lib/hooks";
import MoneyParticles from "./MoneyParticles";

const FAILURE_MODES = [
  {
    id: "hallucination",
    tag: "FAILURE 01",
    title: "AI Guesses. Accounts Must Add Up.",
    problem:
      "AI language models work by predicting likely words, not by doing exact sums. Accounts have to balance to the cent. One rounding slip or a swapped line item, and the books stop matching.",
    solution:
      "FinGuard only lets AI read the document. Every sum, total and tax check is done by ordinary code that gives the exact same answer every time. No AI maths.",
    icon: "∑",
  },
  {
    id: "injection",
    tag: "FAILURE 02",
    title: "Hidden Instructions in Documents",
    problem:
      "Invoices and bank statements come from outside, so they can’t be trusted. Attackers hide text you can’t see, like white text on white, telling the AI to ‘ignore the limits and wire the money’. A plain AI agent may just do it.",
    solution:
      "Every file is checked before anything reads it. The AI can only fill in a fixed form, and each value must match a spot in the document. Hidden instructions put the file on hold straight away.",
    icon: "⚡",
  },
  {
    id: "self-approval",
    tag: "FAILURE 03",
    title: "AI Approving Its Own Payments",
    problem:
      "AI agents are built to act. Give one a payment tool and it may assume it’s allowed, skip spending limits, or approve the very payment it set up, with no person looking.",
    solution:
      "The system won’t let whoever prepared a payment, person or AI, approve it too. A different person approves the exact payment, and any later change cancels their approval.",
    icon: "⚖",
  },
  {
    id: "silent-bypass",
    tag: "FAILURE 04",
    title: "An Error That Lets Payments Through",
    problem:
      "Many systems ‘fail open’: if a checking service times out or hits an error, they let the payment through so nothing gets stuck.",
    solution:
      "FinGuard ‘fails closed’. If a check crashes, times out or errors, the payment stays on hold. An error is never a yes.",
    icon: "🚫",
  },
  {
    id: "double-spend",
    tag: "FAILURE 05",
    title: "Lost Replies and Double Payments",
    problem:
      "If the bank connection drops before the bank replies, nobody knows whether the payment went through. A simple agent sends it again, and the supplier gets $50,000 twice.",
    solution:
      "Money is set aside before a payment goes out, and each payment can only be sent once. If the reply is lost, FinGuard asks the bank what happened instead of sending it again.",
    icon: "🔄",
  },
];

export default function ProblemStatement() {
  const [ref, inView] = useInView({ threshold: 0.1, once: true });
  const [activeTab, setActiveTab] = useState<"raw" | "finguard">("finguard");
  const [selectedFailure, setSelectedFailure] = useState(0);

  return (
    <section
      ref={ref as React.RefObject<HTMLElement>}
      className="bg-carbon text-bone py-24 md:py-32 border-b border-ledger/20 relative overflow-hidden"
      id="problem"
    >
      {/* Background ledger grid effect & finance particles */}
      <div className="absolute inset-0 opacity-5 pointer-events-none ledger-lines" />
      <MoneyParticles theme="dark" count={24} />

      <div className="container-page relative z-10">
        {/* Section Header */}
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 lg:gap-12 mb-16 pb-8 border-b border-bone/10">
          <div>
            <span className="font-mono text-xs uppercase tracking-widest text-vermilion">
              The Problem
            </span>
            <h2 className="font-display font-[900] display-xl uppercase text-bone mt-3">
              The Financial AI Paradox.
              <br />
              <span className="text-vermilion">Fast at Reading.</span>{" "}
              <span>Dangerous at Moving Money.</span>
            </h2>
          </div>
          <p className="font-body text-base md:text-lg text-bone/60 max-w-md leading-relaxed">
            AI makes educated guesses. Finance needs exact answers, and every payment is legally binding. Letting AI move money with no firm rules in the way is a risk no finance team should take.
          </p>
        </div>

        {/* Interactive Comparison Sandbox */}
        <div className="mb-20 bg-bone/5 border border-bone/20 rounded-xl p-6 md:p-8 backdrop-blur-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-bone/10 gap-4">
            <div>
              <span className="font-mono text-xs text-bone/40 uppercase">
                Side-by-Side Comparison
              </span>
              <h3 className="font-display font-bold text-2xl uppercase text-bone mt-1">
                Where Plain AI Fails, and How FinGuard Stops It
              </h3>
            </div>
            {/* Toggle Switch */}
            <div className="flex bg-ink border border-bone/20 rounded-lg p-1 self-start sm:self-auto">
              <button
                onClick={() => setActiveTab("raw")}
                className={`px-4 py-2 text-xs font-mono uppercase font-bold rounded transition-all duration-200 ${
                  activeTab === "raw"
                    ? "bg-vermilion text-white shadow-md scale-102"
                    : "text-bone/60 hover:text-bone"
                }`}
              >
                ⚠ Plain AI Agent (No Controls)
              </button>
              <button
                onClick={() => setActiveTab("finguard")}
                className={`px-4 py-2 text-xs font-mono uppercase font-bold rounded transition-all duration-200 ${
                  activeTab === "finguard"
                    ? "bg-verify text-ink shadow-md scale-102"
                    : "text-bone/60 hover:text-bone"
                }`}
              >
                ✓ With FinGuard (Firm Rules)
              </button>
            </div>
          </div>

          {/* Tab content view */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6">
            {activeTab === "raw" ? (
              <>
                <div className="bg-vermilion/10 border-2 border-vermilion/40 rounded-lg p-5">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-xs text-vermilion font-bold">
                      INPUT RISK
                    </span>
                    <span className="text-xl">⚠️</span>
                  </div>
                  <h4 className="font-display font-bold text-lg uppercase text-bone">
                    Reads Documents As-Is
                  </h4>
                  <p className="font-body text-sm text-bone/70 mt-2">
                    The AI reads PDFs straight in. Hidden text can change what it does, or swap the bank details of who gets paid.
                  </p>
                  <div className="mt-4 pt-3 border-t border-vermilion/20 font-mono text-[11px] text-vermilion">
                    Result: an attacker redirects the payment
                  </div>
                </div>

                <div className="bg-vermilion/10 border-2 border-vermilion/40 rounded-lg p-5">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-xs text-vermilion font-bold">
                      LOGIC DRIFT
                    </span>
                    <span className="text-xl">🎲</span>
                  </div>
                  <h4 className="font-display font-bold text-lg uppercase text-bone">
                    Guesswork Maths and Decisions
                  </h4>
                  <p className="font-body text-sm text-bone/70 mt-2">
                    The AI can make up a discount, round a balance, or skip a rule when things get complicated. Errors slip through without anyone noticing.
                  </p>
                  <div className="mt-4 pt-3 border-t border-vermilion/20 font-mono text-[11px] text-vermilion">
                    Result: $42,500 paid without approval
                  </div>
                </div>

                <div className="bg-vermilion/10 border-2 border-vermilion/40 rounded-lg p-5">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-xs text-vermilion font-bold">
                      EXECUTION FAILURE
                    </span>
                    <span className="text-xl">💥</span>
                  </div>
                  <h4 className="font-display font-bold text-lg uppercase text-bone">
                    One Agent Does Everything
                  </h4>
                  <p className="font-body text-sm text-bone/70 mt-2">
                    The agent sends payments to the bank with no second person approving. When the connection drops, it tries again and pays twice.
                  </p>
                  <div className="mt-4 pt-3 border-t border-vermilion/20 font-mono text-[11px] text-vermilion">
                    Result: paid twice, with no record
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="bg-verify/10 border-2 border-verify/50 rounded-lg p-5">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-xs text-verify font-bold">
                      LAYER 1: CHECK FILES
                    </span>
                    <span className="text-xl">🛡️</span>
                  </div>
                  <h4 className="font-display font-bold text-lg uppercase text-bone">
                    AI Reads, and Shows Its Sources
                  </h4>
                  <p className="font-body text-sm text-bone/70 mt-2">
                    Each file is fingerprinted and held for checking. The AI can only fill in a fixed form, and every value must point to where it appears in the document. Hidden instructions get flagged.
                  </p>
                  <div className="mt-4 pt-3 border-t border-verify/30 font-mono text-[11px] text-verify">
                    Guarantee: every value traced to the document
                  </div>
                </div>

                <div className="bg-verify/10 border-2 border-verify/50 rounded-lg p-5">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-xs text-verify font-bold">
                      LAYER 2: RULES
                    </span>
                    <span className="text-xl">🔒</span>
                  </div>
                  <h4 className="font-display font-bold text-lg uppercase text-bone">
                    Firm Rules, Exact Sums
                  </h4>
                  <p className="font-body text-sm text-bone/70 mt-2">
                    The invoice is locked so it can’t change after checking. Plain code, not AI, applies your rules. If a check crashes, the payment is held, never waved through.
                  </p>
                  <div className="mt-4 pt-3 border-t border-verify/30 font-mono text-[11px] text-verify">
                    Guarantee: exact sums, errors stop payment
                  </div>
                </div>

                <div className="bg-verify/10 border-2 border-verify/50 rounded-lg p-5">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-xs text-verify font-bold">
                      LAYER 3: PAYING
                    </span>
                    <span className="text-xl">🏛️</span>
                  </div>
                  <h4 className="font-display font-bold text-lg uppercase text-bone">
                    Two People, One Payment
                  </h4>
                  <p className="font-body text-sm text-bone/70 mt-2">
                    Whoever asks for a payment can’t approve it. The approver signs off on the exact payment, and the money is set aside first. If the bank goes quiet, we check. We never resend.
                  </p>
                  <div className="mt-4 pt-3 border-t border-verify/30 font-mono text-[11px] text-verify">
                    Guarantee: a record no one can quietly edit
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* 5 Fatal Failure Modes Accordion / Selector */}
        <div>
          <div className="mb-6">
            <span className="font-mono text-xs uppercase tracking-widest text-bone/50">
              5 Ways AI Can Go Wrong With Money
            </span>
            <h3 className="font-display font-bold text-3xl uppercase text-bone mt-1">
              Pick one to see the risk and the fix:
            </h3>
          </div>

          {/* Tabs for Failure Modes */}
          <div className="flex gap-2 overflow-x-auto pb-4 scrollbar-hide">
            {FAILURE_MODES.map((mode, i) => (
              <button
                key={mode.id}
                onClick={() => setSelectedFailure(i)}
                className={`px-4 py-3 rounded-lg border text-left flex-shrink-0 transition-all duration-200 ${
                  selectedFailure === i
                    ? "bg-bone text-ink border-bone shadow-lg scale-102"
                    : "bg-ink/40 border-bone/20 text-bone/60 hover:text-bone hover:border-bone/40"
                }`}
              >
                <div className="font-mono text-[11px] tracking-wider uppercase opacity-70">
                  {mode.tag}
                </div>
                <div className="font-display font-bold text-sm uppercase mt-0.5 whitespace-nowrap">
                  {mode.title}
                </div>
              </button>
            ))}
          </div>

          {/* Active Failure Mode Card */}
          <div className="mt-4 bg-ink/70 border-2 border-bone/30 rounded-xl p-8 transition-all duration-300">
            <div className="flex items-start gap-4">
              <span className="text-4xl p-3 bg-bone/10 rounded-lg">
                {FAILURE_MODES[selectedFailure].icon}
              </span>
              <div className="flex-1">
                <span className="font-mono text-xs text-vermilion uppercase tracking-widest font-bold">
                  {FAILURE_MODES[selectedFailure].tag}
                </span>
                <h4 className="font-display font-[900] text-3xl md:text-4xl uppercase text-bone mt-1">
                  {FAILURE_MODES[selectedFailure].title}
                </h4>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-8 pt-6 border-t border-bone/10">
              <div className="bg-vermilion/5 border border-vermilion/30 rounded-lg p-5">
                <span className="font-mono text-xs text-vermilion uppercase font-bold tracking-wider block mb-2">
                  ✕ The Risk With Plain AI
                </span>
                <p className="font-body text-sm text-bone/80 leading-relaxed">
                  {FAILURE_MODES[selectedFailure].problem}
                </p>
              </div>

              <div className="bg-verify/5 border border-verify/30 rounded-lg p-5">
                <span className="font-mono text-xs text-verify uppercase font-bold tracking-wider block mb-2">
                  ✓ How FinGuard Stops It
                </span>
                <p className="font-body text-sm text-bone/80 leading-relaxed">
                  {FAILURE_MODES[selectedFailure].solution}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
