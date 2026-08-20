"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { api, getToken } from "@/lib/api";
import type { Deal } from "@/lib/types";

const TABS = [
  { href: "", label: "Overview" },
  { href: "/financials", label: "Financials" },
  { href: "/assumptions", label: "Assumptions" },
  { href: "/valuation", label: "Valuation" },
];

export default function DealLayout({ children, params }: { children: React.ReactNode; params: { id: string } }) {
  const router = useRouter();
  const pathname = usePathname();
  const [deal, setDeal] = useState<Deal | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api.get<Deal>(`/api/deals/${params.id}`).then(setDeal).catch(() => setDeal(null));
  }, [params.id, router]);

  const base = `/deals/${params.id}`;

  return (
    <div>
      <div className="mb-2">
        <Link href="/deals" className="text-xs text-[var(--muted)] hover:text-[var(--text)]">
          ← All deals
        </Link>
      </div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{deal?.company_name ?? "Loading…"}</h1>
          {deal && (
            <p className="text-xs text-[var(--muted)]">
              {deal.currency ?? "no currency set"} · Forecast {deal.forecast_years}y · Status: {deal.status}
            </p>
          )}
        </div>
        {deal && !deal.ready_for_valuation && (
          <span className="rounded-full bg-[var(--warn)]/20 px-2 py-1 text-xs text-[var(--warn)]">
            Setup incomplete — set currency, valuation date, fiscal year end &amp; forecast years
          </span>
        )}
      </div>

      <nav className="mb-6 flex gap-1 border-b border-[var(--border)] text-sm">
        {TABS.map((tab) => {
          const href = `${base}${tab.href}`;
          const active = pathname === href || (tab.href === "" && pathname === base);
          return (
            <Link
              key={tab.href}
              href={href}
              className={`border-b-2 px-3 py-2 ${
                active ? "border-[var(--accent)] text-[var(--text)]" : "border-transparent text-[var(--muted)]"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>

      {children}
    </div>
  );
}
