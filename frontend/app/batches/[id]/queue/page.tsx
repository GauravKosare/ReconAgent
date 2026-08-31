import { Shell } from "@/components/shell";
import { QueueBoard } from "@/components/queue-board";
import { getBatch, getExceptions, isDemo } from "@/lib/api";
import { inr } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function QueuePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [b, rows] = await Promise.all([getBatch(id), getExceptions(id)]);
  const demo = isDemo(id);
  const atRisk = rows
    .filter((r) => r.routed_to === "pending_approval")
    .reduce((s, r) => s + Math.abs(r.amount_impact), 0);

  return (
    <Shell batchId={id} demo={demo}>
      <div className="mb-6">
        <h1 className="font-display text-2xl text-ink">Approval queue</h1>
        <p className="text-sm text-faint">
          {b.pending_approval} exceptions awaiting a human decision ·{" "}
          <span className="font-medium text-ink">{inr(atRisk)}</span> at risk. High-confidence,
          low-value items were auto-resolved and logged.
        </p>
      </div>
      <QueueBoard rows={rows} demo={demo} />
    </Shell>
  );
}
