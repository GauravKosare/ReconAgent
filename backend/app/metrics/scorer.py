"""Score a reconciliation batch against a synthetic ground-truth key.

The scorer answers the questions the Buildathon rubric asks:
  * throughput      -> auto_match_rate, runtime, human queue size
  * measured accuracy -> detection precision/recall + per-code classification
  * exception handling -> confusion matrix, money surfaced vs money injected

It is deliberately tolerant of a run with **no LLM**: in that mode every
unresolved cluster is `UNEXPLAINED`, so detection recall is still meaningful
while classification accuracy is reported as N/A.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

_ORDER_RE = re.compile(r"ORD\d+", re.I)

# PRD section 8 targets.
TARGETS = {
    "auto_match_rate": 0.85,
    "detection_recall": 0.85,
    "classification_precision": 0.90,
    "queue_fraction_max": 0.15,
    "runtime_seconds_max": 300.0,
    "money_recovery_ratio": (0.95, 1.05),
}


@dataclass
class CodeStats:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float | None:
        d = self.tp + self.fp
        return round(self.tp / d, 3) if d else None

    @property
    def recall(self) -> float | None:
        d = self.tp + self.fn
        return round(self.tp / d, 3) if d else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        return round(2 * p * r / (p + r), 3) if p and r else None


@dataclass
class ScoreCard:
    txns: int
    injected_defects: int
    llm_used: bool
    auto_match_rate: float
    runtime_seconds: float
    queue_fraction: float

    detected: int
    false_positives: int
    detection_precision: float | None
    detection_recall: float | None

    classification_accuracy: float | None
    per_code: dict[str, CodeStats]
    confusion: dict[str, dict[str, int]]

    money_injected_inr: float
    money_surfaced_inr: float
    money_recovery_ratio: float | None

    passes: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "throughput": {
                "txns": self.txns,
                "auto_match_rate": self.auto_match_rate,
                "runtime_seconds": self.runtime_seconds,
                "human_queue_fraction": round(self.queue_fraction, 3),
            },
            "detection": {
                "injected_defects": self.injected_defects,
                "detected": self.detected,
                "false_positives": self.false_positives,
                "precision": self.detection_precision,
                "recall": self.detection_recall,
            },
            "classification": {
                "llm_used": self.llm_used,
                "accuracy": self.classification_accuracy,
                "per_code": {
                    k: {
                        "precision": v.precision,
                        "recall": v.recall,
                        "f1": v.f1,
                        "tp": v.tp,
                        "fp": v.fp,
                        "fn": v.fn,
                    }
                    for k, v in sorted(self.per_code.items())
                },
                "confusion": self.confusion,
            },
            "money": {
                "injected_inr": round(self.money_injected_inr, 2),
                "surfaced_inr": round(self.money_surfaced_inr, 2),
                "recovery_ratio": self.money_recovery_ratio,
            },
            "targets_met": self.passes,
            "overall_pass": all(self.passes.values()) if self.passes else False,
        }

    def markdown(self) -> str:
        rows = [
            "| Metric | Value | Target | Pass |",
            "| --- | --- | --- | --- |",
            f"| Auto-match rate | {self.auto_match_rate:.1%} | ≥ 85% | {_m(self.passes.get('auto_match_rate'))} |",
            f"| Detection recall | {_pct(self.detection_recall)} | ≥ 85% | {_m(self.passes.get('detection_recall'))} |",
            f"| Detection precision | {_pct(self.detection_precision)} | — | — |",
            f"| Classification accuracy | {_pct(self.classification_accuracy)} | ≥ 90% | {_m(self.passes.get('classification_precision'))} |",
            f"| Human queue | {self.queue_fraction:.1%} | ≤ 15% | {_m(self.passes.get('queue_fraction'))} |",
            f"| Runtime | {self.runtime_seconds:.1f}s | ≤ 300s | {_m(self.passes.get('runtime_seconds'))} |",
            f"| Money recovery ratio | {_ratio(self.money_recovery_ratio)} | 0.95–1.05 | {_m(self.passes.get('money_recovery_ratio'))} |",
        ]
        conf = ["", "**Per-code F1:**", "", "| Code | P | R | F1 | TP/FP/FN |", "| --- | --- | --- | --- | --- |"]
        for k, v in sorted(self.per_code.items()):
            conf.append(f"| {k} | {_pct(v.precision)} | {_pct(v.recall)} | {_pct(v.f1)} | {v.tp}/{v.fp}/{v.fn} |")
        return "\n".join(rows + conf)


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def _ratio(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def _m(x: bool | None) -> str:
    return {True: "✅", False: "❌", None: "—"}[x]


def _order_of(exc: dict, truth_by_utr: dict) -> str | None:
    ext = exc.get("anchor_external_id") or ""
    if _ORDER_RE.fullmatch(str(ext)):
        return str(ext)
    utr = exc.get("anchor_utr")
    if utr and utr in truth_by_utr:
        return truth_by_utr[utr]["order_id"]
    return None


def score_batch(result: dict, ground_truth: list[dict]) -> ScoreCard:
    summary = result["summary"]
    exceptions = result.get("exceptions", [])

    truth_by_order = {t["order_id"]: t for t in ground_truth}
    truth_by_utr = {t["utr"]: t for t in ground_truth if t.get("utr")}
    defects = {t["order_id"]: t["expected_code"] for t in ground_truth if t["expected_code"]}

    # order_id -> predicted codes (list; usually one)
    predicted: dict[str, list[str]] = defaultdict(list)
    surfaced_money = 0.0
    unmapped = 0
    for exc in exceptions:
        order = _order_of(exc, truth_by_utr)
        surfaced_money += abs(float(exc.get("amount_impact", 0) or 0))
        if order is None:
            unmapped += 1
            continue
        predicted[order].append(exc.get("code", "UNEXPLAINED"))

    detected = sum(1 for o in defects if o in predicted)
    false_positives = sum(
        1 for o in predicted if o not in defects and truth_by_order.get(o, {}).get("expected_code") is None
    ) + unmapped

    det_prec = round(detected / (detected + false_positives), 3) if (detected + false_positives) else None
    det_rec = round(detected / len(defects), 3) if defects else None

    # per-code + confusion (expected code -> predicted code)
    per_code: dict[str, CodeStats] = defaultdict(CodeStats)
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    correct = 0
    for order, expected in defects.items():
        preds = predicted.get(order, [])
        pred = preds[0] if preds else "MISSED"
        confusion[expected][pred] += 1
        if pred == expected:
            per_code[expected].tp += 1
            correct += 1
        else:
            per_code[expected].fn += 1
            if pred not in ("MISSED", "UNEXPLAINED"):
                per_code[pred].fp += 1
    # false-positive codes on clean orders
    for order, preds in predicted.items():
        if order in defects or not preds:
            continue
        per_code[preds[0]].fp += 1

    classification_accuracy = round(correct / detected, 3) if (detected and summary.get("llm_used")) else None

    money_injected = round(sum(t.get("injected_impact_inr", 0.0) for t in ground_truth), 2)
    recovery_ratio = round(surfaced_money / money_injected, 3) if money_injected else None

    txns = summary.get("rows_ingested", 0) // 3 or 1
    queue_fraction = summary.get("pending_approval", 0) / txns

    passes = {
        "auto_match_rate": summary.get("auto_match_rate", 0) >= TARGETS["auto_match_rate"],
        "detection_recall": (det_rec or 0) >= TARGETS["detection_recall"],
        "queue_fraction": queue_fraction <= TARGETS["queue_fraction_max"],
        "runtime_seconds": summary.get("runtime_seconds", 1e9) <= TARGETS["runtime_seconds_max"],
    }
    if classification_accuracy is not None:
        passes["classification_precision"] = classification_accuracy >= TARGETS["classification_precision"]
    # Money impact is only populated by the agent, so this check applies only to
    # LLM-backed runs. Deterministic-only runs still surface the defect rows.
    if recovery_ratio is not None and summary.get("llm_used"):
        lo, hi = TARGETS["money_recovery_ratio"]
        passes["money_recovery_ratio"] = lo <= recovery_ratio <= hi

    return ScoreCard(
        txns=txns,
        injected_defects=len(defects),
        llm_used=bool(summary.get("llm_used")),
        auto_match_rate=summary.get("auto_match_rate", 0.0),
        runtime_seconds=summary.get("runtime_seconds", 0.0),
        queue_fraction=queue_fraction,
        detected=detected,
        false_positives=false_positives,
        detection_precision=det_prec,
        detection_recall=det_rec,
        classification_accuracy=classification_accuracy,
        per_code=dict(per_code),
        confusion={k: dict(v) for k, v in confusion.items()},
        money_injected_inr=money_injected,
        money_surfaced_inr=round(surfaced_money, 2),
        money_recovery_ratio=recovery_ratio,
        passes=passes,
    )
