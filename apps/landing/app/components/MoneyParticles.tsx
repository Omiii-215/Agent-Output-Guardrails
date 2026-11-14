"use client";

import { useEffect, useState, useMemo } from "react";
import { useReducedMotion } from "@/lib/hooks";

interface Particle {
  id: number;
  currency: string;
  amount: string;
  x: number;
  delay: number;
  duration: number;
  rotation: number;
  wobble: number;
  type: "banknote" | "gold_coin" | "ledger_hash";
  scale: number;
}

const CURRENCIES = [
  { curr: "$", amount: "10,000", code: "USD" },
  { curr: "₹", amount: "50,000", code: "INR" },
  { curr: "€", amount: "25,000", code: "EUR" },
  { curr: "£", amount: "15,000", code: "GBP" },
  { curr: "$", amount: "100,000", code: "USD" },
  { curr: "¥", amount: "1,000,000", code: "JPY" },
];

function generateParticles(count: number): Particle[] {
  const particles: Particle[] = [];
  for (let i = 0; i < count; i++) {
    const c = CURRENCIES[i % CURRENCIES.length];
    const type: "banknote" | "gold_coin" | "ledger_hash" =
      i % 3 === 0 ? "banknote" : i % 3 === 1 ? "gold_coin" : "banknote";

    particles.push({
      id: i,
      currency: c.curr,
      amount: c.amount,
      x: ((i * 11.3) % 92) + 4, // spread 4% to 96%
      delay: (i * 0.9) % 12,
      duration: 8 + (i % 4) * 2.5,
      rotation: -25 + ((i * 23) % 50),
      wobble: 18 + (i % 5) * 8,
      type,
      scale: 0.85 + (i % 3) * 0.15,
    });
  }
  return particles;
}

/**
 * High-visibility financial asset particles.
 * Renders realistic banknotes with currency markings, guilloche borders,
 * and 3D metallic gold coins that tumble through financial sections.
 */
export default function MoneyParticles({
  count = 20,
  theme = "dark",
  className = "",
}: {
  count?: number;
  theme?: "light" | "dark";
  className?: string;
}) {
  const reducedMotion = useReducedMotion();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const particles = useMemo(() => generateParticles(count), [count]);

  if (reducedMotion || !mounted) return null;

  const isLight = theme === "light";

  return (
    <div
      className={`absolute inset-0 overflow-hidden pointer-events-none z-0 ${className}`}
      aria-hidden="true"
    >
      {particles.map((p) => (
        <div
          key={p.id}
          className="money-particle absolute top-0 select-none"
          style={{
            left: `${p.x}%`,
            animationDelay: `${p.delay}s`,
            animationDuration: `${p.duration}s`,
            ["--wobble" as string]: `${p.wobble}px`,
            ["--rot" as string]: `${p.rotation}deg`,
          }}
        >
          {p.type === "banknote" ? (
            /* High-fidelity stylized Banknote */
            <div
              className={`relative rounded border-2 flex flex-col justify-between p-1.5 shadow-lg backdrop-blur-xs transition-transform ${
                isLight
                  ? "bg-[#E6F3EA]/90 border-[#19D27A]/60 text-[#0C4E2D]"
                  : "bg-[#0F261B]/85 border-[#19D27A]/50 text-[#19D27A]"
              }`}
              style={{
                width: "90px",
                height: "46px",
                transform: `scale(${p.scale}) rotate(${p.rotation}deg)`,
                boxShadow: isLight
                  ? "0 4px 12px rgba(25, 210, 122, 0.15), 0 1px 3px rgba(0,0,0,0.08)"
                  : "0 6px 16px rgba(0,0,0,0.4), 0 0 10px rgba(25, 210, 122, 0.12)",
              }}
            >
              {/* Top row */}
              <div className="flex items-center justify-between font-mono text-[9px] font-black leading-none">
                <span>{p.currency}</span>
                <span className="text-[7px] tracking-widest uppercase opacity-75 font-sans">
                  FINANCIAL RUNTIME
                </span>
                <span>{p.currency}</span>
              </div>

              {/* Center watermark & denomination */}
              <div className="flex items-center justify-center my-0.5 border-y border-dashed border-current/25 py-0.5">
                <span className="font-display font-black text-sm tracking-tight leading-none">
                  {p.currency}
                  {p.amount}
                </span>
              </div>

              {/* Bottom security microprint */}
              <div className="flex items-center justify-between font-mono text-[6px] tracking-tight opacity-70 leading-none">
                <span>#FG-{p.id}98</span>
                <span className="font-bold">VERIFIED</span>
              </div>
            </div>
          ) : (
            /* High-fidelity 3D Gold Coin with metallic sheen */
            <div
              className="relative rounded-full flex items-center justify-center shadow-md coin-spin"
              style={{
                width: "36px",
                height: "36px",
                transform: `scale(${p.scale})`,
                background:
                  "radial-gradient(circle at 35% 35%, #FFE57F 0%, #FFB300 55%, #FF8F00 100%)",
                border: "2px solid #FFE082",
                boxShadow: isLight
                  ? "0 4px 10px rgba(255, 179, 0, 0.35), inset 0 1px 2px rgba(255, 255, 255, 0.8)"
                  : "0 4px 14px rgba(0, 0, 0, 0.5), inset 0 1px 2px rgba(255, 255, 255, 0.8), 0 0 12px rgba(255, 179, 0, 0.25)",
              }}
            >
              <div className="w-[28px] h-[28px] rounded-full border border-dashed border-amber-900/30 flex items-center justify-center">
                <span className="font-mono font-black text-amber-950 text-xs">
                  {p.currency}
                </span>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
