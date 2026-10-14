"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useSession } from "@/app/providers";
import { api } from "@/lib/api";
import { PERSONAS } from "@/lib/session";
import { ErrorNote } from "@/components/ui";

type Me = { memberships: { organization_id: string; organization_name: string; roles: string[] }[] };

export default function LoginPage() {
  const { setSession } = useSession();
  const router = useRouter();
  const [subject, setSubject] = useState(PERSONAS[0].subject);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  async function signIn(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      setSession({ subject, organizationId: null });
      const me = await api<Me>("/v1/me");
      if (me.memberships.length === 0) throw new Error("This identity has no active membership.");
      setSession({ subject, organizationId: me.memberships[0].organization_id });
      router.push("/");
    } catch (err) {
      setSession(null);
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      className="flex min-h-screen items-center justify-center p-4"
      style={{ background: "var(--bg)" }}
    >
      <div className="w-full max-w-sm space-y-5">
        <div className="text-center">
          <h1 className="page-title" style={{ fontSize: "1.5rem" }}>FinGuard</h1>
          <p className="page-description mx-auto mt-1" style={{ fontSize: "0.82rem" }}>
            Development sign-in. Choose a synthetic persona to explore the platform.
          </p>
        </div>
        <form onSubmit={signIn} className="card space-y-4">
          <label className="block text-sm font-medium" htmlFor="persona">
            Persona
          </label>
          <select id="persona" value={subject} onChange={(e) => setSubject(e.target.value)}>
            {PERSONAS.map((p) => (
              <option key={p.subject} value={p.subject}>
                {p.label} &mdash; {p.subject}
              </option>
            ))}
          </select>
          <p className="page-description" style={{ fontSize: "0.76rem", marginTop: "0.25rem" }}>
            This stub exists only in development. Staging and production use OIDC.
          </p>
          <ErrorNote error={error} />
          <button type="submit" className="btn btn-primary w-full" disabled={loading}>
            {loading ? "Signing in\u2026" : "Continue"}
          </button>
        </form>

        <div className="pt-1 text-center">
          <Link
            href="/how-it-works"
            className="btn btn-secondary w-full block text-center"
            style={{ textDecoration: "none" }}
          >
            How our product works &amp; roles guide
          </Link>
        </div>
      </div>
    </main>
  );
}
