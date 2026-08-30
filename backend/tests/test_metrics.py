from __future__ import annotations

from app.metrics import score_batch


def _truth():
    return [
        {"order_id": "ORD1", "utr": "U1", "expected_code": "FEE_MISMATCH",
         "gross": 1000, "expected_net": 976.4, "pg_net": 971.4, "injected_impact_inr": 5.0},
        {"order_id": "ORD2", "utr": "U2", "expected_code": "MISSING_PAYOUT",
         "gross": 500, "expected_net": 488.2, "pg_net": 488.2, "injected_impact_inr": 0.0},
        {"order_id": "ORD3", "utr": "U3", "expected_code": None,
         "gross": 200, "expected_net": 195.3, "pg_net": 195.3, "injected_impact_inr": 0.0},
    ]


def _result(exceptions, llm_used=True, auto_rate=0.9, pending=2, rows=9):
    return {
        "summary": {
            "rows_ingested": rows, "auto_match_rate": auto_rate,
            "pending_approval": pending, "runtime_seconds": 1.0, "llm_used": llm_used,
        },
        "exceptions": exceptions,
    }


def test_perfect_classification():
    exc = [
        {"anchor_external_id": "ORD1", "anchor_utr": "U1", "code": "FEE_MISMATCH", "amount_impact": 5.0},
        {"anchor_external_id": "ORD2", "anchor_utr": "U2", "code": "MISSING_PAYOUT", "amount_impact": 0.0},
    ]
    card = score_batch(_result(exc), _truth())
    assert card.detection_recall == 1.0
    assert card.classification_accuracy == 1.0
    assert card.false_positives == 0
    assert card.money_recovery_ratio == 1.0


def test_false_positive_on_clean_order():
    exc = [
        {"anchor_external_id": "ORD1", "anchor_utr": "U1", "code": "FEE_MISMATCH", "amount_impact": 5.0},
        {"anchor_external_id": "ORD2", "anchor_utr": "U2", "code": "MISSING_PAYOUT", "amount_impact": 0.0},
        {"anchor_external_id": "ORD3", "anchor_utr": "U3", "code": "DUPLICATE", "amount_impact": 0.0},
    ]
    card = score_batch(_result(exc), _truth())
    assert card.false_positives == 1
    assert card.detection_precision == round(2 / 3, 3)


def test_no_llm_reports_na_classification():
    exc = [
        {"anchor_external_id": "ORD1", "anchor_utr": "U1", "code": "UNEXPLAINED", "amount_impact": 0.0},
        {"anchor_external_id": "ORD2", "anchor_utr": "U2", "code": "UNEXPLAINED", "amount_impact": 0.0},
    ]
    card = score_batch(_result(exc, llm_used=False), _truth())
    assert card.detection_recall == 1.0
    assert card.classification_accuracy is None


def test_utr_fallback_mapping():
    exc = [{"anchor_external_id": "pay_abc", "anchor_utr": "U1", "code": "FEE_MISMATCH", "amount_impact": 5.0}]
    card = score_batch(_result(exc, pending=1), _truth())
    assert card.detected == 1
