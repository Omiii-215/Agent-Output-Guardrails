"use client";

import { useRef } from "react";
import { DASHBOARD_URL } from "@/lib/constants";
import { useMagnetic } from "@/lib/hooks";

type CtaButtonProps = {
  variant?: "primary" | "outline" | "dark";
  size?: "sm" | "md" | "lg";
  persona?: string;
  children: React.ReactNode;
};

const sizeClasses: Record<string, string> = {
  sm: "px-5 py-2 text-xs",
  md: "px-7 py-3 text-sm",
  lg: "px-9 py-4 text-base",
};

const variantClasses: Record<string, string> = {
  primary:
    "bg-vermilion text-white hover:scale-105 hover:shadow-[0_6px_24px_rgba(255,59,31,0.4)] active:scale-[1.02]",
  outline:
    "border-2 border-ink text-ink hover:bg-ink hover:text-bone active:opacity-90",
  dark: "bg-ink text-bone hover:bg-carbon active:opacity-90",
};

export default function CtaButton({
  variant = "primary",
  size = "md",
  persona,
  children,
}: CtaButtonProps) {
  const ref = useRef<HTMLAnchorElement>(null);
  useMagnetic(ref as React.RefObject<HTMLElement | null>);

  const href = `${DASHBOARD_URL}${persona ? `?persona=${persona}` : "?persona=operator"}`;

  return (
    <a
      ref={ref}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={[
        "inline-block rounded-md font-display uppercase font-extrabold tracking-wide",
        "transition-all duration-200 ease-out will-change-transform",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-vermilion",
        sizeClasses[size],
        variantClasses[variant],
      ].join(" ")}
    >
      {children}
    </a>
  );
}
