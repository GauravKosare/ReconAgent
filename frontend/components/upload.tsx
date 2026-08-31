"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { runBatch, DEMO_ID } from "@/lib/api";
import { Card } from "./ui";
import { IconArrow, IconCheck, IconUpload } from "./icons";

type Slot = "pg" | "bank" | "ledger";
const SLOTS: { key: Slot; title: string; who: string }[] = [
  { key: "ledger", title: "Internal ledger", who: "your sales / invoice system" },
  { key: "pg", title: "PG settlement report", who: "Razorpay settlement export" },
  { key: "bank", title: "Bank statement", who: "your bank's CSV" },
];

export function Upload() {
  const router = useRouter();
  const [files, setFiles] = useState<Partial<Record<Slot, File>>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const ready = SLOTS.every((s) => files[s.key]);

  async function run() {
    setBusy(true);
    setErr(null);
    const fd = new FormData();
    SLOTS.forEach((s) => fd.set(s.key, files[s.key]!));
    const res = await runBatch(fd);
    setBusy(false);
    if (res?.summary?.batch_id) router.push(`/batches/${res.summary.batch_id}`);
    else setErr("Couldn't reach the reconciliation API. Start the backend, or explore the demo batch.");
  }

  return (
    <div className="grid gap-5">
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
                  {f ? f.name : "Drop CSV or click to choose"}
                </span>
                <input
                  type="file"
                  accept=".csv,.xlsx,text/csv"
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
          disabled={!ready || busy}
          onClick={run}
          className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-white shadow-card transition-transform enabled:hover:-translate-y-0.5 disabled:opacity-50"
        >
          {busy ? "Reconciling…" : "Run reconciliation"}
          {!busy && <IconArrow className="h-[18px] w-[18px]" />}
        </button>
        <a
          href={`/batches/${DEMO_ID}`}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-brand hover:underline"
        >
          Or open the demo batch <IconArrow className="h-4 w-4" />
        </a>
      </div>
    </div>
  );
}
