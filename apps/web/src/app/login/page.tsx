"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { api, setToken, ApiError } from "@/lib/api";

const credentialsSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const parsed = credentialsSchema.safeParse({ email, password });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Invalid input");
      return;
    }
    setLoading(true);
    try {
      if (mode === "register") {
        await api.post("/api/auth/register", { email, name, password });
      }
      const { access_token } = await api.loginForm(email, password);
      setToken(access_token);
      router.push("/deals");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto mt-24 max-w-sm">
      <h1 className="mb-1 text-2xl font-semibold">Valora</h1>
      <p className="mb-8 text-sm text-[var(--muted)]">Investment research & valuation workspace</p>

      <div className="card p-6">
        <div className="mb-6 flex gap-2 text-sm">
          <button
            className={`rounded px-3 py-1 ${mode === "login" ? "bg-[var(--accent)] text-white" : "text-[var(--muted)]"}`}
            onClick={() => setMode("login")}
            type="button"
          >
            Sign in
          </button>
          <button
            className={`rounded px-3 py-1 ${mode === "register" ? "bg-[var(--accent)] text-white" : "text-[var(--muted)]"}`}
            onClick={() => setMode("register")}
            type="button"
          >
            Create account
          </button>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          {mode === "register" && (
            <input
              className="rounded border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
              placeholder="Full name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          )}
          <input
            className="rounded border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
            placeholder="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            className="rounded border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <p className="text-sm text-[var(--bad)]">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="mt-2 rounded bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account & sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
