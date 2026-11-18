"use client";

import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { PIPELINE_STAGES } from "@/lib/constants";
import { useReducedMotion } from "@/lib/hooks";

/* ── Digest hash animation helpers ── */
const FINAL_HASH = "d4a1e7b3c09f28a16d5e3b7f8c2a9d0e4f17";
const HEX_CHARS = "0123456789abcdef";

function getPartialReveal(progress: number): {
  hash: string;
  lockedCount: number;
} {
  const len = FINAL_HASH.length;
  const lockedCount = Math.floor(progress * len);
  const chars: string[] = [];
  for (let i = 0; i < len; i++) {
    if (i < lockedCount) {
      chars.push(FINAL_HASH[i]);
    } else {
      chars.push(HEX_CHARS[Math.floor(Math.random() * HEX_CHARS.length)]);
    }
  }
  return { hash: chars.join(""), lockedCount };
}

/* ── Main Component ── */
export default function Pipeline() {
  const reducedMotion = useReducedMotion();
  const sectionRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);

  const [progress, setProgress] = useState(0);
  // Start with FINAL_HASH on both server and client — identical, no hydration mismatch
  const [digestHash, setDigestHash] = useState(FINAL_HASH);
  const [digestLocked, setDigestLocked] = useState(false);
  const [mounted, setMounted] = useState(false);
  const rafRef = useRef<number>(0);

  // Mark mounted — this fires only on client, after hydration is complete
  useEffect(() => {
    setMounted(true);
  }, []);

  const stageCount = PIPELINE_STAGES.length;
  const approvalIndex = PIPELINE_STAGES.findIndex(
    (s) => s.id === "approval"
  );
  const digestUnlockProgress = approvalIndex >= 0 ? (approvalIndex + 1) / stageCount : 0.55;

  /* ── Scroll handler ── */
  const handleScroll = useCallback(() => {
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0;
      const section = sectionRef.current;
      if (!section) return;

      const rect = section.getBoundingClientRect();
      const sectionHeight = section.offsetHeight;
      const viewportHeight = window.innerHeight;
      const scrollableDistance = sectionHeight - viewportHeight;

      if (scrollableDistance <= 0) {
        setProgress(0);
        return;
      }

      const scrolled = -rect.top;
      const p = Math.max(0, Math.min(1, scrolled / scrollableDistance));
      setProgress(p);
    });
  }, []);

  useEffect(() => {
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => {
      window.removeEventListener("scroll", handleScroll);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [handleScroll]);

  /* ── Digest hash animation driven by progress ── */
  useEffect(() => {
    // Don't run Math.random() until mounted (client-only, after hydration)
    if (!mounted) return;
    if (reducedMotion) {
      setDigestHash(FINAL_HASH);
      setDigestLocked(progress >= digestUnlockProgress);
      return;
    }
    if (progress >= digestUnlockProgress) {
      setDigestHash(FINAL_HASH);
      setDigestLocked(true);
    } else {
      const hashProgress = Math.min(progress / digestUnlockProgress, 1);
      const { hash } = getPartialReveal(hashProgress);
      setDigestHash(hash);
      setDigestLocked(false);
    }
  }, [mounted, progress, digestUnlockProgress, reducedMotion]);

  /* ── Active stage index ── */
  const activeIndex = useMemo(() => {
    return Math.min(
      Math.floor(progress * stageCount),
      stageCount - 1
    );
  }, [progress, stageCount]);

  /* ── Desktop track translate ── */
  const trackTranslate = useMemo(() => {
    if (reducedMotion) return 0;
    return progress * 100;
  }, [progress, reducedMotion]);

  /* ── Locked chars count for coloring ── */
  const lockedCharCount = useMemo(() => {
    if (!mounted) return 0;
    if (digestLocked || progress >= digestUnlockProgress) return FINAL_HASH.length;
    return Math.floor((progress / digestUnlockProgress) * FINAL_HASH.length);
  }, [mounted, digestLocked, progress, digestUnlockProgress]);

  return (
    <section
      ref={sectionRef}
      id="how-it-works"
      className="relative bg-bone"
      /* tall container for scroll-pin: 300vh */
      style={{ height: "300vh" }}
    >
      {/* ── Sticky viewport ── */}
      <div
        className="sticky top-0 h-screen overflow-hidden flex flex-col"
      >
        {/* ── Header ── */}
        <div className="container-page relative pt-20 md:pt-24 pb-6 md:pb-8 flex-shrink-0">
          {/* Large background numeral */}
          <span
            className="hidden lg:block absolute top-6 left-2 font-display font-900 text-ledger/60 text-[200px] leading-none select-none pointer-events-none"
            aria-hidden="true"
          >
            01
          </span>

          <div className="relative z-10">
            <h2 className="font-display font-900 display-2xl uppercase text-ink">
              How It Works
            </h2>
            <p className="font-accent italic text-lg md:text-xl text-ink/70 mt-2 md:mt-3">
              One invoice. Fourteen gates. Zero shortcuts.
            </p>
          </div>

          {/* ── Digest hash display ── */}
          <div className="relative z-10 mt-4 md:mt-5 flex items-center gap-3">
            <code className="font-mono text-xs sm:text-sm text-ink/60 tracking-wide break-all">
              sha256:
              {digestHash.split("").map((char, i) => (
                <span
                  key={`h-${i}`}
                  className={`inline-block transition-colors duration-150 ${
                    digestLocked
                      ? "text-verify"
                      : i < lockedCharCount
                      ? "text-vermilion"
                      : "text-ink/40"
                  }`}
                >
                  {char}
                </span>
              ))}
            </code>
            <span
              className={`font-mono text-xs font-bold tracking-wider transition-all duration-300 ${
                digestLocked
                  ? "opacity-100 text-verify translate-x-0"
                  : "opacity-0 text-verify -translate-x-2"
              }`}
            >
              🔒 DETAILS LOCKED
            </span>
          </div>
        </div>

        {/* ── Desktop: Horizontal track (md and above) ── */}
        <div className="hidden md:flex flex-col flex-1 justify-center relative overflow-hidden">
          {/* Horizontal dashed connector line */}
          <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-0 z-0">
            <svg
              className="w-full h-4 overflow-visible"
              preserveAspectRatio="none"
            >
              <line
                x1="0"
                y1="2"
                x2="100%"
                y2="2"
                stroke="currentColor"
                className="text-ledger"
                strokeWidth="2"
                strokeDasharray="8 6"
              />
            </svg>

            {/* Token dot */}
            <div
              className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-vermilion shadow-lg shadow-vermilion/30 z-20 transition-transform duration-100"
              style={{
                left: `${Math.min(progress * 100, 98)}%`,
                transform: `translate(-50%, -50%) scale(${
                  1 + Math.sin(progress * Math.PI) * 0.3
                })`,
              }}
            >
              <div className="absolute inset-0 rounded-full bg-vermilion animate-ping opacity-30" />
            </div>
          </div>

          {/* Horizontal scrolling track */}
          <div
            ref={trackRef}
            className="flex gap-8 px-12 py-8 relative z-10 will-change-transform"
            style={{
              transform: `translateX(-${trackTranslate * (stageCount - 3) / stageCount}%)`,
              transition: reducedMotion ? "none" : "transform 0.1s linear",
            }}
          >
            {PIPELINE_STAGES.map((stage, i) => {
              const isActive = i === activeIndex;
              const isPast = i < activeIndex;

              return (
                <div
                  key={stage.id}
                  className={`
                    flex-shrink-0 min-w-[280px] max-w-[300px] bg-bone border-2 rounded-lg p-6
                    transition-all duration-300 ease-out
                    ${
                      isActive
                        ? "border-ink border-l-4 border-l-vermilion scale-105 shadow-xl shadow-ink/10"
                        : isPast
                        ? "border-ink/30 opacity-70"
                        : "border-ink/20 opacity-50"
                    }
                  `}
                >
                  {/* Stage number */}
                  <span className="font-mono text-xs text-ink/30 uppercase tracking-widest">
                    Gate {String(i + 1).padStart(2, "0")}
                  </span>

                  {/* Icon */}
                  <div
                    className={`text-3xl mt-3 mb-2 transition-transform duration-300 ${
                      isActive ? "scale-110" : ""
                    }`}
                  >
                    {stage.icon}
                  </div>

                  {/* Label */}
                  <h3
                    className={`font-display font-800 uppercase text-xl leading-tight transition-colors duration-300 ${
                      isActive ? "text-ink" : "text-ink/70"
                    }`}
                  >
                    {stage.label}
                  </h3>

                  {/* Detail */}
                  <p className="font-body text-sm text-ink/60 mt-2 leading-relaxed">
                    {stage.detail}
                  </p>

                  {/* Active indicator dot */}
                  {isActive && (
                    <div className="mt-4 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-vermilion" />
                      <span className="font-mono text-[11px] text-vermilion uppercase tracking-widest">
                        Active
                      </span>
                    </div>
                  )}
                  {isPast && (
                    <div className="mt-4 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-verify" />
                      <span className="font-mono text-[11px] text-verify uppercase tracking-widest">
                        Passed
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Progress bar at bottom */}
          <div className="absolute bottom-8 left-12 right-12 h-1 bg-ledger/50 rounded-full overflow-hidden">
            <div
              className="h-full bg-vermilion rounded-full transition-all duration-100"
              style={{ width: `${progress * 100}%` }}
            />
          </div>
        </div>

        {/* ── Mobile: Vertical stack (below md) ── */}
        <div className="flex md:hidden flex-1 overflow-y-auto px-6 pb-8">
          <div className="relative flex">
            {/* Vertical dashed line */}
            <div className="absolute left-4 top-0 bottom-0 w-px border-l-2 border-dashed border-ledger" />

            {/* Token dot on vertical line */}
            <div
              className="absolute left-4 w-3 h-3 rounded-full bg-vermilion z-10 -translate-x-[5px] transition-all duration-200"
              style={{
                top: `${Math.min(progress * 100, 97)}%`,
              }}
            />

            {/* Stage cards */}
            <div className="flex flex-col gap-4 pl-10">
              {PIPELINE_STAGES.map((stage, i) => {
                const isActive = i === activeIndex;
                const isPast = i < activeIndex;

                return (
                  <div key={stage.id} className="relative flex items-start">
                    {/* Connector dot on the line */}
                    <div
                      className={`absolute -left-[30px] top-4 w-2.5 h-2.5 rounded-full border-2 transition-colors duration-300 ${
                        isActive
                          ? "bg-vermilion border-vermilion"
                          : isPast
                          ? "bg-verify border-verify"
                          : "bg-bone border-ink/30"
                      }`}
                    />

                    {/* Card */}
                    <div
                      className={`flex-1 border-2 rounded-lg p-4 transition-all duration-300 ${
                        isActive
                          ? "border-ink border-l-4 border-l-vermilion bg-bone shadow-md"
                          : isPast
                          ? "border-ink/20 bg-bone/70"
                          : "border-ink/10 bg-bone/50"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{stage.icon}</span>
                        <div>
                          <span className="font-mono text-[11px] text-ink/30 uppercase tracking-widest">
                            Gate {String(i + 1).padStart(2, "0")}
                          </span>
                          <h3
                            className={`font-display font-800 uppercase text-base leading-tight ${
                              isActive ? "text-ink" : "text-ink/60"
                            }`}
                          >
                            {stage.label}
                          </h3>
                        </div>
                      </div>
                      <p className="font-body text-sm text-ink/50 mt-1.5">
                        {stage.detail}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
