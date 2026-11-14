"use client";

import { PERSONAS, DASHBOARD_URL } from "@/lib/constants";
import { useInView } from "@/lib/hooks";
import CtaButton from "./CtaButton";

const TILTS = [-2, 1, -1.5, 2, -1];

export default function PersonaPicker() {
  const [ref, inView] = useInView(0.15);

  return (
    <section
      ref={ref as React.RefObject<HTMLElement>}
      className="bg-carbon text-bone py-20 md:py-28 overflow-hidden"
    >
      <div className="max-w-7xl mx-auto px-4 md:px-8">
        {/* Title */}
        <h2
          className={`font-display font-[900] text-5xl md:text-7xl uppercase text-center mb-4 transition-all duration-700 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
        >
          Pick your seat.
        </h2>
        <p
          className={`font-accent italic text-xl text-center text-bone/60 mb-12 md:mb-16 transition-all duration-700 delay-100 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
        >
          Five roles. Five views. Same evidence trail.
        </p>

        {/* Ticket Cards */}
        <div className="flex gap-4 md:gap-6 overflow-x-auto snap-x snap-mandatory pb-4 md:pb-0 md:overflow-visible md:grid md:grid-cols-5 scrollbar-hide">
          {PERSONAS.map((persona, i) => (
            <div
              key={persona.id}
              className={`ticket-card bg-bone text-ink p-6 min-w-[220px] snap-center flex flex-col justify-between
                transition-transform duration-300 hover:rotate-0 hover:scale-105 hover:shadow-2xl hover:z-10
                ${inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-12"}
              `}
              style={{
                transform: `rotate(${TILTS[i]}deg)`,
                transitionDelay: `${150 + i * 75}ms`,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform =
                  "rotate(0deg) scale(1.05)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = `rotate(${TILTS[i]}deg)`;
              }}
            >
              <div>
                <h3 className="font-display text-2xl uppercase font-bold mb-2">
                  {persona.title}
                </h3>
                <p className="font-body text-sm text-ink/70 mb-6">
                  {persona.description}
                </p>
              </div>
              <a
                href={`${DASHBOARD_URL}?persona=${persona.id}`}
                className="font-mono text-xs uppercase text-vermilion hover:text-ink transition-colors inline-flex items-center gap-1"
              >
                Open as {persona.title} →
              </a>
            </div>
          ))}
        </div>

        {/* Final CTA */}
        <div
          className={`text-center mt-12 md:mt-16 transition-all duration-700 delay-500 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
        >
          <CtaButton variant="primary" size="lg">
            Open the dashboard
          </CtaButton>
        </div>
      </div>
    </section>
  );
}
