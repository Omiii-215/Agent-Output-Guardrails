import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinGuard — Evidence and control for AI-assisted finance",
  description:
    "AI can read an invoice, but it never gets to move money on its own. FinGuard wraps AI in deterministic controls and keeps evidence for every step.",
  openGraph: {
    title: "FinGuard — Your AI can read the invoice. It can't move the money.",
    description:
      "Evidence and a second pair of eyes between AI and every payment.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        {/* Big Shoulders Display — condensed display */}
        {/* Instrument Serif — italic accent */}
        {/* JetBrains Mono — monospace labels */}
        {/* Instrument Sans — body */}
        <link
          href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@800;900&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500;700&family=Instrument+Sans:ital,wght@0,400;0,500;0,600;1,400&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="paper-grain antialiased">
        {children}
      </body>
    </html>
  );
}
