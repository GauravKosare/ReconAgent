import Link from "next/link";
import type { ReactNode } from "react";

export function Card({
  children,
  className = "",
  as: As = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article";
}) {
  return (
    <As
      className={`glass rounded-2xl shadow-card ${className}`}
    >
      {children}
    </As>
  );
}

export function CardHead({
  title,
  hint,
  right,
}: {
  title: string;
  hint?: string;
  right?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 px-5 pt-4 pb-3 border-b border-line">
      <div>
        <h3 className="text-[13px] font-semibold tracking-wide text-muted uppercase">{title}</h3>
        {hint && <p className="text-xs text-faint mt-0.5">{hint}</p>}
      </div>
      {right}
    </div>
  );
}

const TONE: Record<string, string> = {
  ok: "bg-[color-mix(in_srgb,var(--ok)_14%,transparent)] text-ok",
  warn: "bg-[color-mix(in_srgb,var(--warn)_16%,transparent)] text-warn",
  bad: "bg-[color-mix(in_srgb,var(--bad)_14%,transparent)] text-bad",
  brand: "bg-brand-soft text-brand",
  neutral: "bg-surface text-muted",
};

export function Badge({
  children,
  tone = "neutral",
  className = "",
}: {
  children: ReactNode;
  tone?: keyof typeof TONE;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${TONE[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function Dot({ tone = "neutral" }: { tone?: keyof typeof TONE }) {
  const c: Record<string, string> = {
    ok: "var(--ok)",
    warn: "var(--warn)",
    bad: "var(--bad)",
    brand: "var(--brand)",
    neutral: "var(--faint)",
  };
  return (
    <span
      className="inline-block h-2 w-2 rounded-full shrink-0"
      style={{ background: c[tone] }}
    />
  );
}

export function Stat({
  label,
  value,
  sub,
  tone,
  target,
  delay = 0,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "ok" | "warn" | "bad" | "brand";
  target?: string;
  delay?: number;
}) {
  const accent =
    tone === "ok" ? "var(--ok)" : tone === "warn" ? "var(--warn)" : tone === "bad" ? "var(--bad)" : "var(--brand)";
  return (
    <Card className="rise p-5" >
      <div style={{ animationDelay: `${delay}ms` }}>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: accent }} />
          <span className="text-[13px] font-medium text-muted">{label}</span>
        </div>
        <div className="mt-3 font-display text-3xl text-ink num">{value}</div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-faint">
          {sub && <span>{sub}</span>}
          {target && (
            <span className="whitespace-nowrap rounded bg-surface px-1.5 py-0.5 text-faint">
              target {target}
            </span>
          )}
        </div>
      </div>
    </Card>
  );
}

export function NavLink({
  href,
  active,
  icon,
  children,
}: {
  href: string;
  active: boolean;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`group flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors ${
        active
          ? "bg-brand text-white shadow-card"
          : "text-muted hover:bg-surface hover:text-ink"
      }`}
    >
      <span className={active ? "text-white" : "text-faint group-hover:text-brand"}>{icon}</span>
      {children}
    </Link>
  );
}
