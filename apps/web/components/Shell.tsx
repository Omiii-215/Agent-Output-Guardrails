"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSession } from "@/app/providers";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/queue", label: "Review queue" },
  { href: "/invoices/new", label: "New invoice" },
  { href: "/approvals", label: "Approvals" },
  { href: "/reconciliation", label: "Reconciliation" },
  { href: "/policies", label: "Policies" },
  { href: "/audit", label: "Audit" },
  { href: "/modules", label: "Modules" },
];

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

  useEffect(() => {
    if (ready && !session && path !== "/login") router.replace("/login");
  }, [ready, session, path, router]);

  if (path === "/login") return <>{children}</>;
  if (!ready || !session) return null;

  return (
    <div className="min-h-screen md:flex">
      <a href="#main" className="sr-only focus:not-sr-only">
        Skip to content
      </a>
      <nav aria-label="Main" className="border-b p-4 md:w-56 md:border-r md:border-b-0" style={{ borderColor: "var(--border)" }}>
        <div className="mb-4">
          <div className="font-bold">FinGuard</div>
          <div className="muted text-xs">Evidence &amp; control for financial work</div>
        </div>
        <ul className="flex flex-wrap gap-2 md:flex-col md:gap-1">
          {NAV.map((item) => (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={path === item.href ? "page" : undefined}
                className="block rounded px-2 py-1 text-sm no-underline"
                style={path === item.href ? { background: "var(--border)", color: "var(--text)" } : { color: "var(--text)" }}
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
        <div className="mt-6 space-y-1 text-xs">
          <div className="font-semibold">{me.data?.display_name ?? session.subject}</div>
          <div className="muted">{me.data?.roles.join(", ").replaceAll("_", " ")}</div>
          <button className="btn mt-2 text-xs" onClick={() => setSession(null)}>
            Switch user
          </button>
        </div>
      </nav>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 space-y-4 p-4 md:p-6">
        <p className="rounded px-3 py-2 text-xs" style={{ border: "1px dashed var(--indeterminate)", color: "var(--indeterminate)" }}>
          Prototype on synthetic data. Payment execution is simulated; no live provider, bank or customer data is connected.
        </p>
        {children}
      </main>
    </div>
  );
}
