const CCY_SYMBOL: Record<string, string> = { INR: "₹", USD: "$", EUR: "€" };
const CCY_LOCALE: Record<string, string> = { INR: "en-IN", USD: "en-US", EUR: "de-DE" };

/** Currency-aware money formatting — batches carry their own currency (multi-region). */
export const money = (n: number, currency = "INR") =>
  (CCY_SYMBOL[currency] ?? currency + " ") +
  Math.abs(n).toLocaleString(CCY_LOCALE[currency] ?? "en-IN", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  });

/** @deprecated use `money(n, currency)` — kept for INR-only demo data. */
export const inr = (n: number) => money(n, "INR");

export const pct = (n: number, digits = 1) => `${(n * 100).toFixed(digits)}%`;

export const CODE_LABEL: Record<string, string> = {
  FEE_MISMATCH: "Fee mismatch",
  TIMING_GAP: "Timing gap",
  MISSING_PAYOUT: "Missing payout",
  MISSING_IN_LEDGER: "Missing in ledger",
  SHORT_SETTLEMENT: "Short settlement",
  REFUND: "Refund",
  CHARGEBACK: "Chargeback",
  DUPLICATE: "Duplicate",
  FX_DIFF: "FX difference",
  SPLIT_PAYOUT: "Split payout",
  UNEXPLAINED: "Unexplained",
};

// tone per code — drives dot/label colour
export const CODE_TONE: Record<string, "bad" | "warn" | "ok" | "brand"> = {
  FEE_MISMATCH: "warn",
  SHORT_SETTLEMENT: "bad",
  MISSING_PAYOUT: "bad",
  MISSING_IN_LEDGER: "bad",
  CHARGEBACK: "bad",
  TIMING_GAP: "brand",
  DUPLICATE: "warn",
  REFUND: "brand",
  FX_DIFF: "warn",
  SPLIT_PAYOUT: "brand",
  UNEXPLAINED: "warn",
};

export const timeAgo = (iso: string) => {
  const d = (Date.now() - new Date(iso + (iso.endsWith("Z") ? "" : "Z")).getTime()) / 1000;
  if (Number.isNaN(d)) return iso;
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return `${Math.floor(d / 86400)}d ago`;
};

export const clockTime = (iso: string) => {
  const dt = new Date(iso + (iso.endsWith("Z") ? "" : "Z"));
  return Number.isNaN(dt.getTime())
    ? iso
    : dt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};
