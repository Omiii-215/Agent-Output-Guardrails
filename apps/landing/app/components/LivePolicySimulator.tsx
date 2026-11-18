"use client";

import { useState } from "react";
import { useInView } from "@/lib/hooks";

export default function LivePolicySimulator() {
  const [ref, inView] = useInView(0.15);
  const [invoiceAmount, setInvoiceAmount] = useState(12450);
  const [simulateCrash, setSimulateCrash] = useState(false);
  const [injectAttack, setInjectAttack] = useState(false);
  const [selfApproveAttempt, setSelfApproveAttempt] = useState(false);

  // Policy rules:
  // 1. Max single approval limit: $25,000
  // 2. No prompt injection
  // 3. No policy evaluator crash
  // 4. Proposer cannot approve

  const limitExceeded = invoiceAmount > 25000;
  const isBlocked = limitExceeded || simulateCrash || injectAttack || selfApproveAttempt;

  let blockReason = "";
  if (simulateCrash) {
    blockReason = "THE RULE CHECK CRASHED, SO THE PAYMENT IS HELD. AN ERROR IS NEVER A YES.";
  } else if (injectAttack) {
    blockReason = "HIDDEN INSTRUCTIONS FOUND IN THE PDF. THE FILE IS ON HOLD.";
  } else if (selfApproveAttempt) {
    blockReason = "YOU CAN’T APPROVE A PAYMENT YOU ASKED FOR.";
  } else if (limitExceeded) {
    blockReason = "OVER THE $25,000 LIMIT. TWO APPROVALS NEEDED.";
  }

  return (
    <section
      ref={ref as React.RefObject<HTMLElement>}
      className="bg-bone py-24 md:py-32 border-b border-ledger"
      id="simulator"
    >
      <div className="container-page">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="font-mono text-xs uppercase tracking-widest text-vermilion font-bold">
            Try It Yourself
          </span>
          <h2 className="font-display font-[900] display-xl uppercase text-ink mt-3">
            Test the Rules Live.
          </h2>
          <p className="font-accent italic text-xl text-ink/75 mt-4">
            Switch on the tricky cases below and watch FinGuard stop them before any money moves.
          </p>
        </div>

        {/* Simulator Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Controls Panel (Left, 5 cols) */}
          <div className="lg:col-span-5 bg-white border-2 border-ink rounded-xl p-6 shadow-xl space-y-6">
            <div className="border-b border-ledger pb-3">
              <span className="font-mono text-xs text-ink/40 uppercase">
                Step 1: Set the Payment
              </span>
              <h3 className="font-display font-bold text-xl uppercase text-ink">
                Sample Invoice Payment
              </h3>
            </div>

            {/* Amount Slider */}
            <div>
              <div className="flex justify-between items-baseline mb-2">
                <label className="font-mono text-xs uppercase font-bold text-ink">
                  Invoice Amount:
                </label>
                <span className="font-display text-2xl font-[900] text-ink">
                  ${invoiceAmount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </span>
              </div>
              <input
                type="range"
                min={2000}
                max={50000}
                step={500}
                value={invoiceAmount}
                onChange={(e) => setInvoiceAmount(Number(e.target.value))}
                className="w-full h-2 bg-bone rounded-lg appearance-none cursor-pointer accent-vermilion"
              />
              <div className="flex justify-between font-mono text-[11px] text-ink/40 mt-1">
                <span>$2,000 (Tier 1)</span>
                <span>$25,000 (Approval Limit)</span>
                <span>$50,000 (Tier 3)</span>
              </div>
            </div>

            {/* Edge-Case Toggles */}
            <div className="space-y-3 pt-2">
              <span className="font-mono text-xs uppercase font-bold text-ink/60 block">
                Step 2: Add a Problem
              </span>

              {/* Toggle 1: Policy Crash */}
              <button
                onClick={() => setSimulateCrash((v) => !v)}
                className={`w-full flex items-center justify-between p-3 rounded-lg border-2 text-left transition-all ${
                  simulateCrash
                    ? "bg-vermilion/10 border-vermilion text-vermilion font-bold"
                    : "bg-bone/40 border-ledger text-ink hover:border-ink/40"
                }`}
              >
                <div>
                  <div className="text-xs font-mono uppercase">
                    Test 1: The Rule Check Crashes
                  </div>
                  <div className="text-[11px] font-body text-ink/60 mt-0.5">
                    A service times out in the middle of a check
                  </div>
                </div>
                <span className="text-sm font-mono font-bold">
                  {simulateCrash ? "[SIMULATING CRASH]" : "[ARM]"}
                </span>
              </button>

              {/* Toggle 2: Prompt Injection */}
              <button
                onClick={() => setInjectAttack((v) => !v)}
                className={`w-full flex items-center justify-between p-3 rounded-lg border-2 text-left transition-all ${
                  injectAttack
                    ? "bg-vermilion/10 border-vermilion text-vermilion font-bold"
                    : "bg-bone/40 border-ledger text-ink hover:border-ink/40"
                }`}
              >
                <div>
                  <div className="text-xs font-mono uppercase">
                    Test 2: Hidden Instructions
                  </div>
                  <div className="text-[11px] font-body text-ink/60 mt-0.5">
                    Someone hid text in the PDF footer
                  </div>
                </div>
                <span className="text-sm font-mono font-bold">
                  {injectAttack ? "[ATTACK ACTIVE]" : "[ARM]"}
                </span>
              </button>

              {/* Toggle 3: Self-Approval */}
              <button
                onClick={() => setSelfApproveAttempt((v) => !v)}
                className={`w-full flex items-center justify-between p-3 rounded-lg border-2 text-left transition-all ${
                  selfApproveAttempt
                    ? "bg-vermilion/10 border-vermilion text-vermilion font-bold"
                    : "bg-bone/40 border-ledger text-ink hover:border-ink/40"
                }`}
              >
                <div>
                  <div className="text-xs font-mono uppercase">
                    Test 3: Approving Your Own Payment
                  </div>
                  <div className="text-[11px] font-body text-ink/60 mt-0.5">
                    One person tries to do both steps
                  </div>
                </div>
                <span className="text-sm font-mono font-bold">
                  {selfApproveAttempt ? "[BYPASS ATTEMPT]" : "[ARM]"}
                </span>
              </button>
            </div>
          </div>

          {/* Engine Output Terminal (Right, 7 cols) */}
          <div className="lg:col-span-7 bg-ink text-bone border-2 border-ledger rounded-xl p-6 shadow-2xl relative overflow-hidden">
            <div className="flex items-center justify-between pb-4 border-b border-bone/10">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-vermilion/80" />
                <span className="w-3 h-3 rounded-full bg-verify/80" />
                <span className="font-mono text-xs uppercase text-bone/60 ml-2">
                  finguard // rule checker
                </span>
              </div>
              <div className="font-mono text-xs text-bone/40">
                COMPANY: acme
              </div>
            </div>

            {/* Live Status Header */}
            <div className="my-6 p-4 rounded-lg bg-carbon border border-bone/10 flex items-center justify-between">
              <div>
                <span className="font-mono text-[11px] text-bone/40 uppercase tracking-widest block">
                  TRANSACTION STATE
                </span>
                <span
                  className={`font-display text-2xl font-[900] uppercase tracking-wide ${
                    isBlocked ? "text-vermilion" : "text-verify"
                  }`}
                >
                  {isBlocked ? "ACTION BLOCKED / HOLD" : "PROPOSAL VERIFIED & LOCKED"}
                </span>
              </div>
              <div>
                <span
                  className={`stamp text-xs ${
                    isBlocked ? "stamp-vermilion" : "stamp-verify"
                  }`}
                >
                  {isBlocked ? "ON HOLD" : "CHECKS PASSED"}
                </span>
              </div>
            </div>

            {/* Rule Checklist with live animated status */}
            <div className="space-y-3 font-mono text-xs">
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3 px-2.5 py-2 rounded bg-bone/5">
                <span className="text-bone/70">1. File Check & Virus Scan</span>
                <span className="text-verify font-bold">✓ PASS [sha256:4b91…e8]</span>
              </div>

              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3 px-2.5 py-2 rounded bg-bone/5">
                <span className="text-bone/70">2. Hidden Instruction Scan</span>
                {injectAttack ? (
                  <span className="text-vermilion font-bold animate-pulse">
                    ✕ FLAGGED [hidden instruction]
                  </span>
                ) : (
                  <span className="text-verify font-bold">✓ CLEAN [nothing found]</span>
                )}
              </div>

              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3 px-2.5 py-2 rounded bg-bone/5">
                <span className="text-bone/70">3. Spending Rules</span>
                {simulateCrash ? (
                  <span className="text-vermilion font-bold animate-pulse">
                    ✕ HELD [the check crashed]
                  </span>
                ) : limitExceeded ? (
                  <span className="text-vermilion font-bold">
                    ✕ TOO HIGH [over $25,000]
                  </span>
                ) : (
                  <span className="text-verify font-bold">
                    ✓ OK [under $25,000]
                  </span>
                )}
              </div>

              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3 px-2.5 py-2 rounded bg-bone/5">
                <span className="text-bone/70">4. Second Person Approves</span>
                {selfApproveAttempt ? (
                  <span className="text-vermilion font-bold animate-pulse">
                    ✕ REJECTED [can’t approve your own]
                  </span>
                ) : (
                  <span className="text-verify font-bold">
                    ✓ REQUIRED [different approver]
                  </span>
                )}
              </div>

              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3 px-2.5 py-2 rounded bg-bone/5">
                <span className="text-bone/70">5. Money Set Aside</span>
                <span className="text-verify font-bold">✓ RESERVED [can’t pay twice]</span>
              </div>
            </div>

            {/* Reason Banner if Blocked */}
            {isBlocked && (
              <div className="mt-6 p-4 rounded bg-vermilion/15 border border-vermilion/40 text-vermilion font-mono text-xs leading-relaxed animate-fade-in">
                <span className="font-bold block mb-1">STOPPED BY A RULE:</span>
                {blockReason}
              </div>
            )}

            {!isBlocked && (
              <div className="mt-6 p-4 rounded bg-verify/15 border border-verify/40 text-verify font-mono text-xs leading-relaxed">
                <span className="font-bold block mb-1">PAYMENT FINGERPRINT CREATED:</span>
                <span className="break-all">sha256:9c1a084ef71d3298a44b11f62d08c50e29207da</span> · Ready for the approver.
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
