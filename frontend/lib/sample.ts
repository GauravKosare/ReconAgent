import type { AuditEntry, BatchResult } from "./types";

/**
 * Bundled demo data — the dashboard renders from this when the API is
 * unreachable (offline demo / pitch video), mirroring a real 500-txn batch.
 */
export const SAMPLE_BATCH: BatchResult = {
  summary: {
    batch_id: "batch_demo0a1b2c",
    started_at: "2026-08-31T05:40:12",
    finished_at: "2026-08-31T05:40:25",
    runtime_seconds: 13.5,
    rows_ingested: 1486,
    auto_matched_groups: 449,
    auto_match_rate: 0.899,
    clusters_adjudicated: 59,
    exceptions: 59,
    exceptions_by_code: {
      FEE_MISMATCH: 20,
      TIMING_GAP: 12,
      MISSING_PAYOUT: 8,
      SHORT_SETTLEMENT: 7,
      MISSING_IN_LEDGER: 6,
      DUPLICATE: 6,
    },
    auto_resolved: 21,
    pending_approval: 38,
    flagged_amount_inr: 21840.5,
    llm_used: true,
    llm_available: true,
  },
  exceptions: [
    {
      batch_id: "batch_demo0a1b2c", cluster_id: "c07", anchor_source: "ledger",
      anchor_external_id: "ORD100241", anchor_utr: "UTR8840112673",
      code: "FEE_MISMATCH", amount_impact: 5.0, direction: "merchant_owed", confidence: 0.95,
      rationale:
        "Contract MDR 2% => expected fee ₹20.00; PG charged ₹25.00, so net is ₹5.00 short. Bank credit equals the reduced PG net exactly.",
      evidence: ["signals.reason=PG fee over contract by 5.0", "sources=['bank','ledger','pg']"],
      recommended_action: "Raise a fee-dispute ticket for ₹5.00",
      routed_to: "auto_resolved", created_at: "2026-08-31T05:40:19",
    },
    {
      batch_id: "batch_demo0a1b2c", cluster_id: "c11", anchor_source: "ledger",
      anchor_external_id: "ORD100377", anchor_utr: "UTR7213908455",
      code: "MISSING_PAYOUT", amount_impact: 2499.0, direction: "merchant_owed", confidence: 0.78,
      rationale:
        "PG marked this settled on 03 Aug but no bank credit for ₹2,441.98 has arrived; 25 days past the T+2 SLA.",
      evidence: ["signals.reason=PG settled, no matching bank credit, SLA breached"],
      recommended_action: "Escalate to PG settlements — payout past SLA",
      routed_to: "pending_approval", created_at: "2026-08-31T05:40:20",
    },
    {
      batch_id: "batch_demo0a1b2c", cluster_id: "c18", anchor_source: "ledger",
      anchor_external_id: "ORD100455", anchor_utr: "UTR9902144067",
      code: "TIMING_GAP", amount_impact: 976.4, direction: "neutral", confidence: 0.93,
      rationale:
        "Ledger and PG agree; the matching bank credit for ₹976.40 landed 6 days after settlement — outside the T+2 window but reconciled.",
      evidence: ["signals.bank_late_days=6"],
      recommended_action: "No action; recheck after the next bank sync",
      routed_to: "auto_resolved", created_at: "2026-08-31T05:40:21",
    },
    {
      batch_id: "batch_demo0a1b2c", cluster_id: "c23", anchor_source: "pg",
      anchor_external_id: "pay_9Kx2mNqLbZ", anchor_utr: "UTR6650431129",
      code: "MISSING_IN_LEDGER", amount_impact: 1499.0, direction: "merchant_owed", confidence: 0.71,
      rationale:
        "₹1,464.28 was received via PG and credited by the bank, but there is no matching sale in the internal ledger.",
      evidence: ["signals.reason=money received, no matching ledger row"],
      recommended_action: "Ask ops to record the missing sale in the ledger",
      routed_to: "pending_approval", created_at: "2026-08-31T05:40:22",
    },
    {
      batch_id: "batch_demo0a1b2c", cluster_id: "c31", anchor_source: "ledger",
      anchor_external_id: "ORD100512", anchor_utr: "UTR4471200983",
      code: "SHORT_SETTLEMENT", amount_impact: 50.0, direction: "merchant_owed", confidence: 0.66,
      rationale:
        "Fee and tax are correct, but the PG net is ₹50.00 below the expected ₹976.40 with no refund or adjustment on record.",
      evidence: ["signals.net_short_inr=50.0"],
      recommended_action: "Query the PG for the unexplained ₹50.00 deduction",
      routed_to: "pending_approval", created_at: "2026-08-31T05:40:22",
    },
    {
      batch_id: "batch_demo0a1b2c", cluster_id: "c39", anchor_source: "pg",
      anchor_external_id: "pay_2bQ7rTmXcE", anchor_utr: "UTR5518830271",
      code: "DUPLICATE", amount_impact: 499.0, direction: "neutral", confidence: 0.9,
      rationale: "Two identical PG settlement lines for UTR ...30271 (₹499.00 each) — one is a duplicate.",
      evidence: ["signals.duplicate_of=['pg:418']"],
      recommended_action: "Void the duplicate entry after confirmation",
      routed_to: "auto_resolved", created_at: "2026-08-31T05:40:23",
    },
    {
      batch_id: "batch_demo0a1b2c", cluster_id: "c44", anchor_source: "ledger",
      anchor_external_id: "ORD100601", anchor_utr: "UTR7788221094",
      code: "FEE_MISMATCH", amount_impact: 3.0, direction: "merchant_owed", confidence: 0.94,
      rationale: "PG fee ₹23.00 vs contracted ₹20.00 — ₹3.00 overcharged on a ₹1,000.00 capture.",
      evidence: ["signals.fee_overcharge_inr=3.0"],
      recommended_action: "Raise a fee-dispute ticket for ₹3.00",
      routed_to: "auto_resolved", created_at: "2026-08-31T05:40:23",
    },
    {
      batch_id: "batch_demo0a1b2c", cluster_id: "c52", anchor_source: "ledger",
      anchor_external_id: "ORD100688", anchor_utr: "UTR6120945338",
      code: "MISSING_PAYOUT", amount_impact: 999.0, direction: "merchant_owed", confidence: 0.8,
      rationale: "Settled by PG on 09 Aug, no bank credit for ₹975.42; 19 days past SLA.",
      evidence: ["signals.sla_breached=true"],
      recommended_action: "Escalate to PG settlements — payout past SLA",
      routed_to: "pending_approval", created_at: "2026-08-31T05:40:24",
    },
  ],
};

