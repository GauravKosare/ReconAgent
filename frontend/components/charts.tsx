import { CODE_LABEL, CODE_TONE, inr } from "@/lib/format";

const TONE_COLOR: Record<string, string> = {
  bad: "var(--bad)",
  warn: "var(--warn)",
  ok: "var(--ok)",
  brand: "var(--brand)",
};

/* ---------- Donut: exceptions by code ---------- */
export function Donut({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, v]) => s + v, 0) || 1;
  const R = 52;
  const C = 2 * Math.PI * R;
  let offset = 0;

  return (
    <div className="flex flex-wrap items-center gap-6 p-5">
      <svg viewBox="0 0 140 140" className="h-40 w-40 -rotate-90 shrink-0">
        <circle cx="70" cy="70" r={R} fill="none" stroke="var(--line)" strokeWidth="16" />
        {entries.map(([code, v]) => {
          const frac = v / total;
          const dash = frac * C;
          const el = (
            <circle
              key={code}
              cx="70"
              cy="70"
              r={R}
              fill="none"
              stroke={TONE_COLOR[CODE_TONE[code] ?? "brand"]}
              strokeWidth="16"
              strokeDasharray={`${dash} ${C - dash}`}
              strokeDashoffset={-offset}
            />
          );
          offset += dash;
          return el;
        })}
        <text
          x="70"
          y="72"
          textAnchor="middle"
          className="rotate-90 fill-[var(--ink)] font-display"
          style={{ fontSize: 22, transformOrigin: "70px 70px" }}
        >
          {total}
        </text>
      </svg>
      <ul className="grid flex-1 gap-1.5 min-w-[180px]">
        {entries.map(([code, v]) => (
          <li key={code} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-muted">
              <span
                className="h-2.5 w-2.5 rounded-sm"
                style={{ background: TONE_COLOR[CODE_TONE[code] ?? "brand"] }}
              />
              {CODE_LABEL[code] ?? code}
            </span>
            <span className="num font-medium text-ink">{v}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ---------- Funnel: how the batch resolved ---------- */
export function Funnel({
  total,
  autoMatched,
  autoResolved,
  pending,
}: {
  total: number;
  autoMatched: number;
  autoResolved: number;
  pending: number;
}) {
  const rows = [
    { label: "Transactions ingested", n: total, tone: "brand" as const },
    { label: "Auto-matched (exact, no AI)", n: autoMatched, tone: "ok" as const },
    { label: "Exceptions auto-resolved", n: autoResolved, tone: "warn" as const },
    { label: "Sent to human review", n: pending, tone: "bad" as const },
  ];
  const max = Math.max(...rows.map((r) => r.n), 1);
  return (
    <div className="grid gap-3 p-5">
      {rows.map((r) => (
        <div key={r.label}>
          <div className="mb-1 flex justify-between text-sm">
            <span className="text-muted">{r.label}</span>
            <span className="num font-semibold text-ink">{r.n.toLocaleString("en-IN")}</span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface">
            <div
              className="h-full rounded-full transition-[width] duration-500"
              style={{ width: `${(r.n / max) * 100}%`, background: TONE_COLOR[r.tone] }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ---------- Bullet: a metric vs its target ---------- */
export function Bullet({
  label,
  value,
  target,
  max = 1,
  format = (n: number) => `${(n * 100).toFixed(1)}%`,
  higherIsBetter = true,
}: {
  label: string;
  value: number;
  target: number;
  max?: number;
  format?: (n: number) => string;
  higherIsBetter?: boolean;
}) {
  const pass = higherIsBetter ? value >= target : value <= target;
  return (
    <div className="grid gap-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted">{label}</span>
        <span className="num font-semibold" style={{ color: pass ? "var(--ok)" : "var(--bad)" }}>
          {format(value)}
        </span>
      </div>
      <div className="relative h-3 rounded-full bg-surface">
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{
            width: `${Math.min(100, (value / max) * 100)}%`,
            background: pass ? "var(--ok)" : "var(--bad)",
          }}
        />
        <div
          className="absolute inset-y-[-2px] w-[2px] bg-ink"
          style={{ left: `${Math.min(100, (target / max) * 100)}%` }}
          title={`target ${format(target)}`}
        />
      </div>
    </div>
  );
}

/* ---------- Money bars: rupees at risk by code ---------- */
export function MoneyBars({ rows }: { rows: { code: string; amount: number }[] }) {
  const max = Math.max(...rows.map((r) => r.amount), 1);
  return (
    <div className="grid gap-2.5 p-5">
      {rows.map((r) => (
        <div key={r.code} className="grid grid-cols-[130px_1fr_auto] items-center gap-3 text-sm">
          <span className="truncate text-muted">{CODE_LABEL[r.code] ?? r.code}</span>
          <div className="h-2 rounded-full bg-surface">
            <div
              className="h-full rounded-full"
              style={{
                width: `${(r.amount / max) * 100}%`,
                background: TONE_COLOR[CODE_TONE[r.code] ?? "brand"],
              }}
            />
          </div>
          <span className="num text-xs font-medium text-ink">{inr(r.amount)}</span>
        </div>
      ))}
    </div>
  );
}
