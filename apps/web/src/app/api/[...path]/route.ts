import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

function upstreamOrigin(): string {
  const raw = process.env.API_UPSTREAM_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  return raw.replace(/\/$/, "");
}

async function proxy(req: NextRequest, context: { params: { path: string[] } }) {
  const path = (context.params.path ?? []).join("/");
  const target = `${upstreamOrigin()}/api/${path}${req.nextUrl.search}`;
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) headers.set(key, value);
  });
  headers.delete("accept-encoding");

  const init: RequestInit & { duplex?: "half" } = { method: req.method, headers, redirect: "manual" };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
    init.duplex = "half";
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch (err) {
    const reason = err instanceof Error ? err.message : "upstream unreachable";
    return NextResponse.json(
      {
        detail:
          `Cannot reach API at ${upstreamOrigin()} (${reason}). ` +
          "Set API_UPSTREAM_URL (or NEXT_PUBLIC_API_BASE_URL) on the web service to the API URL.",
      },
      { status: 502 }
    );
  }

  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) out.set(key, value);
  });
  return new NextResponse(upstream.body, { status: upstream.status, headers: out });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
