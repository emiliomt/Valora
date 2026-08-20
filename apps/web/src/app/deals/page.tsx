"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { Deal, Workspace } from "@/lib/types";

export default function DealsPage() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<string | null>(null);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [newDealName, setNewDealName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    (async () => {
      try {
        const ws = await api.get<Workspace[]>("/api/workspaces");
        setWorkspaces(ws);
        if (ws.length > 0) setActiveWorkspace(ws[0].id);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load workspaces");
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  useEffect(() => {
    if (!activeWorkspace) return;
    api
      .get<Deal[]>("/api/deals", { workspace_id: activeWorkspace })
      .then(setDeals)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load deals"));
  }, [activeWorkspace]);

  async function createWorkspace(e: React.FormEvent) {
    e.preventDefault();
    if (!newWorkspaceName.trim()) return;
    const ws = await api.post<Workspace>("/api/workspaces", { name: newWorkspaceName });
    setWorkspaces((prev) => [...prev, ws]);
    setActiveWorkspace(ws.id);
    setNewWorkspaceName("");
  }

  async function createDeal(e: React.FormEvent) {
    e.preventDefault();
    if (!activeWorkspace || !newDealName.trim()) return;
    try {
      const deal = await api.post<Deal>("/api/deals", {
        workspace_id: activeWorkspace,
        company_name: newDealName,
      });
      setDeals((prev) => [...prev, deal]);
      setNewDealName("");
      router.push(`/deals/${deal.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create deal");
    }
  }

  if (loading) return <p className="text-sm text-[var(--muted)]">Loading…</p>;

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Deals</h1>
        <button
          onClick={() => {
            clearToken();
            router.push("/login");
          }}
          className="text-sm text-[var(--muted)] hover:text-[var(--text)]"
        >
          Sign out
        </button>
      </div>

      {error && <p className="mb-4 text-sm text-[var(--bad)]">{error}</p>}

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <label className="text-sm text-[var(--muted)]">Workspace</label>
        <select
          className="rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
          value={activeWorkspace ?? ""}
          onChange={(e) => setActiveWorkspace(e.target.value)}
        >
          {workspaces.map((w) => (
            <option key={w.id} value={w.id} className="bg-[var(--panel)]">
              {w.name}
            </option>
          ))}
        </select>
        <form onSubmit={createWorkspace} className="flex items-center gap-2">
          <input
            className="rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
            placeholder="New workspace name"
            value={newWorkspaceName}
            onChange={(e) => setNewWorkspaceName(e.target.value)}
          />
          <button className="rounded border border-[var(--border)] px-2 py-1 text-sm" type="submit">
            + Workspace
          </button>
        </form>
      </div>

      {activeWorkspace && (
        <form onSubmit={createDeal} className="card mb-6 flex items-center gap-3 p-4">
          <input
            className="flex-1 rounded border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
            placeholder="Company name (e.g. Acme Corp)"
            value={newDealName}
            onChange={(e) => setNewDealName(e.target.value)}
          />
          <button className="rounded bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white" type="submit">
            Create deal
          </button>
        </form>
      )}

      <div className="card divide-y divide-[var(--border)]">
        {deals.length === 0 && <p className="p-4 text-sm text-[var(--muted)]">No deals yet in this workspace.</p>}
        {deals.map((deal) => (
          <Link
            key={deal.id}
            href={`/deals/${deal.id}`}
            className="flex items-center justify-between p-4 hover:bg-white/5"
          >
            <div>
              <p className="font-medium">{deal.company_name}</p>
              <p className="text-xs text-[var(--muted)]">
                {deal.industry} · {deal.investment_type} · {deal.status}
              </p>
            </div>
            <span
              className={`rounded-full px-2 py-1 text-xs ${
                deal.ready_for_valuation ? "bg-[var(--good)]/20 text-[var(--good)]" : "bg-[var(--warn)]/20 text-[var(--warn)]"
              }`}
            >
              {deal.ready_for_valuation ? "Ready for valuation" : "Setup incomplete"}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
