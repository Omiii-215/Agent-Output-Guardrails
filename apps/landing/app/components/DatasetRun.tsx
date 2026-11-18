"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useReducedMotion, useInView } from "@/lib/hooks";

function useCountUp(
  target: number,
  duration: number,
  start: boolean,
  skip: boolean
): number {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (skip) {
      setValue(target);
      return;
    }
    if (!start) {
      setValue(0);
      return;
    }

    const startTime = performance.now();

    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(step);
      }
    };

    rafRef.current = requestAnimationFrame(step);

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [target, duration, start, skip]);

  return value;
}

export default function DatasetRun() {
  const prefersReduced = useReducedMotion();
  const [ref, inView] = useInView({ threshold: 0.2, once: true });
  const count = useCountUp(26, 1500, inView, prefersReduced);

  return (
    <section ref={ref} className="bg-carbon text-bone py-24 md:py-32">
      <div className="container-page">
        {/* Section number */}
        <span className="font-mono text-sm text-bone/30 tracking-widest">
          06
        </span>

        {/* Heading */}
        <h2 className="font-display font-900 display-xl uppercase text-bone mt-4">
          TESTED ON REAL DATA.
          <br />
          MISTAKES INCLUDED.
        </h2>

        {/* Card */}
        <div
          className={`max-w-2xl mx-auto mt-16 bg-bone/5 border border-bone/20 rounded-lg p-8 transition-all duration-700 ${
            inView
              ? "opacity-100 translate-y-0"
              : prefersReduced
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-8"
          }`}
        >
          <p className="font-display text-6xl text-vermilion text-center">
            {count}
            <span className="font-body text-lg text-bone/80 ml-2">
              invoices
            </span>
          </p>

          <p className="font-mono text-sm text-bone/60 text-center mt-4">
            from{" "}
            <a
              href="https://huggingface.co/datasets/katanaml-org/invoices-donut-data-v1"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-4 decoration-bone/30 hover:decoration-vermilion hover:text-vermilion transition-colors duration-200"
            >
              katanaml-org/invoices-donut-data-v1
            </a>
          </p>

          <p className="font-body text-lg text-bone/80 mt-4 text-center">
            A public dataset. With its labelling mistakes kept on purpose.
          </p>

          <p className="font-body text-sm text-bone/50 mt-4 text-center">
            We don&rsquo;t cherry-pick test data. If the labels are wrong, we
            run on them anyway. That&rsquo;s the point.
          </p>
        </div>

        {/* Bottom tagline */}
        <p className="font-accent italic text-lg text-bone/40 mt-8 text-center">
          Three modules built. Five gated. Zero fake metrics.
        </p>
      </div>
    </section>
  );
}
