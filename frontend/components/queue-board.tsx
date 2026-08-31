"use client";

import { useMemo, useState } from "react";
import type { ExceptionRecord } from "@/lib/types";
import { CODE_LABEL, CODE_TONE, inr, pct } from "@/lib/format";
import { submitApproval } from "@/lib/api";
import { Badge, Card, Dot } from "./ui";
import { IconCheck, IconChevron, IconEdit, IconShield, IconX } from "./icons";

type Decision = "approve" | "reject" | "edit";
type Row = ExceptionRecord & { _resolved?: Decision };

const FILTERS = [
  { key: "pending_approval", label: "Needs review" },
  { key: "auto_resolved", label: "Auto-resolved" },
  { key: "all", label: "All" },
] as const;

export function QueueBoard({
  rows: initial,
  demo,
}: {
  rows: ExceptionRecord[];
  demo: boolean;
}) {
  const [rows, setRows] = useState<Row[]>(initial);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("pending_approval");
  const [reviewer, setReviewer] = useState("you@company.com");
  const [open, setOpen] = useState<string | null>(
    initial.find((r) => r.routed_to === "pending_approval")?.cluster_id ?? initial[0]?.cluster_id ?? null,
  );

  const shown = useMemo(
    () => (filter === "all" ? rows : rows.filter((r) => r.routed_to === filter)),
    [rows, filter],
  );

  const counts = useMemo(
    () => ({
      pending_approval: rows.filter((r) => r.routed_to === "pending_approval" && !r._resolved).length,
      auto_resolved: rows.filter((r) => r.routed_to === "auto_resolved").length,
      all: rows.length,
    }),
    [rows],
  );

  async function act(r: Row, decision: Decision, note: string) {
    setRows((prev) =>
      prev.map((x) => (x.cluster_id === r.cluster_id ? { ...x, _resolved: decision } : x)),
    );
    if (!demo) await submitApproval(r.cluster_id, reviewer, decision, note);
  }

  return (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-xl border border-line bg-surface/60 p-1">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                filter === f.key ? "bg-card text-ink shadow-card" : "text-muted hover:text-ink"
              }`}
            >
              {f.label}
              <span className="ml-1.5 text-xs text-faint">{counts[f.key]}</span>
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-xs text-faint">
          Reviewing as
          <input
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            className="rounded-lg border border-line bg-card px-2.5 py-1.5 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
          />
        </label>
      </div>

      <div className="grid gap-3">
        {shown.length === 0 && (
          <Card className="p-10 text-center text-sm text-faint">Nothing here — queue is clear.</Card>
        )}
        {shown.map((r) => (
          <ExceptionCard
            key={r.cluster_id}
            row={r}
            open={open === r.cluster_id}
            onToggle={() => setOpen(open === r.cluster_id ? null : r.cluster_id)}
            onAct={act}
          />
        ))}
      </div>
    </>
  );
}

function ExceptionCard({
  row,
  open,
  onToggle,
  onAct,
}: {
  row: Row;
  open: boolean;
  onToggle: () => void;
  onAct: (r: Row, d: Decision, note: string) => void;
}) {
  const tone = CODE_TONE[row.code] ?? "brand";
  const [note, setNote] = useState("");
  const resolved = row._resolved;

  return (
    <Card className={`rise overflow-hidden ${resolved ? "opacity-70" : ""}`}>
      <button
        onClick={onToggle}
        className="flex w-full cursor-pointer items-center gap-4 px-5 py-4 text-left"
      >
        <IconChevron
          className={`h-4 w-4 shrink-0 text-faint transition-transform ${open ? "rotate-90" : ""}`}
        />
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <Badge tone={tone}>
            <Dot tone={tone} />
            {CODE_LABEL[row.code] ?? row.code}
          </Badge>
          <span className="hidden truncate text-sm text-muted sm:block">{row.rationale}</span>
        </div>
        <span className="num shrink-0 font-display text-lg text-ink">{inr(row.amount_impact)}</span>
        <span className="hidden shrink-0 text-xs text-faint md:block">conf {pct(row.confidence, 0)}</span>
        {resolved ? (
          <Badge tone={resolved === "reject" ? "bad" : "ok"}>
            {resolved === "reject" ? "rejected" : resolved === "edit" ? "edited" : "approved"}
          </Badge>
        ) : (
          <Badge tone={row.routed_to === "auto_resolved" ? "ok" : "warn"}>
            {row.routed_to === "auto_resolved" ? "auto-resolved" : "pending"}
          </Badge>
        )}
      </button>

      {open && (
        <div className="border-t border-line bg-surface/40 px-5 py-4">
          <div className="grid gap-4 md:grid-cols-[1fr_260px]">
            <div className="grid gap-3">
              <Field label="Agent rationale">{row.rationale}</Field>
              <Field label="Recommended action">{row.recommended_action || "—"}</Field>
              <div>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-faint">
                  Evidence
                </p>
                <ul className="grid gap-1">
                  {(row.evidence?.length ? row.evidence : ["—"]).map((e, i) => (
                    <li
                      key={i}
                      className="rounded-md bg-card px-2.5 py-1.5 font-mono text-[11px] text-muted"
                    >
                      {e}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="grid content-start gap-3 rounded-xl border border-line bg-card p-3">
              <dl className="grid gap-1.5 text-xs">
                <Meta k="Cluster" v={row.cluster_id} mono />
                <Meta k="Anchor" v={`${row.anchor_source ?? "—"} · ${row.anchor_external_id ?? "—"}`} mono />
                <Meta k="UTR" v={row.anchor_utr ?? "—"} mono />
                <Meta k="Direction" v={row.direction.replace("_", " ")} />
                <Meta k="Confidence" v={pct(row.confidence)} />
              </dl>

              {!resolved && (
                <>
                  <input
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Add a note (optional)"
                    className="rounded-lg border border-line bg-bg px-2.5 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
                  />
                  <div className="grid grid-cols-3 gap-2">
                    <ActionBtn tone="ok" onClick={() => onAct(row, "approve", note)}>
                      <IconCheck className="h-4 w-4" /> Approve
                    </ActionBtn>
                    <ActionBtn tone="brand" onClick={() => onAct(row, "edit", note)}>
                      <IconEdit className="h-4 w-4" /> Edit
                    </ActionBtn>
                    <ActionBtn tone="bad" onClick={() => onAct(row, "reject", note)}>
                      <IconX className="h-4 w-4" /> Reject
                    </ActionBtn>
                  </div>
                  <p className="flex items-center gap-1.5 text-[11px] text-faint">
                    <IconShield className="h-3.5 w-3.5" /> Every decision is written to the audit log.
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-faint">{label}</p>
      <p className="text-sm leading-relaxed text-ink">{children}</p>
    </div>
  );
}

function Meta({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-faint">{k}</dt>
      <dd className={`text-right text-muted ${mono ? "font-mono text-[11px]" : ""}`}>{v}</dd>
    </div>
  );
}

function ActionBtn({
  tone,
  onClick,
  children,
}: {
  tone: "ok" | "bad" | "brand";
  onClick: () => void;
  children: React.ReactNode;
}) {
  const c = {
    ok: "border-ok/40 text-ok hover:bg-ok/10",
    bad: "border-bad/40 text-bad hover:bg-bad/10",
    brand: "border-brand/40 text-brand hover:bg-brand/10",
  }[tone];
  return (
    <button
      onClick={onClick}
      className={`inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-lg border bg-card px-2 py-2 text-xs font-semibold transition-colors ${c}`}
    >
      {children}
    </button>
  );
}
