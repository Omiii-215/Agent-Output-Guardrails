"use client";

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

  async function signIn(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      setSession({ subject, organizationId: null });
      const me = await api<Me>("/v1/me");
      if (me.memberships.length === 0) throw new Error("This identity has no active membership.");
      setSession({ subject, organizationId: me.memberships[0].organization_id });
      router.push("/");
    } catch (err) {
      setSession(null);
      setError(err);
    }
  }

  return (
    <main className="mx-auto mt-16 max-w-md space-y-4 p-4">
      <h1 className="text-xl font-bold">FinGuard development sign-in</h1>
      <p className="muted text-sm">
        Choose a synthetic persona from the seeded organizations. This stub exists only in development;
        staging and production sign in through OIDC.
      </p>
      <form onSubmit={signIn} className="card space-y-3">
        <label className="block text-sm font-medium" htmlFor="persona">
          Persona
        </label>
        <select id="persona" value={subject} onChange={(e) => setSubject(e.target.value)}>
          {PERSONAS.map((p) => (
            <option key={p.subject} value={p.subject}>
              {p.label} — {p.subject}
            </option>
          ))}
        </select>
        <ErrorNote error={error} />
        <button type="submit" className="btn btn-primary w-full">
          Continue
        </button>
      </form>
    </main>
  );
}
