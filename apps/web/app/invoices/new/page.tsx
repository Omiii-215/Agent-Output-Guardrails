"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, idempotencyKey, uploadFile } from "@/lib/api";
import { ErrorNote, Section, Status } from "@/components/ui";

type Vendor = { id: string; name: string; beneficiary: { verification_status: string; account_masked: string } | null };
type Line = { description: string; quantity: string; unit_price: string; tax_rate: string };

export default function NewInvoice() {
  const router = useRouter();
  const vendors = useQuery({ queryKey: ["vendors"], queryFn: () => api<Vendor[]>("/v1/vendors") });
  const [vendorId, setVendorId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({ currency: "INR" });
  const [lines, setLines] = useState<Line[]>([]);
  // One key per form instance: resubmitting after a network error cannot create a second case.
  const [key] = useState(() => idempotencyKey("invoice"));

  const create = useMutation({
    mutationFn: async () => {
      let documentId: string | null = null;
      if (file) {
        const doc = await uploadFile(file);
        if (doc.status !== "CLEAN") throw new Error(`Upload rejected: ${doc.rejection_reason}`);
        documentId = doc.id;
      }
      const filled = Object.fromEntries(Object.entries(fields).filter(([, v]) => v));
      return api<{ case_id: string }>("/v1/invoices", {
        method: "POST",
        headers: { "Idempotency-Key": key },
        json: {
          vendor_id: vendorId,
          document_version_id: documentId,
          extract: !!documentId,
          fields: filled,
          lines: lines.filter((l) => l.quantity && l.unit_price),
        },
      });
    },
    onSuccess: (r) => router.push(`/cases/${r.case_id}`),
  });

  const field = (name: string, label: string, placeholder = "") => (
    <label className="text-sm">
      {label}
      <input value={fields[name] ?? ""} placeholder={placeholder} onChange={(e) => setFields({ ...fields, [name]: e.target.value })} />
    </label>
  );

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">New invoice</h1>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Section title="Vendor and source">
          <label className="block text-sm">
            Vendor
            <select required value={vendorId} onChange={(e) => setVendorId(e.target.value)}>
              <option value="">Choose…</option>
              {(vendors.data ?? []).map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} {v.beneficiary ? `· ${v.beneficiary.account_masked} (${v.beneficiary.verification_status.toLowerCase()})` : "· no payee"}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            Invoice document (PDF). Its text is extracted and every value must be confirmed by a person.
            <input type="file" accept="application/pdf,text/plain" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          {vendorId ? (
            <p className="text-sm">
              Payee status:{" "}
              <Status value={vendors.data?.find((v) => v.id === vendorId)?.beneficiary?.verification_status ?? "UNVERIFIED"} />
            </p>
          ) : null}
        </Section>
        <Section title="Fields (optional when a document is attached)">
          <div className="grid gap-3 sm:grid-cols-3">
            {field("invoice_number", "Invoice number")}
            {field("invoice_date", "Invoice date", "YYYY-MM-DD")}
            {field("due_date", "Due date", "YYYY-MM-DD")}
            {field("currency", "Currency")}
            {field("total", "Total (major units)", "5900.00")}
            {field("po_number", "PO number")}
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium">Line items</div>
            {lines.map((l, i) => (
              <div key={i} className="grid gap-2 sm:grid-cols-4">
                {(["description", "quantity", "unit_price", "tax_rate"] as const).map((k) => (
                  <input
                    key={k}
                    aria-label={`Line ${i + 1} ${k}`}
                    placeholder={k === "tax_rate" ? "0.18" : k.replace("_", " ")}
                    value={l[k]}
                    onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, [k]: e.target.value } : x)))}
                  />
                ))}
              </div>
            ))}
            <button type="button" className="btn text-sm" onClick={() => setLines([...lines, { description: "", quantity: "", unit_price: "", tax_rate: "0.18" }])}>
              Add line
            </button>
          </div>
        </Section>
        <ErrorNote error={create.error} />
        <button className="btn btn-primary" disabled={!vendorId || create.isPending}>
          {create.isPending ? "Submitting…" : "Create review case"}
        </button>
      </form>
    </div>
  );
}
