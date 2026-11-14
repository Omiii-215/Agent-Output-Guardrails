"use client";

import { useReducedMotion } from "@/lib/hooks";

const TICKER_ITEMS = [
  { pair: "USD/INR", value: "83.42", change: "+0.12", up: true },
  { pair: "EUR/USD", value: "1.0847", change: "-0.003", up: false },
  { pair: "NIFTY 50", value: "19,843", change: "+127", up: true },
  { pair: "BTC/USD", value: "97,234", change: "+1,420", up: true },
  { pair: "SENSEX", value: "65,928", change: "-89", up: false },
  { pair: "GBP/INR", value: "104.67", change: "+0.31", up: true },
  { pair: "GOLD", value: "2,041", change: "+8.50", up: true },
  { pair: "S&P 500", value: "5,892", change: "-12", up: false },
  { pair: "JPY/USD", value: "0.0067", change: "+0.0001", up: true },
  { pair: "CRUDE", value: "78.34", change: "-0.89", up: false },
];

/**
 * A horizontal scrolling financial ticker tape.
 * Place between sections as a visual divider.
 */
export default function FinanceTicker() {
  const reducedMotion = useReducedMotion();

  // Double the items for seamless loop
  const items = [...TICKER_ITEMS, ...TICKER_ITEMS];

  return (
    <div className="relative bg-carbon border-y border-ink/20 overflow-hidden select-none">
      <div
        className={`flex items-center gap-0 whitespace-nowrap py-2 ${
          reducedMotion ? "" : "finance-ticker"
        }`}
      >
        {items.map((item, i) => (
          <span
            key={`${item.pair}-${i}`}
            className="inline-flex items-center gap-2 px-6 font-mono text-xs"
          >
            <span className="text-bone/50 font-bold">{item.pair}</span>
            <span className="text-bone/70">{item.value}</span>
            <span
              className={item.up ? "text-verify" : "text-vermilion"}
            >
              {item.up ? "▲" : "▼"} {item.change}
            </span>
            <span className="text-ink/20 mx-2">│</span>
          </span>
        ))}
      </div>
    </div>
  );
}
