import Link from "next/link";
import { Shell } from "@/components/shell";
import { Card, CardHead, Badge, Stat } from "@/components/ui";
import { IconArrow, IconSpark, IconUpload } from "@/components/icons";
import { listBatches } from "@/lib/api";
import { DEMO_ID } from "@/lib/api";
import { inr, pct } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function Overview() {
  const batches = await listBatches();
  const latest = batches[0];
  const demo = latest?.batch_id === DEMO_ID;

  return (
    <Shell demo={demo}>
      {/* hero */}
      <section className="rise mb-8 flex flex-col gap-4 rounded-2xl border border-line bg-gradient-to-br from-brand-soft/70 to-transparent p-6 md:flex-row md:items-center md:justify-between md:p-8">
        <div className="max-w-xl">
          <span className="mb-2 inline-flex items-center gap-1.5 text-xs font-medium text-brand">
            <IconSpark className="h-4 w-4" /> Autonomous finance-ops agent
          </span>
          <h1 className="font-display text-2xl leading-tight text-ink md:text-[28px]">
            Reconcile settlement, bank & ledger — and see exactly what doesn&apos;t add up.
          </h1>
          <p className="mt-2 text-sm text-muted">
            The deterministic core matches every transaction three ways. The AI classifies and
            explains the exceptions. You review only what needs a human.
          </p>
        </div>
        <Link
          href="/upload"
          className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-white shadow-card transition-transform hover:-translate-y-0.5"
        >
          <IconUpload className="h-[18px] w-[18px]" /> Run a new batch
        </Link>
      </section>

      {latest ? (
        <>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-[13px] font-semibold uppercase tracking-wide text-muted">
              Latest batch
            </h2>
            <Link
              href={`/batches/${latest.batch_id}`}
              className="inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline"
            >
              Open dashboard <IconArrow className="h-4 w-4" />
            </Link>
          </div>

          <div className="mb-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat
              label="Auto-match rate"
              value={pct(latest.auto_match_rate ?? 0)}
              sub={`${latest.auto_matched_groups ?? "—"} matched with no AI`}
              tone="ok"
              target="≥ 85%"
              delay={0}
            />
            <Stat
              label="Exceptions"
              value={String(latest.exceptions ?? 0)}
              sub={`${latest.auto_resolved ?? 0} auto-resolved`}
              tone="warn"
              delay={60}
            />
            <Stat
              label="Needs review"
              value={String(latest.pending_approval ?? 0)}
              sub="in the approval queue"
              tone="bad"
              delay={120}
            />
            <Stat
              label="Money at risk"
              value={inr(latest.flagged_amount_inr ?? 0)}
              sub={`${latest.rows_ingested ?? 0} rows · ${latest.runtime_seconds ?? "—"}s`}
              tone="brand"
              delay={180}
            />
          </div>

          <Card className="rise">
            <CardHead title="Recent batches" hint={demo ? "Sample data — start the API for live batches" : undefined} />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-faint">
                    <th className="px-5 py-3 font-medium">Batch</th>
                    <th className="px-5 py-3 font-medium">Rows</th>
                    <th className="px-5 py-3 font-medium">Auto-match</th>
                    <th className="px-5 py-3 font-medium">Exceptions</th>
                    <th className="px-5 py-3 font-medium">Queue</th>
                    <th className="px-5 py-3 font-medium">At risk</th>
                    <th className="px-5 py-3 font-medium">Mode</th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map((b) => (
                    <tr key={b.batch_id} className="border-t border-line hover:bg-surface/60">
                      <td className="px-5 py-3">
                        <Link href={`/batches/${b.batch_id}`} className="font-mono text-brand hover:underline">
                          {b.batch_id}
                        </Link>
                      </td>
                      <td className="num px-5 py-3 text-muted">{b.rows_ingested ?? "—"}</td>
                      <td className="num px-5 py-3">{b.auto_match_rate != null ? pct(b.auto_match_rate) : "—"}</td>
                      <td className="num px-5 py-3">{b.exceptions ?? "—"}</td>
                      <td className="num px-5 py-3">{b.pending_approval ?? "—"}</td>
                      <td className="num px-5 py-3 text-muted">{inr(b.flagged_amount_inr ?? 0)}</td>
                      <td className="px-5 py-3">
                        <Badge tone={b.llm_used ? "brand" : "neutral"}>
                          {b.llm_used ? "AI adjudicated" : "deterministic"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      ) : (
        <Card className="p-10 text-center">
          <p className="text-muted">No batches yet.</p>
          <Link href="/upload" className="mt-3 inline-block font-medium text-brand hover:underline">
            Run your first reconciliation →
          </Link>
        </Card>
      )}
    </Shell>
  );
}
