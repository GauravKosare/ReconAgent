import type {
  AuditEntry,
  BatchResult,
  BatchSummary,
  ExceptionRecord,
  SampleDataset,
} from "./types";
import { SAMPLE_AUDIT, SAMPLE_BATCH } from "./sample";

// NEXT_PUBLIC_API_URL always wins when set. Otherwise: the local dev server
// during `next dev`, and the deployed backend for any production build
// (Vercel or otherwise) — so a misconfigured/missing dashboard env var still
// resolves to the real API instead of silently falling back to demo mode.
const DEFAULT_API =
  process.env.NODE_ENV === "development"
    ? "http://localhost:8000"
    : "https://reconagent-api.onrender.com";
const BASE = process.env.NEXT_PUBLIC_API_URL || DEFAULT_API;
const DEMO_ID = SAMPLE_BATCH.summary.batch_id;

async function tryFetch<T>(
  path: string,
  init?: RequestInit,
  timeoutMs = 8000,
): Promise<T | null> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/** True when the batch id is the bundled demo (offline mode). */
export const isDemo = (id: string) => id === DEMO_ID;

export async function listBatches(): Promise<BatchSummary[]> {
  const live = await tryFetch<BatchSummary[]>("/batches");
  if (live && live.length) return live;
  return [SAMPLE_BATCH.summary];
}

export async function getBatch(id: string): Promise<BatchSummary> {
  if (isDemo(id)) return SAMPLE_BATCH.summary;
  return (await tryFetch<BatchSummary>(`/batches/${id}`)) ?? SAMPLE_BATCH.summary;
}

export async function getExceptions(
  id: string,
  routedTo?: string,
): Promise<ExceptionRecord[]> {
  let rows: ExceptionRecord[] | null = null;
  if (!isDemo(id)) {
    const q = routedTo ? `?routed_to=${routedTo}` : "";
    rows = await tryFetch<ExceptionRecord[]>(`/batches/${id}/exceptions${q}`);
  }
  const all = rows ?? SAMPLE_BATCH.exceptions;
  return routedTo ? all.filter((e) => e.routed_to === routedTo) : all;
}

export async function getAudit(id: string): Promise<AuditEntry[]> {
  if (isDemo(id)) return SAMPLE_AUDIT;
  return (await tryFetch<AuditEntry[]>(`/batches/${id}/audit`)) ?? SAMPLE_AUDIT;
}

const RUN_TIMEOUT_MS = 120_000; // a real reconcile + LLM enrichment run

export async function runBatch(form: FormData): Promise<BatchResult | null> {
  return tryFetch<BatchResult>("/batches", { method: "POST", body: form }, RUN_TIMEOUT_MS);
}

export async function runRealisticBatch(form: FormData): Promise<BatchResult | null> {
  return tryFetch<BatchResult>(
    "/batches/realistic",
    { method: "POST", body: form },
    RUN_TIMEOUT_MS,
  );
}

export async function listSamples(): Promise<SampleDataset[]> {
  return (await tryFetch<SampleDataset[]>("/samples")) ?? [];
}

export async function runSample(folder: string): Promise<BatchResult | null> {
  const fd = new FormData();
  fd.set("folder", folder);
  return tryFetch<BatchResult>(
    "/batches/realistic/sample",
    { method: "POST", body: fd },
    RUN_TIMEOUT_MS,
  );
}

export async function submitApproval(
  clusterId: string,
  reviewer: string,
  decision: "approve" | "reject" | "edit",
  note: string,
): Promise<boolean> {
  const fd = new FormData();
  fd.set("exception_cluster_id", clusterId);
  fd.set("reviewer", reviewer);
  fd.set("decision", decision);
  fd.set("note", note);
  const r = await tryFetch<{ ok: boolean }>("/approvals", { method: "POST", body: fd });
  return !!r?.ok;
}

export { DEMO_ID };
