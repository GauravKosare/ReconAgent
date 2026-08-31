import { Shell } from "@/components/shell";
import { Upload } from "@/components/upload";
import { Card } from "@/components/ui";

const STEPS = [
  ["Normalise", "three column formats → one transaction schema; raw rows kept verbatim"],
  ["Exact match", "join on UTR, verify amounts + fee — 85–95% resolved with no AI"],
  ["Signals", "deterministic rules classify every leftover into the taxonomy"],
  ["Adjudicate", "the AI confirms each call, writes the rationale, or flags for a human"],
  ["Route", "high-confidence + small ₹ auto-resolves; the rest goes to your queue"],
];

export default function UploadPage() {
  return (
    <Shell>
      <div className="mb-6">
        <h1 className="font-display text-2xl text-ink">New reconciliation batch</h1>
        <p className="text-sm text-faint">
          Upload the three exports for one settlement period. Nothing is stored until you run.
        </p>
      </div>

      <Upload />

      <Card className="rise mt-8 p-5 md:p-6">
        <h3 className="mb-4 text-[13px] font-semibold uppercase tracking-wide text-muted">
          What happens when you run
        </h3>
        <ol className="grid gap-3 sm:grid-cols-5">
          {STEPS.map(([t, d], i) => (
            <li key={t} className="relative">
              <span className="font-display text-brand">{i + 1}</span>
              <p className="text-sm font-semibold text-ink">{t}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-faint">{d}</p>
            </li>
          ))}
        </ol>
      </Card>
    </Shell>
  );
}
