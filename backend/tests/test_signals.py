from __future__ import annotations

from datetime import datetime

from app.matching.candidates import Candidate, Cluster
from app.matching.signals import compute_signals
from app.models import NormalizedTxn, Source

REF = datetime(2026, 8, 30)
KW = dict(mdr_percent=2.0, gst_percent=18.0, sla_days=2, ref_date=REF)


def _t(source, **kw):
    base = dict(
        batch_id="b", source=source, raw_record_id=f"{source.value}:x",
        amount_gross=1000.0, fee=20.0, tax=3.6, amount_net=976.4,
        txn_date=datetime(2026, 8, 1), settlement_date=datetime(2026, 8, 3), utr="U1",
    )
    base.update(kw)
    return NormalizedTxn(**base)


def _cluster(anchor, *cands):
    return Cluster("c1", anchor, [Candidate(txn=c, score=0.9) for c in cands])


def test_fee_mismatch():
    pg = _t(Source.PG, raw_record_id="pg:1", fee=25.0, amount_net=971.4)
    bank = _t(Source.BANK, raw_record_id="bank:1", amount_gross=971.4, fee=0.0, tax=0.0, amount_net=971.4)
    led = _t(Source.LEDGER, raw_record_id="led:1")
    s = compute_signals(_cluster(led, pg, bank), [], **KW)
    assert s.suggested_code == "FEE_MISMATCH"
    assert s.suggested_amount_impact == 5.0


def test_short_settlement():
    pg = _t(Source.PG, raw_record_id="pg:1", fee=20.0, amount_net=950.0)  # fee ok, net short
    bank = _t(Source.BANK, raw_record_id="bank:1", amount_gross=950.0, amount_net=950.0, fee=0, tax=0)
    led = _t(Source.LEDGER, raw_record_id="led:1")
    s = compute_signals(_cluster(led, pg, bank), [], **KW)
    assert s.suggested_code == "SHORT_SETTLEMENT"
    assert s.suggested_amount_impact == 26.4


def test_timing_gap_late_bank():
    pg = _t(Source.PG, raw_record_id="pg:1")
    bank = _t(Source.BANK, raw_record_id="bank:1", amount_gross=976.4, amount_net=976.4, fee=0, tax=0,
              settlement_date=datetime(2026, 8, 9))  # 6 days after pg settlement
    led = _t(Source.LEDGER, raw_record_id="led:1")
    s = compute_signals(_cluster(led, pg, bank), [], **KW)
    assert s.suggested_code == "TIMING_GAP"
    assert s.bank_late_days == 6


def test_missing_payout_no_bank_sla_breached():
    pg = _t(Source.PG, raw_record_id="pg:1")
    led = _t(Source.LEDGER, raw_record_id="led:1")
    s = compute_signals(_cluster(led, pg), [], **KW)
    assert s.suggested_code == "MISSING_PAYOUT"
    assert s.sla_breached is True


def test_missing_in_ledger():
    pg = _t(Source.PG, raw_record_id="pg:1")
    bank = _t(Source.BANK, raw_record_id="bank:1", amount_gross=976.4, amount_net=976.4, fee=0, tax=0)
    s = compute_signals(_cluster(pg, bank), [], **KW)
    assert s.suggested_code == "MISSING_IN_LEDGER"


def test_duplicate():
    pg = _t(Source.PG, raw_record_id="pg:1")
    dup = _t(Source.PG, raw_record_id="pg:2")
    s = compute_signals(_cluster(pg), [pg, dup], **KW)
    assert s.suggested_code == "DUPLICATE"


def test_clean_match():
    pg = _t(Source.PG, raw_record_id="pg:1")
    bank = _t(Source.BANK, raw_record_id="bank:1", amount_gross=976.4, amount_net=976.4, fee=0, tax=0)
    led = _t(Source.LEDGER, raw_record_id="led:1")
    s = compute_signals(_cluster(led, pg, bank), [], **KW)
    assert s.suggested_verdict == "matched"
    assert s.suggested_code is None
