"use client";

import { useState, useEffect, useCallback } from "react";
import { useReducedMotion, useInView } from "@/lib/hooks";

type AnimationPhase =
  | "idle"
  | "click-jamie"
  | "shake-jamie"
  | "stamp-denied"
  | "activate-morgan"
  | "click-morgan"
  | "stamp-approved"
  | "lock-digest"
  | "done";

export default function MakerChecker() {
  const prefersReducedMotion = useReducedMotion();
  const [ref, isInView] = useInView({ threshold: 0.3 });
  const [phase, setPhase] = useState<AnimationPhase>("idle");
  const [hasPlayed, setHasPlayed] = useState(false);

  const runSequence = useCallback(() => {
    if (hasPlayed) return;
    setHasPlayed(true);

    if (prefersReducedMotion) {
      setPhase("done");
      return;
    }

    const timers: ReturnType<typeof setTimeout>[] = [];
    const delay = (ms: number) =>
      new Promise<void>((resolve) => {
        timers.push(setTimeout(resolve, ms));
      });

    (async () => {
      await delay(1000);
      setPhase("click-jamie");
      await delay(300);
      setPhase("shake-jamie");
      await delay(600);
      setPhase("stamp-denied");
      await delay(1500);
      setPhase("activate-morgan");
      await delay(600);
      setPhase("click-morgan");
      await delay(400);
      setPhase("stamp-approved");
      await delay(800);
      setPhase("lock-digest");
      await delay(600);
      setPhase("done");
    })();

    return () => timers.forEach(clearTimeout);
  }, [hasPlayed, prefersReducedMotion]);

  useEffect(() => {
    if (isInView && !hasPlayed) {
      const cleanup = runSequence();
      return cleanup;
    }
  }, [isInView, hasPlayed, runSequence]);

  const phaseIndex = [
    "idle",
    "click-jamie",
    "shake-jamie",
    "stamp-denied",
    "activate-morgan",
    "click-morgan",
    "stamp-approved",
    "lock-digest",
    "done",
  ].indexOf(phase);

  const isDone = phase === "done";
  const showDeniedStamp = phaseIndex >= 3 || isDone;
  const morganActive = phaseIndex >= 4 || isDone;
  const morganClicked = phaseIndex >= 5 || isDone;
  const showApprovedStamp = phaseIndex >= 6 || isDone;
  const digestLocked = phaseIndex >= 7 || isDone;

  return (
    <section ref={ref} className="relative bg-bone py-24 md:py-32 overflow-hidden">
      {/* Section number */}
      <div aria-hidden="true" className="hidden lg:block absolute top-8 left-8 text-ledger/20 font-display text-[8rem] md:text-[12rem] leading-none select-none pointer-events-none">
        03
      </div>

      <div className="container-page relative z-10">
        {/* Title */}
        <h2 className="font-display font-900 display-xl uppercase text-ink mb-6">
          THE PERSON WHO PROPOSES{" "}
          <span className="text-vermilion">CAN&rsquo;T</span> APPROVE.
        </h2>

        {/* Subtitle */}
        <p className="font-body text-lg max-w-2xl text-ink mb-16">
          Maker-checker. Because &ldquo;I&rsquo;ll just approve my own
          thing&rdquo; is how money goes missing.
        </p>

        {/* Split-screen Demo */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
          {/* LEFT panel — Jamie (Proposer) */}
          <div className="relative bg-bone border-2 border-ink rounded-lg p-8 overflow-hidden">
            {/* Avatar */}
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-full bg-ink text-bone flex items-center justify-center font-display font-900 text-sm">
                JD
              </div>
              <span className="font-mono text-sm text-ink">
                Jamie — Proposer
              </span>
            </div>

            {/* Payment details */}
            <div className="space-y-2 mb-8">
              <p className="font-body text-ink">Payment to Acme Corp</p>
              <p className="font-mono text-ink">Amount: $12,450.00</p>
              <p className="font-mono text-xs text-ink/50">
                {digestLocked ? (
                  <>🔒 sha256:d4a1…8bc2 LOCKED</>
                ) : (
                  <>Digest: sha256:d4a1…8bc2</>
                )}
              </p>
            </div>

            {/* Button */}
            <button
              className={`bg-vermilion text-white px-6 py-3 font-display uppercase text-sm rounded transition-transform ${
                phase === "click-jamie"
                  ? "scale-95"
                  : ""
              } ${
                phase === "shake-jamie" ? "button-deny" : ""
              }`}
              aria-disabled
              tabIndex={-1}
            >
              Approve My Own Payment
            </button>

            {/* Denied stamp */}
            {showDeniedStamp && (
              <div
                className={`mt-6 flex justify-start pointer-events-none lg:mt-0 lg:absolute lg:right-6 lg:bottom-6 ${
                  !prefersReducedMotion && phase === "stamp-denied"
                    ? "stamp-slam"
                    : ""
                }`}
              >
                <div className="border-4 border-vermilion text-vermilion font-display font-900 uppercase text-xl md:text-2xl px-6 py-3 -rotate-6 bg-bone/90 rounded text-center leading-tight">
                  INDEPENDENT
                  <br />
                  APPROVAL REQUIRED
                </div>
              </div>
            )}
          </div>

          {/* RIGHT panel — Morgan (Approver) */}
          <div className="relative bg-bone border-2 border-ink rounded-lg p-8 overflow-hidden">
            {/* Avatar */}
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-full bg-ink text-bone flex items-center justify-center font-display font-900 text-sm">
                MC
              </div>
              <span className="font-mono text-sm text-ink">
                Morgan — Approver
              </span>
            </div>

            {/* Payment details */}
            <div className="space-y-2 mb-8">
              <p className="font-body text-ink">Payment to Acme Corp</p>
              <p className="font-mono text-ink">Amount: $12,450.00</p>
              <p className="font-mono text-xs text-ink/50">
                {digestLocked ? (
                  <>🔒 sha256:d4a1…8bc2 LOCKED</>
                ) : (
                  <>Digest: sha256:d4a1…8bc2</>
                )}
              </p>
            </div>

            {/* Button */}
            <button
              className={`px-6 py-3 font-display uppercase text-sm rounded transition-all duration-300 ${
                morganActive
                  ? "bg-verify text-ink opacity-100"
                  : "bg-ink text-bone opacity-40"
              } ${morganClicked && !showApprovedStamp ? "scale-95" : ""}`}
              aria-disabled
              tabIndex={-1}
            >
              Approve Payment
            </button>

            {/* Approved stamp */}
            {showApprovedStamp && (
              <div
                className={`mt-6 flex justify-start pointer-events-none lg:mt-0 lg:absolute lg:right-6 lg:bottom-6 ${
                  !prefersReducedMotion && phase === "stamp-approved"
                    ? "stamp-slam"
                    : ""
                }`}
              >
                <div className="border-4 border-verify text-verify font-display font-900 uppercase text-3xl md:text-4xl px-8 py-4 -rotate-6 bg-bone/90 rounded">
                  APPROVED
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
