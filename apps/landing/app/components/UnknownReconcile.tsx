"use client";

import { useState, useEffect, useCallback } from "react";
import { useReducedMotion, useInView } from "@/lib/hooks";

type AnimationPhase =
  | "idle"
  | "send-packet"
  | "return-packet"
  | "response-lost"
  | "reconcile-loop"
  | "status-settled"
  | "done";

export default function UnknownReconcile() {
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
      await delay(600);
      setPhase("send-packet");
      await delay(1200);
      setPhase("return-packet");
      await delay(800);
      setPhase("response-lost");
      await delay(1200);
      setPhase("reconcile-loop");
      await delay(1500);
      setPhase("status-settled");
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
    "send-packet",
    "return-packet",
    "response-lost",
    "reconcile-loop",
    "status-settled",
    "done",
  ].indexOf(phase);

  const isDone = phase === "done";
  const packetSending = phase === "send-packet";
  const packetReturning = phase === "return-packet";
  const responseLost = phaseIndex >= 3 || isDone;
  const showReconcile = phaseIndex >= 4 || isDone;
  const showSettled = phaseIndex >= 5 || isDone;

  return (
    <section ref={ref} className="relative bg-carbon py-24 md:py-32 overflow-hidden">
      {/* Section number */}
      <div aria-hidden="true" className="hidden lg:block absolute top-8 left-8 text-bone/10 font-display text-[8rem] md:text-[12rem] leading-none select-none pointer-events-none">
        04
      </div>

      <div className="container-page relative z-10">
        {/* Title */}
        <h2 className="font-display font-900 display-xl uppercase text-bone mb-6">
          UNKNOWN? NEVER RESEND.
        </h2>

        {/* Subtitle */}
        <p className="font-body text-lg text-bone opacity-80 mb-14 md:mb-20 max-w-2xl">
          When a payment response is lost, we check status. We never send it twice.
        </p>

        {/* Diagram */}
        <div className="relative max-w-3xl mx-auto">
          {/* Boxes and line */}
          <div className="flex items-center justify-between gap-2 sm:gap-4">
            {/* Left box */}
            <div className="border border-bone/30 rounded px-2 py-3 sm:p-4 font-mono text-xs sm:text-sm leading-snug text-bone bg-carbon w-[29%] sm:w-auto sm:min-w-[180px] text-center shrink-0">
              Payment Service
            </div>

            {/* Connection line area */}
            <div className="relative flex-1 min-w-0 h-16">
              {/* The line */}
              <svg
                className="absolute inset-0 w-full h-full"
                preserveAspectRatio="none"
                viewBox="0 0 400 64"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                {/* Forward line */}
                <line
                  x1="0"
                  y1="24"
                  x2="380"
                  y2="24"
                  stroke="rgba(255,255,255,0.3)"
                  strokeWidth="1.5"
                />
                {/* Forward arrowhead */}
                <polygon
                  points="380,18 400,24 380,30"
                  fill="rgba(255,255,255,0.3)"
                />
                {/* Return line */}
                <line
                  x1="400"
                  y1="44"
                  x2="20"
                  y2="44"
                  stroke="rgba(255,255,255,0.15)"
                  strokeWidth="1.5"
                  strokeDasharray={responseLost ? "4 4" : "0"}
                />
                {/* Return arrowhead */}
                <polygon
                  points="20,38 0,44 20,50"
                  fill="rgba(255,255,255,0.15)"
                />
              </svg>

              {/* Sending packet (forward) */}
              {packetSending && (
                <div className="absolute top-[18px] left-0 w-3 h-3 rounded-full bg-vermilion animate-[packetForward_1.2s_ease-in-out_forwards] z-10" />
              )}

              {/* Returning packet (dissolves midway) */}
              {packetReturning && (
                <div className="absolute top-[38px] right-0 w-3 h-3 rounded-full bg-vermilion animate-[packetReturn_0.8s_ease-in_forwards] z-10" />
              )}

              {/* Response lost label */}
              {responseLost && (
                <div className="absolute top-[52px] sm:top-[34px] left-1/2 -translate-x-1/2 flex items-center gap-1.5 z-20 sm:bg-carbon sm:px-1.5">
                  <span className="static-flicker text-vermilion font-mono text-xs whitespace-nowrap">
                    Response lost
                  </span>
                </div>
              )}
            </div>

            {/* Right box */}
            <div className="border border-bone/30 rounded px-2 py-3 sm:p-4 font-mono text-xs sm:text-sm leading-snug text-bone bg-carbon w-[29%] sm:w-auto sm:min-w-[180px] text-center shrink-0">
              Bank Gateway
            </div>
          </div>

          {/* Reconcile loop */}
          {showReconcile && (
            <div className="mt-12 flex flex-col items-center gap-4">
              <div className="flex items-center gap-3 animate-pulse">
                {/* Circular arrow icon */}
                <svg
                  className="w-8 h-8 text-verify"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
                <span className="font-mono text-verify text-sm">
                  Check status — don&rsquo;t resend
                </span>
              </div>

              {/* Status badge */}
              {showSettled && (
                <div className="mt-4 border-2 border-verify rounded-lg px-6 py-3 inline-flex items-center gap-2">
                  <span className="font-mono text-verify text-base tracking-wider">
                    STATUS: SETTLED ✓
                  </span>
                </div>
              )}

              {/* Bottom quote */}
              {showSettled && (
                <p className="mt-6 font-accent italic text-lg text-bone/60 text-center max-w-lg">
                  Duplicate payments are worse than late payments.
                </p>
              )}
            </div>
          )}
        </div>
      </div>

    </section>
  );
}
