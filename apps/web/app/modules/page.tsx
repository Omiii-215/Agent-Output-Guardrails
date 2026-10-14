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
    <div className="space-y-5">
      <div>
        <h1 className="page-title">Modules</h1>
        <p className="page-description mt-1">
          All eight workflows share identity, evidence, policies, approvals, the action gateway and audit. Modules not yet validated with a
          customer describe their future scope only.
        </p>
      </div>
      <ul className="grid gap-4 sm:grid-cols-2">
        {(modules.data ?? []).map((m) => (
          <li
            key={m.code}
            className="card space-y-2"
            aria-disabled={!m.enabled}
            style={!m.enabled ? { opacity: 0.6 } : undefined}
          >
            <div className="flex items-center justify-between gap-2">
              <h2 className="section-title">
                M{m.number} &middot; {m.name}
              </h2>
              <span
                className={`status-badge ${m.enabled ? "status-pass" : "status-neutral"}`}
              >
                {m.enabled ? (m.simulation_only ? "Simulation" : "Enabled") : "Future scope"}
              </span>
            </div>
            <p className="text-sm text-secondary">{m.summary}</p>
            <p className="muted" style={{ fontSize: "0.75rem" }}>
              {m.stage}. Gate: {m.activation_gate}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
