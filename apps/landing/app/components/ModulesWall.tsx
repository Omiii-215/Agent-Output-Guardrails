"use client";

import { useState } from "react";
import { useReducedMotion, useInView } from "@/lib/hooks";
import { GATED_MODULES, BUILT_MODULES } from "@/lib/constants";

function PadlockIcon({ className }: { className?: string }) {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function BuiltCard({
  module,
}: {
  module: { code: string; name: string; detail?: string };
}) {
  return (
    <div className="border-l-4 border-verify bg-white rounded-r-lg p-6 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="font-display text-2xl text-ink">{module.code}</span>
        <span className="text-verify font-mono text-xs uppercase tracking-wider">
          BUILT
        </span>
      </div>
      <p className="font-body font-semibold text-ink">{module.name}</p>
      {module.detail && (
        <p className="font-mono text-xs text-ink/60 mt-2">{module.detail}</p>
      )}
    </div>
  );
}

function GatedCard({
  module,
}: {
  module: { code: string; name: string };
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className={`relative bg-ink/5 border-2 border-dashed rounded-lg p-6 transition-colors duration-300 ${
        hovered ? "border-vermilion/40" : "border-ink/20"
      }`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="flex flex-col items-center text-center">
        <PadlockIcon
          className={`text-ink/40 mb-4 ${hovered ? "rattle" : ""}`}
        />
        <span className="font-display text-xl text-ink/60 mb-1">
          {module.code}
        </span>
        <p className="font-body font-semibold text-ink/60">{module.name}</p>

        {/* Mobile: always visible */}
        <p className="mt-3 font-mono text-xs text-vermilion md:hidden">
          No evaluator until it&rsquo;s earned.
        </p>

        {/* Desktop: hover tooltip */}
        <div
          className={`hidden md:block absolute inset-0 rounded-lg bg-ink/5 backdrop-blur-sm items-center justify-center transition-opacity duration-200 ${
            hovered
              ? "opacity-100 pointer-events-auto flex"
              : "opacity-0 pointer-events-none"
          }`}
          style={{ display: hovered ? "flex" : "none" }}
        >
          <p className="font-mono text-sm text-vermilion px-4 text-center">
            No evaluator until it&rsquo;s earned.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function ModulesWall() {
  const prefersReduced = useReducedMotion();
  const [ref, inView] = useInView({ threshold: 0.1, once: true });

  return (
    <section ref={ref} className="bg-bone py-24 md:py-32 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Section number */}
        <span className="font-mono text-sm text-ink/30 tracking-widest">
          05
        </span>

        {/* Heading */}
        <h2 className="font-display font-900 text-5xl md:text-7xl uppercase text-ink mt-4 leading-[0.95]">
          WHAT&rsquo;S BUILT.
          <br />
          WHAT&rsquo;S NOT.
        </h2>
        <p className="font-accent italic text-xl text-ink/70 mt-6 max-w-xl">
          Contracts exist for everything. Evaluators exist for three.
        </p>

        {/* Built modules row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mt-16">
          {BUILT_MODULES.map((mod) => (
            <BuiltCard key={mod.code} module={mod} />
          ))}
        </div>

        {/* Gated modules wall */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mt-12">
          {GATED_MODULES.map((mod) => (
            <GatedCard key={mod.code} module={mod} />
          ))}
        </div>
      </div>
    </section>
  );
}
