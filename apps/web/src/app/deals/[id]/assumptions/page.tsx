"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { api, ApiError } from "@/lib/api";
import {
  ASSUMPTION_KEYS,
  ASSUMPTION_LABELS,
  SCENARIOS,
  type AssumptionSet,
  type Deal,
  type FinancialPeriod,
  type Scenario,
} from "@/lib/types";

type YearAssumptions = Record<(typeof ASSUMPTION_KEYS)[number], number>;

const scenarioMetaSchema = z.object({
  wacc: z.number().gt(0).lt(1),
  terminal_growth_rate: z.number().gte(-0.05).lt(1),
});

const DEFAULT_ROW: YearAssumptions = {
  revenue_growth_rate: 0.1,
  gross_margin: 0.5,
  opex_pct_of_revenue: 0.3,
  d_and_a_pct_of_revenue: 0.03,
  capex_pct_of_revenue: 0.03,
  nwc_pct_of_revenue: 0.05,
  tax_rate: 0.25,
};

export default function AssumptionsPage({ params }: { params: { id: string } }) {
  const dealId = params.id;
  const [deal, setDeal] = useState<Deal | null>(null);
  const [forecastYears, setForecastYears] = useState<number[]>([]);
  const [scenario, setScenario] = useState<Scenario>("base");
  const [wacc, setWacc] = useState(0.1);
  const [terminalGrowth, setTerminalGrowth] = useState(0.025);
  const [rows, setRows] = useState<Record<number, YearAssumptions>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    (async () => {
      const [d, periods] = await Promise.all([
        api.get<Deal>(`/api/deals/${dealId}`),
        api.get<FinancialPeriod[]>(`/api/deals/${dealId}/financials`),
      ]);
      setDeal(d);
      const historicalYears = periods.filter((p) => p.is_historical).map((p) => p.fiscal_year);
      const lastHistorical = historicalYears.length > 0 ? Math.max(...historicalYears) : new Date().getFullYear();
      setForecastYears(Array.from({ length: d.forecast_years }, (_, i) => lastHistorical + i + 1));
    })();
  }, [dealId]);

  const loadScenario = useCallback(
    async (s: Scenario) => {
      try {
        const sets = await api.get<AssumptionSet[]>(`/api/deals/${dealId}/assumptions`);
        const found = sets.find((set) => set.scenario === s);
        if (found) {
          setWacc(found.wacc);
          setTerminalGrowth(found.terminal_growth_rate);
          const byYear: Record<number, YearAssumptions> = {};
          for (const a of found.assumptions) {
            byYear[a.fiscal_year] = byYear[a.fiscal_year] ?? { ...DEFAULT_ROW };
            (byYear[a.fiscal_year] as Record<string, number>)[a.key] = a.value;
          }
          setRows(byYear);
        } else {
          setWacc(0.1);
          setTerminalGrowth(0.025);
          setRows({});
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load assumptions");
      }
    },
    [dealId]
  );

  useEffect(() => {
    loadScenario(scenario);
  }, [scenario, loadScenario]);

  function rowFor(fy: number): YearAssumptions {
    return rows[fy] ?? DEFAULT_ROW;
  }

  function setCell(fy: number, key: (typeof ASSUMPTION_KEYS)[number], value: number) {
    setRows((prev) => ({
      ...prev,
      [fy]: { ...(prev[fy] ?? DEFAULT_ROW), [key]: value },
    }));
  }

  function applyToAllYears(key: (typeof ASSUMPTION_KEYS)[number], value: number) {
    setRows((prev) => {
      const next: Record<number, YearAssumptions> = { ...prev };
      for (const fy of forecastYears) {
        next[fy] = { ...(next[fy] ?? DEFAULT_ROW), [key]: value };
      }
      return next;
    });
  }

  const valid = useMemo(() => scenarioMetaSchema.safeParse({ wacc, terminal_growth_rate: terminalGrowth }).success && wacc > terminalGrowth, [
    wacc,
    terminalGrowth,
  ]);

  async function save() {
    setError(null);
    if (!valid) {
      setError("WACC must be greater than the terminal growth rate.");
      return;
    }
    setSaving(true);
    try {
      const assumptions = forecastYears.flatMap((fy) =>
        ASSUMPTION_KEYS.map((key) => ({
          key,
          fiscal_year: fy,
          value: rowFor(fy)[key],
          origin: "user" as const,
        }))
      );
      await api.put(`/api/deals/${dealId}/assumptions/${scenario}`, {
        scenario,
        wacc,
        terminal_growth_rate: terminalGrowth,
        assumptions,
      });
      setSavedAt(Date.now());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save assumptions");
    } finally {
      setSaving(false);
    }
  }

  async function cloneFromBase() {
    if (scenario === "base") return;
    await api.post(`/api/deals/${dealId}/assumptions/base/clone-to/${scenario}`);
    await loadScenario(scenario);
  }

  if (!deal) return <p className="text-sm text-[var(--muted)]">Loading…</p>;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-2">
        {SCENARIOS.map((s) => (
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
        {scenario !== "base" && (
          <button onClick={cloneFromBase} className="ml-2 text-xs text-[var(--accent)] underline">
            Clone from base
          </button>
        )}
      </div>

      <div className="card flex flex-wrap gap-6 p-4">
        <label className="text-sm">
          WACC
          <input
            type="number"
            step="0.001"
            className="mt-1 block w-32 rounded border border-[var(--border)] bg-transparent px-2 py-1"
            value={wacc}
            onChange={(e) => setWacc(Number(e.target.value))}
          />
        </label>
        <label className="text-sm">
          Terminal growth rate
          <input
            type="number"
            step="0.001"
            className="mt-1 block w-32 rounded border border-[var(--border)] bg-transparent px-2 py-1"
            value={terminalGrowth}
            onChange={(e) => setTerminalGrowth(Number(e.target.value))}
          />
        </label>
        {!valid && <p className="self-end text-sm text-[var(--bad)]">Terminal growth must be below WACC.</p>}
      </div>

      <div className="card overflow-x-auto p-4">
        <table className="data-table">
          <thead>
            <tr>
              <th>Driver</th>
              {forecastYears.map((fy) => (
                <th key={fy}>FY{fy}</th>
              ))}
              <th>Apply →</th>
            </tr>
          </thead>
          <tbody>
            {ASSUMPTION_KEYS.map((key) => (
              <tr key={key}>
                <td className="text-left">{ASSUMPTION_LABELS[key]}</td>
                {forecastYears.map((fy) => (
                  <td key={fy}>
                    <input
                      type="number"
                      step="0.001"
                      className="w-20 rounded border border-[var(--border)] bg-transparent px-1 py-0.5 text-right"
                      value={rowFor(fy)[key]}
                      onChange={(e) => setCell(fy, key, Number(e.target.value))}
                    />
                  </td>
                ))}
                <td>
                  <button
                    className="text-xs text-[var(--accent)] underline"
                    onClick={() => applyToAllYears(key, rowFor(forecastYears[0] ?? 0)[key])}
                    title="Apply year 1's value across all forecast years"
                  >
                    apply all
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {error && <p className="text-sm text-[var(--bad)]">{error}</p>}
      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={saving}
          className="self-start rounded bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {saving ? "Saving…" : `Save ${scenario} assumptions`}
        </button>
        {savedAt && <span className="text-xs text-[var(--good)]">Saved.</span>}
      </div>
    </div>
  );
}
