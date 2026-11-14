"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useReducedMotion } from "@/lib/hooks";

type StampType = "VERIFIED" | "FLAGGED" | "FROZEN" | "APPROVED" | "BLOCKED";

type PlacedStamp = {
  id: string;
  x: number;
  y: number;
  type: StampType;
  rotation: number;
};

type RainParticle = {
  id: number;
  symbol: string;
  x: number;
  delay: number;
  duration: number;
  rotation: number;
  isNote: boolean;
};

export default function InteractiveStampCanvas() {
  const reducedMotion = useReducedMotion();
  const [activeStamp, setActiveStamp] = useState<StampType>("VERIFIED");
  const [stamps, setStamps] = useState<PlacedStamp[]>([]);
  const [stampModeActive, setStampModeActive] = useState(false);
  const [isRainingMoney, setIsRainingMoney] = useState(false);
  const [rainParticles, setRainParticles] = useState<RainParticle[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);

  // Play a realistic mechanical stamp click sound using Web Audio API
  const playStampSound = useCallback(() => {
    try {
      if (typeof window === "undefined") return;
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      if (!AudioCtx) return;
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioCtx();
      }
      const ctx = audioContextRef.current;
      if (ctx.state === "suspended") {
        ctx.resume();
      }
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(140, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(30, ctx.currentTime + 0.08);
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.08);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.09);
    } catch {
      // Audio not supported or blocked by user gesture
    }
  }, []);

  // Global click handler when stamp mode is toggled
  useEffect(() => {
    if (!stampModeActive) return;

    const handleClick = (e: MouseEvent) => {
      // Don't place stamp if clicking the toolbar itself
      const target = e.target as HTMLElement;
      if (target.closest(".stamp-toolbar")) return;

      const newStamp: PlacedStamp = {
        id: Math.random().toString(36).substring(2, 9),
        x: e.pageX,
        y: e.pageY,
        type: activeStamp,
        rotation: (Math.random() - 0.5) * 24, // -12 to +12 degrees
      };

      setStamps((prev) => [...prev.slice(-25), newStamp]);
      playStampSound();
    };

    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, [stampModeActive, activeStamp, playStampSound, reducedMotion]);

  // Trigger high-volume money shower
  const triggerMoneyRain = () => {
    const symbols = ["$100", "₹500", "€50", "£20", "$", "₹", "💰", "💸"];
    const particles: RainParticle[] = Array.from({ length: 45 }, (_, i) => ({
      id: Date.now() + i,
      symbol: symbols[i % symbols.length],
      x: Math.random() * 96 + 2,
      delay: Math.random() * 1.5,
      duration: 3.5 + Math.random() * 2,
      rotation: Math.random() * 360,
      isNote: i % 2 === 0,
    }));

    setRainParticles(particles);
    setIsRainingMoney(true);

    setTimeout(() => {
      setIsRainingMoney(false);
    }, 6000);
  };

  const clearStamps = () => setStamps([]);

  return (
    <>
      {/* Dynamic Money Shower Layer */}
      {isRainingMoney && (
        <div
          className="fixed inset-0 pointer-events-none z-50 overflow-hidden"
          aria-hidden="true"
        >
          {rainParticles.map((p) => (
            <div
              key={p.id}
              className="money-particle absolute top-0 select-none"
              style={{
                left: `${p.x}%`,
                animationDelay: `${p.delay}s`,
                animationDuration: `${p.duration}s`,
                ["--wobble" as string]: "35px",
                ["--rot" as string]: `${p.rotation}deg`,
              }}
            >
              {p.isNote ? (
                <div className="w-14 h-7 rounded border border-verify/50 bg-verify/20 backdrop-blur-xs flex items-center justify-between px-2 font-mono text-[10px] font-bold text-verify shadow-lg">
                  <span>{p.symbol}</span>
                  <span className="text-[7px] opacity-80">VALID</span>
                  <span>{p.symbol}</span>
                </div>
              ) : (
                <div className="w-7 h-7 rounded-full border border-amber-400 bg-amber-400/20 backdrop-blur-xs flex items-center justify-center font-mono text-xs font-bold text-amber-500 shadow-md">
                  {p.symbol}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Rendered rubber stamps on document — absolute so they stick to scroll position */}
      <div
        className="pointer-events-none absolute top-0 left-0 w-full min-h-full z-40 overflow-hidden"
        aria-hidden="true"
      >
        {stamps.map((s) => {
          const isVermilion = s.type === "FLAGGED" || s.type === "BLOCKED";
          return (
            <div
              key={s.id}
              className="absolute pointer-events-none transform -translate-x-1/2 -translate-y-1/2 will-change-transform"
              style={{
                left: s.x,
                top: s.y,
              }}
            >
              <div
                className={`stamp ${
                  isVermilion ? "stamp-vermilion" : "stamp-verify"
                } ${reducedMotion ? "" : "stamp-slam"} text-base sm:text-lg md:text-xl font-[900] shadow-sm select-none bg-bone/90`}
                style={{
                  transform: `rotate(${s.rotation}deg)`,
                }}
              >
                {s.type}
              </div>
            </div>
          );
        })}
      </div>

      {/* Floating Interactive Stamp & Finance Animation Toolbar */}
      <aside
        aria-label="Interactive Rubber Stamp Tool"
        className="stamp-toolbar fixed bottom-6 right-6 z-50 bg-ink/95 text-bone border-2 border-ledger/40 rounded-xl p-3 shadow-2xl backdrop-blur-md flex flex-col gap-2 max-w-[320px] transition-all duration-300"
      >
        <div className="flex items-center justify-between gap-3 pb-2 border-b border-bone/10">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-verify animate-pulse" />
            <span className="font-mono text-xs font-bold uppercase tracking-wider text-bone">
              Interactive Tools
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={triggerMoneyRain}
              title="Drop financial currency animation"
              className="font-mono text-[10px] uppercase px-2 py-0.5 rounded font-bold bg-amber-400/20 text-amber-300 hover:bg-amber-400/30 transition-all border border-amber-400/30"
            >
              💸 Drop Money
            </button>
            <button
              onClick={() => setStampModeActive((v) => !v)}
              aria-label={stampModeActive ? "Turn stamp tool off" : "Turn stamp tool on"}
              className={`font-mono text-[10px] uppercase px-2 py-0.5 rounded font-bold transition-all ${
                stampModeActive
                  ? "bg-verify text-ink"
                  : "bg-bone/10 text-bone/60 hover:text-bone hover:bg-bone/20"
              }`}
            >
              {stampModeActive ? "STAMPS ON" : "STAMPS"}
            </button>
          </div>
        </div>

        {stampModeActive && (
          <div className="space-y-2 pt-1">
            <p className="font-body text-xs text-bone/70 leading-tight">
              Click anywhere on the page to stamp evidence seals:
            </p>
            <div className="grid grid-cols-3 gap-1.5">
              {(["VERIFIED", "FLAGGED", "FROZEN", "APPROVED", "BLOCKED"] as StampType[]).map(
                (type) => {
                  const isRed = type === "FLAGGED" || type === "BLOCKED";
                  return (
                    <button
                      key={type}
                      onClick={() => setActiveStamp(type)}
                      className={`px-2 py-1.5 rounded font-display font-bold text-xs uppercase transition-all ${
                        activeStamp === type
                          ? isRed
                            ? "bg-vermilion text-white scale-102 shadow-md"
                            : "bg-verify text-ink scale-102 shadow-md"
                          : "bg-bone/10 text-bone/70 hover:bg-bone/20"
                      }`}
                    >
                      {type}
                    </button>
                  );
                }
              )}
            </div>

            {stamps.length > 0 && (
              <div className="flex items-center justify-between pt-1 border-t border-bone/10">
                <span className="font-mono text-[10px] text-bone/50">
                  {stamps.length} stamps placed
                </span>
                <button
                  onClick={clearStamps}
                  className="font-mono text-[10px] text-vermilion hover:underline uppercase"
                >
                  Clear all
                </button>
              </div>
            )}
          </div>
        )}
      </aside>
    </>
  );
}
