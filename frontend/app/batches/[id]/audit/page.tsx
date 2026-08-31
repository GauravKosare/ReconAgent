import { Shell } from "@/components/shell";
import { Card } from "@/components/ui";
import { getAudit, isDemo } from "@/lib/api";
import { clockTime } from "@/lib/format";

export const dynamic = "force-dynamic";

const ACTOR_TONE = (a: string) =>
  a === "system" ? "var(--faint)" : a === "agent" ? "var(--brand)" : "var(--accent)";

export default async function AuditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const entries = await getAudit(id);
  const demo = isDemo(id);

  return (
    <Shell batchId={id} demo={demo}>
      <div className="mb-6">
        <h1 className="font-display text-2xl text-ink">Audit log</h1>
        <p className="text-sm text-faint">
          Append-only. Every ingest, match, adjudication, routing decision and human approval —{" "}
          {entries.length} entries.
        </p>
      </div>

      <Card className="rise p-5 md:p-6">
        <ol className="relative ml-3 border-l border-line">
          {entries.map((e, i) => (
            <li key={i} className="mb-6 ml-6 last:mb-0">
              <span
                className="absolute -left-[7px] mt-1.5 h-3.5 w-3.5 rounded-full border-2 border-bg"
                style={{ background: ACTOR_TONE(e.actor) }}
              />
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-faint">{clockTime(e.created_at)}</span>
                <span
                  className="rounded-md px-1.5 py-0.5 text-[11px] font-medium"
                  style={{
                    background: "color-mix(in srgb, " + ACTOR_TONE(e.actor) + " 14%, transparent)",
                    color: ACTOR_TONE(e.actor),
                  }}
                >
                  {e.actor}
                </span>
                <span className="text-sm font-medium text-ink">{e.action}</span>
                <span className="text-sm text-faint">
                  {e.target_type} <span className="font-mono">{e.target_id}</span>
                </span>
              </div>
              {e.after && (
                <pre className="mt-2 overflow-x-auto rounded-lg bg-surface/70 p-3 font-mono text-[11px] leading-relaxed text-muted">
                  {JSON.stringify(e.after, null, 2)}
                </pre>
              )}
            </li>
          ))}
        </ol>
      </Card>
    </Shell>
  );
}
