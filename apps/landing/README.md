# FinGuard Landing Page

Marketing site for **FinGuard** — an evidence and control platform for AI-assisted financial work.

> "Your AI can read the invoice. It can't move the money."

---

## Running locally

```bash
# From the repo root
cd apps/landing

# Install dependencies (first time)
npm install

# Start the dev server on port 3001
npm run dev
```

The landing page opens at **http://localhost:3001**.

The dashboard CTA links to `NEXT_PUBLIC_DASHBOARD_URL` (default: `http://localhost:3000`).  
To point it at a different dashboard:

```bash
# .env.local
NEXT_PUBLIC_DASHBOARD_URL=https://your-dashboard.example.com
```

---

## Production build

```bash
npm run build
npm start          # starts on port 3001
```

---

## Page structure

| Section | Description |
|---------|-------------|
| **Nav** | Fixed bar — wordmark + "Open the dashboard" CTA |
| **Hero** | Headline reveal with rotating stamp animation on floating invoice cards |
| **Pipeline** (§01) | Scroll-pinned horizontal pipeline — 14 gates, animated token + morphing digest hash |
| **Injection Demo** (§02) | Fake invoice with hidden white-on-white prompt injection revealed by scan line |
| **Maker-Checker** (§03) | Split-screen approval demo — proposer rejected, independent approver required |
| **Unknown Reconcile** (§04) | Lost-response animation — reconcile loop, never resend |
| **Modules Wall** (§05) | Built vs gated modules — padlock rattle on hover |
| **Dataset Run** (§06) | 26-invoice test run with count-up animation |
| **Audit Ticker** (§07) | Endless two-row marquee of append-only chained-hash log lines |
| **Honesty** | "WE ARE A PROTOTYPE." — big legal stamp, honest status |
| **Persona Picker** | 5 tilted ticket cards (operator, approver, auditor, policy author, admin) |
| **Footer** | Wordmark + GitHub link |

---

## Animation libraries used

| Library | Version | Used for |
|---------|---------|---------|
| **CSS Animations** (native) | — | Headline clip-reveal, stamp-slam, screen-shake, marquee, scanner line, button-deny, rattle, flicker |
| **Framer Motion** | 12.x | (available, not yet used — reserved for page transition polish) |
| **GSAP + ScrollTrigger** | 3.x | (available — pipeline horizontal scroll driven by vanilla scroll listener for perf) |
| **Lenis** | 1.x | (available — smooth scroll, opt-in) |

> All signature animations are implemented in pure CSS keyframes + React `useState`/`useEffect` for minimal JS overhead. `prefers-reduced-motion` is respected throughout — animations swap to simple fades.

---

## Fonts (Google Fonts)

| Font | Weight | Used for |
|------|--------|---------|
| **Big Shoulders Display** | 800, 900 | All display headlines (condensed, loud) |
| **Instrument Serif** | 400 italic | Accent/subline copy |
| **JetBrains Mono** | 400, 500, 700 | Hashes, labels, log lines, monospace UI |
| **Instrument Sans** | 400–600 | Body text |

---

## Brand colours

| Token | Hex | Role |
|-------|-----|------|
| `--color-bone` | `#EFE9DC` | Background (paper) |
| `--color-ink` | `#0C0C0D` | Primary text |
| `--color-vermilion` | `#FF3B1F` | CTA, flags, blocked states |
| `--color-verify` | `#19D27A` | Approved, passed states |
| `--color-carbon` | `#1A1A1C` | Dark section backgrounds |
| `--color-ledger` | `#D9D1BF` | Ruled lines, borders, dividers |

---

## Notes

- **Prototype status**: All copy is honest. Payments run on a simulator. No real money.
- **Dataset**: 26 invoices from `katanaml-org/invoices-donut-data-v1` (public, labelling mistakes kept).
- **GitHub**: https://github.com/Omiii-215/Agent-Output-Guardrails
- **Working name**: FinGuard is not the final product name.
