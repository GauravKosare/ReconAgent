"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  DEMO_ID,
  listSamples,
  runBatch,
  runRealisticBatch,
  runSample,
} from "@/lib/api";
import type { SampleDataset } from "@/lib/types";
import { Card } from "./ui";
import { IconArrow, IconCheck, IconSpark, IconUpload } from "./icons";

type Slot = "pg" | "bank" | "ledger";
const SLOTS: { key: Slot; title: string; who: string }[] = [
  { key: "ledger", title: "Internal ledger", who: "your sales / invoice system" },
  { key: "pg", title: "PG settlement report", who: "Razorpay recon or Stripe balance export" },
  { key: "bank", title: "Bank statement", who: "CSV, MT940 or CAMT.053" },
];
const REGIONS = ["IN", "US", "EU"] as const;

export function Upload() {
  const router = useRouter();
  const [files, setFiles] = useState<Partial<Record<Slot, File>>>({});
  const [region, setRegion] = useState<(typeof REGIONS)[number]>("IN");
  const [realistic, setRealistic] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [samples, setSamples] = useState<SampleDataset[]>([]);

  useEffect(() => {
    listSamples().then(setSamples);
  }, []);

  const ready = SLOTS.every((s) => files[s.key]);

  function done(res: Awaited<ReturnType<typeof runBatch>>, fallbackMsg: string) {
    setBusy(null);
    if (res?.summary?.batch_id) router.push(`/batches/${res.summary.batch_id}`);
    else setErr(fallbackMsg);
  }

  async function run() {
    setBusy("upload");
    setErr(null);
    const fd = new FormData();
    SLOTS.forEach((s) => fd.set(s.key, files[s.key]!));
    if (realistic) {
      fd.set("region", region);
      done(await runRealisticBatch(fd), "Couldn't reach the reconciliation API. Start the backend, or run a sample dataset below.");
    } else {
      done(await runBatch(fd), "Couldn't reach the reconciliation API. Start the backend, or explore the demo batch.");
    }
  }

  async function sample(folder: string) {
    setBusy(folder);
    setErr(null);
    done(await runSample(folder), "Couldn't reach the reconciliation API. Start the backend to run a live sample.");
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-muted">
          Region
          <select
            value={region}
            onChange={(e) => setRegion(e.target.value as (typeof REGIONS)[number])}
            className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-sm text-ink"
          >
            {REGIONS.map((r) => (
              <option key={r} value={r}>
                {r === "IN" ? "India · INR" : r === "US" ? "United States · USD" : "Europe · EUR"}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={realistic}
            onChange={(e) => setRealistic(e.target.checked)}
            className="h-4 w-4 accent-[var(--brand)]"
          />
          Real bank / PG formats (settlement-batch reconciliation)
        </label>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {SLOTS.map((s) => {
          const f = files[s.key];
          return (
            <Card key={s.key} className="rise">
              <label className="flex cursor-pointer flex-col gap-2 p-5">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-ink">{s.title}</span>
                  {f ? (
                    <IconCheck className="h-[18px] w-[18px] text-ok" />
                  ) : (
                    <IconUpload className="h-[18px] w-[18px] text-faint" />
                  )}
                </div>
                <span className="text-xs text-faint">{s.who}</span>
                <span
                  className={`mt-2 truncate rounded-lg border border-dashed px-3 py-3 text-center text-xs ${
                    f ? "border-ok/40 bg-ok/5 text-ok" : "border-line bg-surface/50 text-faint"
                  }`}
                >
                  {f ? f.name : "Drop file or click to choose"}
                </span>
                <input
                  type="file"
                  accept=".csv,.xml,.mt940,.txt,.sta,text/csv"
                  className="hidden"
                  onChange={(e) =>
                    setFiles((p) => ({ ...p, [s.key]: e.target.files?.[0] ?? undefined }))
                  }
                />
              </label>
            </Card>
          );
        })}
      </div>

      {err && (
        <p className="rounded-xl border border-bad/30 bg-bad/5 px-4 py-3 text-sm text-bad">{err}</p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          disabled={!ready || busy !== null}
          onClick={run}
          className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-white shadow-card transition-transform enabled:hover:-translate-y-0.5 disabled:opacity-50"
        >
          {busy === "upload" ? "Reconciling…" : "Run reconciliation"}
          {busy !== "upload" && <IconArrow className="h-[18px] w-[18px]" />}
        </button>
        <a
          href={`/batches/${DEMO_ID}`}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-brand hover:underline"
        >
          Or open the demo batch <IconArrow className="h-4 w-4" />
        </a>
      </div>

      {samples.length > 0 && (
        <Card className="rise p-5">
          <div className="mb-3 flex items-center gap-2">
            <IconSpark className="h-[18px] w-[18px] text-brand" />
            <h3 className="text-[13px] font-semibold uppercase tracking-wide text-muted">
              Or run a sample dataset
            </h3>
          </div>
          <p className="mb-4 text-xs text-faint">
            Real-format statements (Razorpay recon · Stripe balance · MT940 · CAMT.053 · bank
            CSV) with injected defects and known ground truth. Runs the full pipeline live.
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {samples.map((d) => (
              <button
                key={d.folder}
                disabled={busy !== null}
                onClick={() => sample(d.folder)}
                className="flex items-center justify-between gap-3 rounded-lg border border-line bg-surface/50 px-3 py-2.5 text-left text-sm transition-colors enabled:hover:border-brand/50 enabled:hover:bg-brand-soft/40 disabled:opacity-50"
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium text-ink">{d.folder}</span>
                  <span className="block truncate text-xs text-faint">
                    {d.region} · {d.currency} · {d.pg_format} + {d.bank_format} · {d.payments} payments ·{" "}
                    {d.injected_defects} defects
                  </span>
                </span>
                <span className="shrink-0 text-xs font-medium text-brand">
                  {busy === d.folder ? "running…" : "run"}
                </span>
              </button>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
