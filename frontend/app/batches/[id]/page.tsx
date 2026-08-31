import Link from "next/link";
import { Shell } from "@/components/shell";
import { Card, CardHead, Badge, Stat } from "@/components/ui";
import { Bullet, Donut, Funnel, MoneyBars } from "@/components/charts";
import { IconArrow, IconQueue } from "@/components/icons";
import { getBatch, getExceptions, isDemo } from "@/lib/api";
import { inr, pct } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function BatchDashboard({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [b, exceptions] = await Promise.all([getBatch(id), getExceptions(id)]);
  const demo = isDemo(id);

  const money = Object.entries(b.exceptions_by_code || {})
    .map(([code]) => ({
      code,
      amount: exceptions
        .filter((e) => e.code === code)
        .reduce((s, e) => s + Math.abs(e.amount_impact), 0),
    }))
    .filter((r) => r.amount > 0)
    .sort((a, b) => b.amount - a.amount);

  const txns = Math.max(Math.round((b.rows_ingested || 0) / 3), 1);
  const queueFrac = (b.pending_approval || 0) / txns;

  return (
    <Shell batchId={id} demo={demo}>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">Batch dashboard</h1>
          <p className="text-sm text-faint">
            {b.rows_ingested} source rows · {b.clusters_adjudicated} clusters adjudicated ·{" "}
            {b.runtime_seconds}s ·{" "}
            <Badge tone={b.llm_used ? "brand" : "neutral"} className="align-middle">
              {b.llm_used ? "AI adjudicated" : "deterministic only"}
            </Badge>
          </p>
        </div>
        <Link
          href={`/batches/${id}/queue`}
          className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-card transition-transform hover:-translate-y-0.5"
        >
          <IconQueue className="h-[18px] w-[18px]" />
          Review queue · {b.pending_approval}
        </Link>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Auto-match rate" value={pct(b.auto_match_rate)} sub={`${b.auto_matched_groups} exact matches`} tone="ok" target="≥ 85%" delay={0} />
        <Stat label="Exceptions found" value={String(b.exceptions)} sub={`${b.auto_resolved} auto-resolved`} tone="warn" delay={60} />
        <Stat label="Needs a human" value={String(b.pending_approval)} sub={pct(queueFrac) + " of transactions"} tone="bad" target="≤ 15%" delay={120} />
        <Stat label="Money at risk" value={inr(b.flagged_amount_inr)} sub="flagged across all exceptions" tone="brand" delay={180} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="rise lg:col-span-2">
          <CardHead title="How the batch resolved" hint="Deterministic core clears the bulk; AI adjudicates the rest" />
          <Funnel
            total={b.rows_ingested ? txns : 0}
            autoMatched={b.auto_matched_groups}
            autoResolved={b.auto_resolved}
            pending={b.pending_approval}
          />
        </Card>

        <Card className="rise">
          <CardHead title="Exceptions by type" />
          <Donut data={b.exceptions_by_code || {}} />
        </Card>

        <Card className="rise lg:col-span-2">
          <CardHead title="Rupees at risk by exception type" hint="Sum of |amount impact| per code" />
          {money.length ? (
            <MoneyBars rows={money} />
          ) : (
            <p className="p-5 text-sm text-faint">No monetary impact recorded on this batch.</p>
          )}
        </Card>

        <Card className="rise">
          <CardHead title="Quality gates" hint="Measured vs. target" />
          <div className="grid gap-4 p-5">
            <Bullet label="Auto-match rate" value={b.auto_match_rate} target={0.85} max={1} />
            <Bullet
              label="Human queue"
              value={queueFrac}
              target={0.15}
              max={0.3}
              higherIsBetter={false}
            />
            <Bullet
              label="Runtime"
              value={b.runtime_seconds}
              target={300}
              max={300}
              higherIsBetter={false}
              format={(n) => `${n.toFixed(1)}s`}
            />
          </div>
        </Card>
      </div>

      <Link
        href={`/batches/${id}/audit`}
        className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline"
      >
        View the full audit log <IconArrow className="h-4 w-4" />
      </Link>
    </Shell>
  );
}
