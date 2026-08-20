"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Deal } from "@/lib/types";

const CURRENCIES = ["USD", "EUR", "GBP", "MXN", "BRL", "CAD"];

export default function DealOverviewPage({ params }: { params: { id: string } }) {
  const [deal, setDeal] = useState<Deal | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    currency: "",
    valuation_date: "",
    fiscal_year_end: "",
    forecast_years: 5,
    investment_thesis: "",
    industry: "general",
  });

  useEffect(() => {
    api.get<Deal>(`/api/deals/${params.id}`).then((d) => {
      setDeal(d);
      setForm({
        currency: d.currency ?? "USD",
        valuation_date: d.valuation_date ?? "",
        fiscal_year_end: d.fiscal_year_end ?? "12-31",
        forecast_years: d.forecast_years,
        investment_thesis: d.investment_thesis ?? "",
        industry: d.industry,
      });
    });
  }, [params.id]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await api.patch<Deal>(`/api/deals/${params.id}`, form);
      setDeal(updated);
    } finally {
      setSaving(false);
    }
  }

  if (!deal) return <p className="text-sm text-[var(--muted)]">Loading…</p>;

  return (
    <div className="card max-w-xl p-6">
      <h2 className="mb-4 text-lg font-medium">Deal setup</h2>
      <p className="mb-4 text-sm text-[var(--muted)]">
        Currency, valuation date, fiscal year end, and forecast period must be set before a valuation can be run
        (PRD 7.2).
      </p>
      <form onSubmit={save} className="flex flex-col gap-4">
        <label className="text-sm">
          Industry
          <select
            className="mt-1 w-full rounded border border-[var(--border)] bg-transparent px-3 py-2"
            value={form.industry}
            onChange={(e) => setForm((f) => ({ ...f, industry: e.target.value }))}
          >
            {["general", "saas", "fintech", "consumer_ecommerce", "healthcare_telehealth", "industrial_hardware"].map(
              (i) => (
                <option key={i} value={i} className="bg-[var(--panel)]">
                  {i}
                </option>
              )
            )}
          </select>
        </label>
        <label className="text-sm">
          Currency
          <select
            className="mt-1 w-full rounded border border-[var(--border)] bg-transparent px-3 py-2"
            value={form.currency}
            onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value }))}
          >
            {CURRENCIES.map((c) => (
              <option key={c} value={c} className="bg-[var(--panel)]">
                {c}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Valuation date
          <input
            type="date"
            className="mt-1 w-full rounded border border-[var(--border)] bg-transparent px-3 py-2"
            value={form.valuation_date}
            onChange={(e) => setForm((f) => ({ ...f, valuation_date: e.target.value }))}
          />
        </label>
        <label className="text-sm">
          Fiscal year end (MM-DD)
          <input
            className="mt-1 w-full rounded border border-[var(--border)] bg-transparent px-3 py-2"
            value={form.fiscal_year_end}
            onChange={(e) => setForm((f) => ({ ...f, fiscal_year_end: e.target.value }))}
            placeholder="12-31"
          />
        </label>
        <label className="text-sm">
          Forecast years
          <input
            type="number"
            min={1}
            max={10}
            className="mt-1 w-full rounded border border-[var(--border)] bg-transparent px-3 py-2"
            value={form.forecast_years}
            onChange={(e) => setForm((f) => ({ ...f, forecast_years: Number(e.target.value) }))}
          />
        </label>
        <label className="text-sm">
          Investment thesis (optional)
          <textarea
            className="mt-1 w-full rounded border border-[var(--border)] bg-transparent px-3 py-2"
            rows={4}
            value={form.investment_thesis}
            onChange={(e) => setForm((f) => ({ ...f, investment_thesis: e.target.value }))}
          />
        </label>
        <button
          type="submit"
          disabled={saving}
          className="self-start rounded bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {saving ? "Saving…" : "Save"}
        </button>
      </form>
    </div>
  );
}
