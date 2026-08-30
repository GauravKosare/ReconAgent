from __future__ import annotations

from datetime import datetime

from app.matching import exact_match
from app.matching.fees import recompute_expected_fee
from app.models import NormalizedTxn, Source


def _txn(source: Source, **kw) -> NormalizedTxn:
    base = dict(
        batch_id="b1",
        source=source,
        raw_record_id=f"{source.value}:{kw.get('n', 0)}",
        amount_gross=1000.0,
        fee=20.0,
        tax=3.6,
        amount_net=976.4,
        txn_date=datetime(2026, 8, 1),
        settlement_date=datetime(2026, 8, 3),
        utr="UTR123",
    )
    base.update(kw)
    base.pop("n", None)
    return NormalizedTxn(**base)


def test_exact_three_way_match():
    txns = [
        _txn(Source.LEDGER, n=1),
        _txn(Source.PG, n=2),
        _txn(Source.BANK, n=3, amount_net=976.4, fee=0.0, tax=0.0, amount_gross=976.4),
    ]
    groups, leftovers = exact_match(txns)
    assert len(groups) == 1
    assert groups[0].status == "auto_matched"
    assert leftovers == []


def test_missing_bank_credit_is_leftover():
    txns = [_txn(Source.LEDGER, n=1), _txn(Source.PG, n=2)]
    groups, leftovers = exact_match(txns)
    assert groups == []
    assert len(leftovers) == 2


def test_fee_recompute_detects_overcharge():
    t = _txn(Source.PG, fee=25.0, amount_net=971.4)
    fe = recompute_expected_fee(t, mdr_percent=2.0, gst_percent=18.0)
    assert fe.expected_fee == 20.0
    assert round(fe.fee_delta, 2) == 5.0
    assert not fe.within_tolerance
