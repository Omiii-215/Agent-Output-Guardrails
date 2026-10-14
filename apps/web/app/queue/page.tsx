"use client";

import Link from "next/link";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { ErrorNote, Loading, Status } from "@/components/ui";

type CaseRow = {
  id: string;
  title: string;
  module: string;
  status: string;
  outcome: string | null;
  owner_subject: string | null;
  updated_at: string;
};

const STATUSES = ["", "NEEDS_INFORMATION", "READY_TO_EVALUATE", "IN_REVIEW", "READY_FOR_ACTION", "ACTION_PENDING", "RESOLVED", "CLOSED"];

export default function Queue() {
  const [status, setStatus] = useState("");
  const [module, setModule] = useState("");
  const query = useInfiniteQuery({
    queryKey: ["cases", status, module],
    initialPageParam: "",
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: "50" });
      if (status) params.set("status", status);
      if (module) params.set("module", module);
      if (pageParam) params.set("cursor", pageParam);
      return api<{ items: CaseRow[]; next_cursor: string | null }>(`/v1/cases?${params}`);
    },
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const rows = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">Review queue</h1>
        <p className="page-description mt-1">All cases across modules. Filter by status or module to narrow the list.</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <label className="text-sm font-medium">
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s ? s.replaceAll("_", " ") : "Any"}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium">
          Module
          <select value={module} onChange={(e) => setModule(e.target.value)}>
            <option value="">Any</option>
            <option value="invoices">Invoices</option>
            <option value="reconciliation">Reconciliation</option>
          </select>
        </label>
      </div>
      <ErrorNote error={query.error} />
      {query.isLoading ? (
        <Loading />
      ) : (
        <div className="card overflow-x-auto">
          <table>
            <caption className="sr-only">Cases</caption>
            <thead>
              <tr>
                <th scope="col">Case</th>
                <th scope="col">Module</th>
                <th scope="col">Status</th>
                <th scope="col">Latest outcome</th>
                <th scope="col">Owner</th>
                <th scope="col">Updated</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link href={`/cases/${c.id}`} className="font-medium">{c.title}</Link>
                  </td>
                  <td className="text-sm text-secondary">{c.module}</td>
                  <td>
                    <Status value={c.status} />
                  </td>
                  <td>
                    <Status value={c.outcome} />
                  </td>
                  <td className="text-sm text-secondary">{c.owner_subject ?? "\u2014"}</td>
                  <td className="muted text-sm">{new Date(c.updated_at).toLocaleString()}</td>
                </tr>
              ))}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="muted py-6 text-center">
                    No cases match the current filters.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
          {query.hasNextPage ? (
            <div className="mt-3 flex justify-center">
              <button className="btn" onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage}>
                Load more
              </button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