export const SAMPLE_AUDIT: AuditEntry[] = [
  { batch_id: "batch_demo0a1b2c", actor: "system", action: "ingest", target_type: "batch",
    target_id: "batch_demo0a1b2c", before: null, after: { txn_count: 1486 },
    created_at: "2026-08-31T05:40:12" },
  { batch_id: "batch_demo0a1b2c", actor: "system", action: "exact_match", target_type: "batch",
    target_id: "batch_demo0a1b2c", before: null, after: { auto_matched: 449, leftovers: 139 },
    created_at: "2026-08-31T05:40:13" },
  { batch_id: "batch_demo0a1b2c", actor: "agent", action: "adjudicate", target_type: "cluster",
    target_id: "c07", before: null,
    after: { route: "auto_resolved", reason: "within confidence + rupee bounds", model: "groq/qwen/qwen3.8-27b" },
    created_at: "2026-08-31T05:40:19" },
  { batch_id: "batch_demo0a1b2c", actor: "agent", action: "adjudicate", target_type: "cluster",
    target_id: "c11", before: null,
    after: { route: "pending_approval", reason: "MISSING_PAYOUT always needs a human" },
    created_at: "2026-08-31T05:40:20" },
  { batch_id: "batch_demo0a1b2c", actor: "agent", action: "adjudicate", target_type: "cluster",
    target_id: "c31", before: null,
    after: { route: "pending_approval", reason: "confidence 0.66 below floor" },
    created_at: "2026-08-31T05:40:22" },
  { batch_id: "batch_demo0a1b2c", actor: "priya@acme.in", action: "approval:approve", target_type: "exception",
    target_id: "c11", before: null, after: { note: "Confirmed with PG ops, payout re-queued" },
    created_at: "2026-08-31T06:02:41" },
];
