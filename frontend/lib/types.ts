export type ExceptionCode =
  | "FEE_MISMATCH"
  | "TIMING_GAP"
  | "MISSING_PAYOUT"
  | "MISSING_IN_LEDGER"
  | "SHORT_SETTLEMENT"
  | "REFUND"
  | "CHARGEBACK"
  | "DUPLICATE"
  | "FX_DIFF"
  | "SPLIT_PAYOUT"
  | "UNEXPLAINED";

export interface BatchSummary {
  batch_id: string;
  started_at: string;
  finished_at: string;
  runtime_seconds: number;
  rows_ingested: number;
  auto_matched_groups: number;
  auto_match_rate: number;
  clusters_adjudicated: number;
  exceptions: number;
  exceptions_by_code: Record<string, number>;
  auto_resolved: number;
  pending_approval: number;
  flagged_amount_inr: number;
  llm_used: boolean;
  llm_available: boolean;
  region?: string;
  currency?: string;
  formats?: Record<string, string>;
  persisted?: boolean;
}

export interface SampleDataset {
  folder: string;
  region: string;
  profile: string;
  pg_format: string;
  bank_format: string;
  strong: boolean;
  payments: number;
  currency: string;
  cross_border: number;
  injected_defects: number;
}

export interface ExceptionRecord {
  batch_id: string;
  cluster_id: string;
  anchor_source: string | null;
  anchor_external_id: string | null;
  anchor_utr: string | null;
  code: ExceptionCode;
  amount_impact: number;
  direction: string;
  confidence: number;
  rationale: string;
  evidence: string[];
  recommended_action: string;
  routed_to: "auto_resolved" | "pending_approval" | "resolved" | "rejected";
  created_at: string;
}

export interface AuditEntry {
  batch_id: string;
  actor: string;
  action: string;
  target_type: string;
  target_id: string;
  before: unknown;
  after: Record<string, unknown> | null;
  created_at: string;
}

export interface BatchResult {
  summary: BatchSummary;
  exceptions: ExceptionRecord[];
}
