"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { Deal, Workspace } from "@/lib/types";

const DEFAULT_WORKSPACE_NAME = "Personal";

export default function DealsPage() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<string | null>(null);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [newDealName, setNewDealName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creatingWorkspace, setCreatingWorkspace] = useState(false);
  const [creatingDeal, setCreatingDeal] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    (async () => {
      try {
        let ws = await api.get<Workspace[]>("/api/workspaces");
        // Accounts created before register auto-provisioned a workspace still land here
        // with none. Create a default so the new-deal workflow is always available.
        if (ws.length === 0) {
          const created = await api.post<Workspace>("/api/workspaces", { name: DEFAULT_WORKSPACE_NAME });
          ws = [created];
        }
        setWorkspaces(ws);
        setActiveWorkspace(ws[0].id);
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

  async function ensureWorkspace(): Promise<string | null> {
    if (activeWorkspace) return activeWorkspace;
    try {
      const created = await api.post<Workspace>("/api/workspaces", { name: DEFAULT_WORKSPACE_NAME });
      setWorkspaces((prev) => (prev.some((w) => w.id === created.id) ? prev : [...prev, created]));
      setActiveWorkspace(created.id);
      return created.id;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create workspace");
      return null;
    }
  }

  async function createWorkspace(e: React.FormEvent) {
    e.preventDefault();
    const name = newWorkspaceName.trim();
    if (!name) {
      setError("Enter a workspace name to create one.");
      return;
    }
    setError(null);
    setCreatingWorkspace(true);
    try {
      const ws = await api.post<Workspace>("/api/workspaces", { name });
      setWorkspaces((prev) => [...prev, ws]);
      setActiveWorkspace(ws.id);
      setNewWorkspaceName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create workspace");
    } finally {
      setCreatingWorkspace(false);
    }
  }

  async function createDeal(e: React.FormEvent) {
    e.preventDefault();
    const companyName = newDealName.trim();
    if (!companyName) {
      setError("Enter a company name to start a deal.");
      return;
    }
    setError(null);
    setCreatingDeal(true);
    try {
      const workspaceId = await ensureWorkspace();
      if (!workspaceId) return;
      const deal = await api.post<Deal>("/api/deals", {
        workspace_id: workspaceId,
        company_name: companyName,
      });
      setDeals((prev) => [...prev, deal]);
      setNewDealName("");
      router.push(`/deals/${deal.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create deal");
    } finally {
      setCreatingDeal(false);
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
          onChange={(e) => setActiveWorkspace(e.target.value || null)}
        >
          {workspaces.length === 0 && (
            <option value="" className="bg-[var(--panel)]">
              No workspace yet
            </option>
          )}
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
            required
          />
          <button
            className="rounded border border-[var(--border)] px-2 py-1 text-sm disabled:opacity-60"
            type="submit"
            disabled={creatingWorkspace}
          >
            {creatingWorkspace ? "Creating…" : "+ Workspace"}
          </button>
        </form>
      </div>

      <form onSubmit={createDeal} className="card mb-6 flex items-center gap-3 p-4">
        <input
          className="flex-1 rounded border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          placeholder="Company name (e.g. Acme Corp)"
          value={newDealName}
          onChange={(e) => setNewDealName(e.target.value)}
          required
        />
        <button
          className="rounded bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
          type="submit"
          disabled={creatingDeal}
        >
          {creatingDeal ? "Creating…" : "Create deal"}
        </button>
      </form>

      <div className="card divide-y divide-[var(--border)]">
        {deals.length === 0 && (
          <p className="p-4 text-sm text-[var(--muted)]">
            No deals yet in this workspace. Enter a company name above and click{" "}
            <span className="text-[var(--text)]">Create deal</span> to start a valuation workflow.
          </p>
        )}
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
