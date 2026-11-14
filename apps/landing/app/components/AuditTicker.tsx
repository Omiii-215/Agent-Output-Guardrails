"use client";

import { useMemo } from "react";
import { AUDIT_LOG_LINES } from "@/lib/constants";
import { useReducedMotion } from "@/lib/hooks";

function styleLine(line: string) {
  const parts: React.ReactNode[] = [];
  const regex =
    /(sha256:[a-f0-9…]+|hash:[a-f0-9…]+|hmac_sha256:[a-f0-9…]+|chain_hash:sha256:[a-f0-9…]+|prev:sha256:[a-f0-9…]+|digest:sha256:[a-f0-9…]+)|(SETTLED|CLEAR|MALWARE_CLEAR|RECONCILE_RESOLVED)|(BLOCKED|INJECTION_DETECT)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(line)) !== null) {
    if (match.index > lastIndex) {
      parts.push(line.slice(lastIndex, match.index));
    }
    if (match[1]) {
      parts.push(
        <span key={match.index} className="text-vermilion">
          {match[0]}
        </span>
      );
    } else if (match[2]) {
      parts.push(
        <span key={match.index} className="text-verify font-bold">
          {match[0]}
        </span>
      );
    } else if (match[3]) {
      parts.push(
        <span key={match.index} className="text-vermilion font-bold">
          {match[0]}
        </span>
      );
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < line.length) {
    parts.push(line.slice(lastIndex));
  }

  return parts;
}

function MarqueeRow({
  lines,
  direction,
  duration,
}: {
  lines: string[];
  direction: "left" | "right";
  duration: string;
}) {
  const animationClass =
    direction === "left" ? "marquee-left" : "marquee-right";

  const content = useMemo(
    () =>
      lines.map((line, i) => (
        <span
          key={i}
          className="font-mono text-xs md:text-sm whitespace-nowrap px-4 py-2 mx-2 bg-ink/5 rounded inline-block"
        >
          {styleLine(line)}
        </span>
      )),
    [lines]
  );

  return (
    <div className="flex overflow-hidden relative">
      <div
        className={`flex shrink-0 ${animationClass}`}
        style={{ animationDuration: duration }}
      >
        {content}
      </div>
      <div
        className={`flex shrink-0 ${animationClass}`}
        style={{ animationDuration: duration }}
        aria-hidden
      >
        {content}
      </div>
    </div>
  );
}

export default function AuditTicker() {
  const reducedMotion = useReducedMotion();

  const halfLen = Math.ceil(AUDIT_LOG_LINES.length / 2);
  const row1 = AUDIT_LOG_LINES.slice(0, halfLen);
  const row2 = AUDIT_LOG_LINES.slice(halfLen);

  return (
    <section className="bg-bone py-20 md:py-28 overflow-hidden">
      <div className="max-w-7xl mx-auto px-4 md:px-8">
        {/* Title */}
        <h2 className="font-display font-[900] text-5xl md:text-7xl uppercase text-center text-ink mb-4">
          Every step. Every hash. Forever.
        </h2>
        <p className="font-accent italic text-xl text-center text-ink/70 mb-12 md:mb-16">
          Append-only. Chained hashes. Sealed on export.
        </p>
      </div>

      {/* Marquee area */}
      <div className="relative">
        {/* Top fade */}
        <div className="absolute top-0 left-0 right-0 h-8 bg-gradient-to-b from-bone to-transparent z-10 pointer-events-none" />

        <div
          className={`space-y-3 ${reducedMotion ? "[&_*]:!animation-play-state-paused" : ""}`}
        >
          <MarqueeRow lines={row1} direction="left" duration="40s" />
          <MarqueeRow lines={row2} direction="right" duration="60s" />
        </div>

        {/* Bottom fade */}
        <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-bone to-transparent z-10 pointer-events-none" />
      </div>
    </section>
  );
}
