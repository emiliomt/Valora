"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, getToken } from "@/lib/api";
import type { ModelVersion, Scenario, SensitivityGrid, ValuationRunOut } from "@/lib/types";
import { SCENARIOS } from "@/lib/types";

const fmt = (n: number | null | undefined, digits = 0) =>
  n == null || Number.isNaN(n) ? "—" : n.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
const pct = (n: number | null | undefined) => (n == null ? "—" : `${(n * 100).toFixed(1)}%`);

export default function ValuationPage({ params }: { params: { id: string } }) {
  const dealId = params.id;
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [activeVersion, setActiveVersion] = useState<ModelVersion | null>(null);
  const [results, setResults] = useState<ValuationRunOut | null>(null);
  const [scenario, setScenario] = useState<Scenario>("base");
  const [sensitivity, setSensitivity] = useState<SensitivityGrid | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [newVersionName, setNewVersionName] = useState("IC v1");

  const refreshVersions = useCallback(async () => {
    const vs = await api.get<ModelVersion[]>(`/api/deals/${dealId}/model-versions`);
    setVersions(vs);
    if (vs.length > 0 && !activeVersion) setActiveVersion(vs[0]);
  }, [dealId, activeVersion]);

  useEffect(() => {
    refreshVersions().catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dealId]);

  useEffect(() => {
    if (!activeVersion) return;
    api
      .get<ValuationRunOut>(`/api/model-versions/${activeVersion.id}/outputs`)
      .then(setResults)
      .catch(() => setResults(null));
  }, [activeVersion]);

  useEffect(() => {
    if (!activeVersion || !results?.scenarios[scenario]) {
      setSensitivity(null);
      return;
    }
    api
      .get<SensitivityGrid>(`/api/model-versions/${activeVersion.id}/sensitivities/wacc-vs-growth`, { scenario })
      .then(setSensitivity)
      .catch(() => setSensitivity(null));
  }, [activeVersion, results, scenario]);

  async function createVersion() {
    setBusy(true);
    setError(null);
    try {
      const mv = await api.post<ModelVersion>(`/api/deals/${dealId}/model-versions`, { name: newVersionName });
      setVersions((prev) => [mv, ...prev]);
      setActiveVersion(mv);
      setResults(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create model version");
    } finally {
      setBusy(false);
    }
  }

  async function calculate() {
    if (!activeVersion) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api.post<ValuationRunOut>(`/api/model-versions/${activeVersion.id}/calculate`);
      setResults(out);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Calculation failed");
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    if (!activeVersion) return;
    setBusy(true);
    setError(null);
    try {
      const mv = await api.post<ModelVersion>(`/api/model-versions/${activeVersion.id}/approve`);
      setActiveVersion(mv);
      setVersions((prev) => prev.map((v) => (v.id === mv.id ? mv : v)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  }

  async function exportXlsx() {
    if (!activeVersion) return;
    setBusy(true);
    setError(null);
    try {
      const job = await api.post<{ export_job_id: string }>(`/api/model-versions/${activeVersion.id}/exports/xlsx`);
      const token = getToken();
      const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
      const res = await fetch(`${apiBase}/api/exports/${job.export_job_id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${activeVersion.name.replace(/\s+/g, "_")}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }

  const scenarioResult = results?.scenarios[scenario];

  return (
    <div className="flex flex-col gap-6">
      <div className="card flex flex-wrap items-center gap-3 p-4">
        <select
          className="rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
          value={activeVersion?.id ?? ""}
          onChange={(e) => setActiveVersion(versions.find((v) => v.id === e.target.value) ?? null)}
        >
          {versions.length === 0 && <option>No model versions yet</option>}
          {versions.map((v) => (
            <option key={v.id} value={v.id} className="bg-[var(--panel)]">
              {v.name} ({v.status})
            </option>
          ))}
        </select>
        <input
          className="rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
          value={newVersionName}
          onChange={(e) => setNewVersionName(e.target.value)}
          placeholder="New version name"
        />
        <button onClick={createVersion} disabled={busy} className="rounded border border-[var(--border)] px-3 py-1.5 text-sm">
          + New version
        </button>
        {activeVersion && (
          <>
            <button onClick={calculate} disabled={busy} className="rounded bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white">
              Calculate
            </button>
            <button
              onClick={approve}
              disabled={busy || activeVersion.status === "approved" || !results}
              className="rounded border border-[var(--good)] px-3 py-1.5 text-sm text-[var(--good)] disabled:opacity-40"
            >
              {activeVersion.status === "approved" ? "Approved" : "Approve"}
            </button>
            <button
              onClick={exportXlsx}
              disabled={busy || activeVersion.status !== "approved"}
              className="rounded border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-40"
              title={activeVersion.status !== "approved" ? "Approve the model version before exporting" : ""}
            >
              Export XLSX
            </button>
          </>
        )}
      </div>

      {error && <p className="text-sm text-[var(--bad)]">{error}</p>}

      {results && (
        <>
          <div className="flex gap-2">
            {SCENARIOS.filter((s) => results.scenarios[s]).map((s) => (
              <button
                key={s}
                onClick={() => setScenario(s)}
                className={`rounded px-3 py-1.5 text-sm capitalize ${
                  scenario === s ? "bg-[var(--accent)] text-white" : "border border-[var(--border)] text-[var(--muted)]"
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          {scenarioResult && (
            <>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                {[
                  ["Enterprise Value", fmt(scenarioResult.dcf.enterprise_value)],
                  ["Equity Value", fmt(scenarioResult.dcf.equity_value)],
                  ["Value / Share", scenarioResult.dcf.implied_value_per_share != null ? fmt(scenarioResult.dcf.implied_value_per_share, 2) : "—"],
                  ["TV % of EV", pct(scenarioResult.dcf.terminal_value_pct_of_ev)],
                ].map(([label, value]) => (
                  <div key={label} className="card p-4">
                    <p className="text-xs text-[var(--muted)]">{label}</p>
                    <p className="mt-1 text-xl font-semibold">{value}</p>
                  </div>
                ))}
              </div>

              {scenarioResult.model_checks.checks.some((c) => !c.passed) && (
                <div className="card p-4">
                  <h3 className="mb-2 text-sm font-medium">Model checks</h3>
                  <ul className="flex flex-col gap-1 text-sm">
                    {scenarioResult.model_checks.checks
                      .filter((c) => !c.passed)
                      .map((c, i) => (
                        <li key={i} className={c.severity === "error" ? "text-[var(--bad)]" : "text-[var(--warn)]"}>
                          {c.severity === "error" ? "✗" : "⚠"} {c.message}
                        </li>
                      ))}
                  </ul>
                </div>
              )}

              <div className="card overflow-x-auto p-4">
                <h3 className="mb-2 text-sm font-medium">Forecast &amp; UFCF — {scenario}</h3>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>FY</th>
                      <th>Revenue</th>
                      <th>EBITDA</th>
                      <th>EBIT</th>
                      <th>NOPAT</th>
                      <th>Capex</th>
                      <th>Δ NWC</th>
                      <th>UFCF</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scenarioResult.forecast.map((row) => (
                      <tr key={row.fiscal_year}>
                        <td>{row.fiscal_year}</td>
                        <td>{fmt(row.revenue)}</td>
                        <td>{fmt(row.ebitda)}</td>
                        <td>{fmt(row.ebit)}</td>
                        <td>{fmt(row.nopat)}</td>
                        <td>{fmt(row.capex)}</td>
                        <td>{fmt(row.change_in_nwc)}</td>
                        <td className="font-medium">{fmt(row.ufcf)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {sensitivity && (
                <div className="card overflow-x-auto p-4">
                  <h3 className="mb-2 text-sm font-medium">
                    Sensitivity: {sensitivity.row_label} vs {sensitivity.column_label} (Enterprise Value)
                  </h3>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>WACC \ g</th>
                        {sensitivity.column_values.map((g) => (
                          <th key={g}>{pct(g)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sensitivity.row_values.map((w, ri) => (
                        <tr key={w}>
                          <td>{pct(w)}</td>
                          {sensitivity.grid[ri].map((v, ci) => (
                            <td key={ci}>{v == null || Number.isNaN(v) ? "n/a" : fmt(v)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </>
      )}

      {!results && activeVersion && <p className="text-sm text-[var(--muted)]">Not calculated yet — click Calculate.</p>}
      {!activeVersion && <p className="text-sm text-[var(--muted)]">Create a model version to run a valuation.</p>}
    </div>
  );
}
