"use client";

import { useEffect, useState } from "react";
import CtaButton from "./CtaButton";

export default function Nav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 100);
    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      className={[
        "fixed top-0 inset-x-0 z-50",
        "bg-bone/90 backdrop-blur-sm",
        "border-b border-ledger",
        "transition-shadow duration-300",
        scrolled ? "shadow-[0_2px_12px_rgba(12,12,13,0.08)]" : "shadow-none",
      ].join(" ")}
    >
      <div className="container-page flex items-center justify-between gap-4 py-3">
        {/* Wordmark */}
        <a href="#" className="font-display text-xl font-black tracking-widest text-ink select-none">
          FIN<span className="text-vermilion">GUARD</span>
        </a>

        {/* Section Links (desktop) */}
        <div className="hidden lg:flex items-center gap-6 font-mono text-xs uppercase tracking-wider text-ink/70">
          <a href="#problem" className="hover:text-vermilion transition-colors">
            The Problem
          </a>
          <a href="#capital-interceptor" className="hover:text-vermilion transition-colors">
            See It Work
          </a>
          <a href="#architecture" className="hover:text-vermilion transition-colors">
            How It’s Built
          </a>
          <a href="#how-it-works" className="hover:text-vermilion transition-colors">
            Step by Step

          </a>
          <a href="#simulator" className="hover:text-vermilion transition-colors">
            Try It
          </a>
          <a href="#guarantees" className="hover:text-vermilion transition-colors">
            Guarantees
          </a>
        </div>

        {/* CTA */}
        <CtaButton variant="primary" size="sm">
          Open the dashboard
        </CtaButton>
      </div>
    </nav>
  );
}
