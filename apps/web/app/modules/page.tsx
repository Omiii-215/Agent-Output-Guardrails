"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Loading } from "@/components/ui";

type Module = {
  code: string;
  number: number;
  name: string;
  stage: string;
  enabled: boolean;
  simulation_only: boolean;
  summary: string;
  activation_gate: string;
};

export default function Modules() {
  const modules = useQuery({ queryKey: ["modules"], queryFn: () => api<Module[]>("/v1/modules") });
  if (modules.isLoading) return <Loading />;
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Modules</h1>
      <p className="muted text-sm">
        All eight workflows share identity, evidence, policies, approvals, the action gateway and audit. Modules not yet validated with a
        customer describe their future scope only; they produce no results.
      </p>
      <ul className="grid gap-3 sm:grid-cols-2">
        {(modules.data ?? []).map((m) => (
          <li key={m.code} className="card space-y-1" aria-disabled={!m.enabled}>
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold">
                M{m.number} · {m.name}
              </h2>
              <span className="text-xs font-semibold">
                {m.enabled ? (m.simulation_only ? "Enabled · simulation" : "Enabled") : "Not enabled · future scope"}
              </span>
            </div>
            <p className="text-sm">{m.summary}</p>
            <p className="muted text-xs">
              {m.stage}. Gate: {m.activation_gate}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
