"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { FinancialPeriod, ImportResult, ModelChecksReport } from "@/lib/types";

export default function FinancialsPage({ params }: { params: { id: string } }) {
  const dealId = params.id;
  const [periods, setPeriods] = useState<FinancialPeriod[]>([]);
  const [checks, setChecks] = useState<ModelChecksReport | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const refresh = useCallback(async () => {
    const [p, c] = await Promise.all([
      api.get<FinancialPeriod[]>(`/api/deals/${dealId}/financials`),
      api.get<ModelChecksReport>(`/api/deals/${dealId}/financials/model-checks`),
    ]);
    setPeriods(p);
    setChecks(c);
  }, [dealId]);

  useEffect(() => {
    refresh().catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, [refresh]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const doc = await api.upload<{ id: string }>(`/api/deals/${dealId}/documents`, file, {
        document_type: "financial_statements",
      });
      const result = await api.upload<ImportResult>(`/api/deals/${dealId}/financials/import`, file, {
        document_id: doc.id,
      });
      setImportResult(result);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function approveSelected() {
    if (selected.size === 0) return;
    await api.post(`/api/deals/${dealId}/financials/approve-mappings`, Array.from(selected));
    setSelected(new Set());
    await refresh();
  }

  const allLineItems = periods.flatMap((p) => p.line_items);
  const unapprovedMapped = allLineItems.filter((li) => li.mapping_status === "proposed" && li.normalized_key);

  return (
    <div className="flex flex-col gap-6">
      <div className="card p-4">
        <label className="flex flex-col gap-2 text-sm">
          <span>
            Upload historical financials (CSV or XLSX). Expected columns: <code>fiscal_year, statement_type,
            label, value, currency, unit_scale</code>. See <code>docs/model-logic.md</code> for the full format.
          </span>
          <input type="file" accept=".csv,.xlsx,.xls" onChange={onUpload} disabled={uploading} />
        </label>
        {uploading && <p className="mt-2 text-xs text-[var(--muted)]">Uploading &amp; importing…</p>}
        {error && <p className="mt-2 text-sm text-[var(--bad)]">{error}</p>}
        {importResult && (
          <p className="mt-2 text-xs text-[var(--muted)]">
            Imported {importResult.line_items_created} line items across {importResult.periods_created} period(s).{" "}
            {importResult.unresolved_mappings > 0 && (
              <span className="text-[var(--warn)]">{importResult.unresolved_mappings} need manual mapping.</span>
            )}
          </p>
        )}
      </div>

      {checks && (
        <div className="card p-4">
          <h3 className="mb-2 text-sm font-medium">Data quality checks</h3>
          <ul className="flex flex-col gap-1 text-sm">
            {checks.checks.map((c, i) => (
              <li key={i} className={c.passed ? "text-[var(--good)]" : c.severity === "error" ? "text-[var(--bad)]" : "text-[var(--warn)]"}>
                {c.passed ? "✓" : "✗"} {c.message}
              </li>
            ))}
            {checks.checks.length === 0 && <li className="text-[var(--muted)]">No checks yet — upload financials first.</li>}
          </ul>
        </div>
      )}

      <div className="card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-medium">Financial line items — original vs. normalized</h3>
          <button
            onClick={approveSelected}
            disabled={selected.size === 0}
            className="rounded bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
          >
            Approve {selected.size > 0 ? `(${selected.size})` : "selected"}
          </button>
        </div>
        {unapprovedMapped.length > 0 && (
          <button
            className="mb-3 text-xs text-[var(--accent)] underline"
            onClick={() => setSelected(new Set(unapprovedMapped.map((li) => li.id)))}
          >
            Select all mapped-but-unapproved ({unapprovedMapped.length})
          </button>
        )}
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th></th>
                <th>FY</th>
                <th>Statement</th>
                <th>Reported label</th>
                <th>Normalized key</th>
                <th>Value</th>
                <th>Confidence</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {periods.flatMap((period) =>
                period.line_items.map((li) => (
                  <tr key={li.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.has(li.id)}
                        onChange={() => toggle(li.id)}
                        disabled={li.mapping_status === "approved"}
                      />
                    </td>
                    <td>{period.fiscal_year}</td>
                    <td className="text-left">{li.statement_type}</td>
                    <td className="text-left">{li.reported_label}</td>
                    <td className="text-left">{li.normalized_key ?? <span className="text-[var(--warn)]">unmapped</span>}</td>
                    <td>{li.value.toLocaleString()}</td>
                    <td>{li.confidence_score != null ? `${Math.round(li.confidence_score * 100)}%` : "—"}</td>
                    <td className="text-left">
                      <span
                        className={
                          li.mapping_status === "approved"
                            ? "text-[var(--good)]"
                            : li.mapping_status === "manual"
                              ? "text-[var(--bad)]"
                              : "text-[var(--warn)]"
                        }
                      >
                        {li.mapping_status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
              {allLineItems.length === 0 && (
                <tr>
                  <td colSpan={8} className="text-center text-[var(--muted)]">
                    No financials uploaded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
