"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSession } from "@/app/providers";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", label: "Overview", icon: "grid" },
  { href: "/queue", label: "Review queue", icon: "list" },
  { href: "/invoices/new", label: "New invoice", icon: "plus" },
  { href: "/approvals", label: "Approvals", icon: "check" },
  { href: "/reconciliation", label: "Reconciliation", icon: "arrows" },
  { href: "/policies", label: "Policies", icon: "shield" },
  { href: "/audit", label: "Audit", icon: "history" },
  { href: "/modules", label: "Modules", icon: "layers" },
];

// Simple SVG icons rendered inline to avoid any dependency
function NavIcon({ name }: { name: string }) {
  const icons: Record<string, ReactNode> = {
    grid: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="1" y="1" width="6" height="6" rx="1" /><rect x="9" y="1" width="6" height="6" rx="1" />
        <rect x="1" y="9" width="6" height="6" rx="1" /><rect x="9" y="9" width="6" height="6" rx="1" />
      </svg>
    ),
    list: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
        <line x1="5" y1="3" x2="15" y2="3" /><line x1="5" y1="8" x2="15" y2="8" /><line x1="5" y1="13" x2="15" y2="13" />
        <circle cx="2" cy="3" r="1" fill="currentColor" /><circle cx="2" cy="8" r="1" fill="currentColor" />
        <circle cx="2" cy="13" r="1" fill="currentColor" />
      </svg>
    ),
    plus: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
        <line x1="8" y1="3" x2="8" y2="13" /><line x1="3" y1="8" x2="13" y2="8" />
      </svg>
    ),
    check: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="3 8 7 12 13 4" />
      </svg>
    ),
    arrows: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="4 2 4 14" /><polyline points="2 4 4 2 6 4" />
        <polyline points="12 14 12 2" /><polyline points="10 12 12 14 14 12" />
      </svg>
    ),
    shield: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 1L2 4v4c0 3.5 2.5 6 6 7 3.5-1 6-3.5 6-7V4L8 1z" />
      </svg>
    ),
    history: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="8" cy="8" r="6.5" /><polyline points="8 4 8 8 11 10" />
      </svg>
    ),
    layers: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="8 1 1 5 8 9 15 5" /><polyline points="1 8 8 12 15 8" />
        <polyline points="1 11 8 15 15 11" />
      </svg>
    ),
  };
  return <span className="sidebar-link-icon">{icons[name] ?? null}</span>;
}

type SessionInfo = { subject: string; display_name: string; roles: string[]; capabilities: string[] };

export function useMe() {
  const { session } = useSession();
  return useQuery({
    queryKey: ["session", session?.subject, session?.organizationId],
    queryFn: () => api<SessionInfo>("/v1/session"),
    enabled: !!session,
  });
}

export function Shell({ children }: { children: ReactNode }) {
  const { session, setSession, ready } = useSession();
  const router = useRouter();
  const path = usePathname();
  const me = useMe();

  const isPublic = path === "/login" || path === "/how-it-works";

  useEffect(() => {
    if (ready && !session && !isPublic) router.replace("/login");
  }, [ready, session, isPublic, router]);

  if (path === "/login") return <>{children}</>;
  if (path === "/how-it-works" && !session) {
    return (
      <div className="min-h-screen" style={{ background: "var(--bg)" }}>
        <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-12">
          <div className="mb-6 flex items-center justify-between border-b pb-4" style={{ borderColor: "var(--border)" }}>
            <span className="text-sm font-semibold tracking-wide" style={{ color: "var(--fg)" }}>
              FinGuard
            </span>
            <Link href="/login" className="btn btn-secondary text-xs">
              &larr; Back to sign in
            </Link>
          </div>
          {children}
        </div>
      </div>
    );
  }
  if (!ready || !session) return null;

  return (
    <div className="min-h-screen md:flex">
      <a href="#main" className="sr-only focus:not-sr-only">
        Skip to content
      </a>
      <nav aria-label="Main" className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-name">FinGuard</div>
          <div className="sidebar-brand-tagline">Evidence and control platform</div>
        </div>
        <div className="sidebar-nav">
          <ul>
            {NAV.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={path === item.href ? "page" : undefined}
                  className="sidebar-link"
                >
                  <NavIcon name={item.icon} />
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div className="sidebar-user">
          <div>
            <div className="sidebar-user-name">{me.data?.display_name ?? session.subject}</div>
            <div className="sidebar-user-role">{me.data?.roles.join(", ").replaceAll("_", " ")}</div>
          </div>
          <button className="btn mt-2 text-xs" onClick={() => setSession(null)}>
            Switch user
          </button>
        </div>
      </nav>
      <main id="main" className="page-content flex-1 space-y-5">
        <div className="notice-banner notice-banner--info">
          <span style={{ flexShrink: 0, fontWeight: 600 }}>Prototype</span>
          <span>Running on synthetic data. Payment execution is simulated. No live provider, bank or customer data is connected.</span>
        </div>
        {children}
      </main>
    </div>
  );
}
