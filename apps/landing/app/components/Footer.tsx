"use client";

import { GITHUB_URL } from "@/lib/constants";

export default function Footer() {
  return (
    <footer className="bg-ink text-bone">
      {/* Ledger line separator */}
      <div className="h-px bg-bone/10" />

      <div className="py-12 px-4 md:px-8">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6 md:gap-0">
          {/* Left: Wordmark */}
          <div className="text-center md:text-left">
            <span className="font-display font-[900] tracking-widest text-bone/40 text-xl">
              FINGUARD
            </span>
            <p className="font-mono text-xs text-bone/30 mt-1">
              FinGuard is a working name.
            </p>
          </div>

          {/* Right: GitHub link */}
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-sm text-bone/60 hover:text-bone transition-colors"
          >
            View on GitHub →
          </a>
        </div>
      </div>
    </footer>
  );
}
