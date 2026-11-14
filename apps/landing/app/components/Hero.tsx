"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useReducedMotion, useInView } from "@/lib/hooks";
import { DASHBOARD_URL } from "@/lib/constants";
import CtaButton from "./CtaButton";
import MoneyParticles from "./MoneyParticles";

const INVOICES = [
  { id: "INV-4821", rotate: "-3deg", top: "8%", left: "4%", opacity: 0.2 },
  { id: "INV-7734", rotate: "2deg", top: "12%", right: "5%", opacity: 0.25 },
  { id: "INV-3309", rotate: "-1deg", bottom: "18%", left: "10%", opacity: 0.15 },
];

type StampType = "FLAGGED" | "VERIFIED";

export default function Hero() {
  const reducedMotion = useReducedMotion();
  const [heroRef, inView] = useInView(0.15);
  const [revealed, setRevealed] = useState(false);
  const [stampIndex, setStampIndex] = useState<number | null>(null);
  const [stampType, setStampType] = useState<StampType>("FLAGGED");
  const stampCycleRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setRevealed(true), 80);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (inView) setRevealed(true);
  }, [inView]);

  const applyStamp = useCallback(() => {
    const cycle = stampCycleRef.current;
    const cardIdx = cycle % 3;
    const type: StampType = cycle % 2 === 0 ? "FLAGGED" : "VERIFIED";
    stampCycleRef.current += 1;

    setStampIndex(cardIdx);
    setStampType(type);
  }, []);

  useEffect(() => {
    if (!revealed) return;

    timerRef.current = setTimeout(() => {
      applyStamp();
      intervalRef.current = setInterval(applyStamp, 4000);
    }, 2000);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [revealed, applyStamp]);

  return (
    <>
      <section
        ref={heroRef as React.RefObject<HTMLElement>}
        className={`relative min-h-screen flex items-center justify-center bg-bone ledger-lines overflow-hidden ${reducedMotion ? "reduced-motion" : ""}`}
      >
        {/* Ambient finance falling notes & currency */}
        <MoneyParticles theme="light" count={18} />

        {/* Invoice Cards (decorative) */}
        {INVOICES.map((inv, i) => {
          const posStyle: React.CSSProperties = {
            transform: `rotate(${inv.rotate})`,
            opacity: inv.opacity,
            ...(inv.top ? { top: inv.top } : {}),
            ...(inv.bottom ? { bottom: inv.bottom } : {}),
            ...(inv.left ? { left: inv.left } : {}),
            ...(inv.right ? { right: inv.right } : {}),
          };

          const isStamped = stampIndex === i;

          return (
            <div
              key={inv.id}
              aria-hidden="true"
              className="absolute hidden md:block w-[180px] h-[240px] lg:w-[240px] lg:h-[320px] bg-white shadow-lg rounded-lg p-4 lg:p-6 z-0 pointer-events-none"
              style={posStyle}
            >
              <p className="font-mono text-xs lg:text-sm text-carbon/70 mb-3 lg:mb-4">
                {inv.id}
              </p>
              <div className="space-y-2 lg:space-y-3">
                <div className="h-2 bg-carbon/10 rounded w-full" />
                <div className="h-2 bg-carbon/10 rounded w-4/5" />
                <div className="h-2 bg-carbon/10 rounded w-3/5" />
                <div className="h-px bg-carbon/20 my-2 lg:my-3" />
                <div className="h-2 bg-carbon/10 rounded w-full" />
                <div className="h-2 bg-carbon/10 rounded w-2/3" />
              </div>

              {isStamped && (
                <div
                  className={`absolute inset-0 flex items-center justify-center ${reducedMotion ? "stamp-appear is-stamped" : "stamp-slam"}`}
                >
                  <span
                    className={`stamp ${stampType === "FLAGGED" ? "stamp-vermilion" : "stamp-verify"}`}
                  >
                    {stampType}
                  </span>
                </div>
              )}
            </div>
          );
        })}

        {/* Content */}
        <div className="relative z-10 text-center px-4 sm:px-6 max-w-5xl mx-auto">
          {/* Headline */}
          <h1 className="font-display font-900 uppercase leading-[0.9] tracking-tight text-ink">
            <span
              className={`block text-5xl md:text-7xl lg:text-8xl xl:text-9xl headline-reveal ${revealed ? "is-visible" : ""}`}
            >
              YOUR AI CAN READ THE INVOICE.
            </span>
            <span
              className={`block text-5xl md:text-7xl lg:text-8xl xl:text-9xl mt-1 md:mt-2 headline-reveal-delayed ${revealed ? "is-visible" : ""}`}
            >
              IT <span className="text-vermilion">CAN&rsquo;T</span> MOVE THE
              MONEY.
            </span>
          </h1>

          {/* Subline */}
          <p
            className={`font-accent italic text-xl md:text-2xl max-w-2xl mx-auto mt-6 md:mt-8 opacity-80 text-ink subline-fade ${revealed ? "is-visible" : ""}`}
          >
            FinGuard puts evidence and a second pair of eyes between AI and
            every payment.
          </p>

          {/* CTA */}
          <div
            className={`mt-8 cta-fade ${revealed ? "is-visible" : ""}`}
          >
            <CtaButton variant="primary" size="lg">
              Open the dashboard
            </CtaButton>
          </div>
        </div>
      </section>
    </>
  );
}
