"""Round-trip tests: realistic generator -> real-format files -> parsers ->
settlement reconciliation -> scorecard."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data.realworld.emit import EMITTERS  # noqa: E402
from data.realworld.scenario import build_scenario  # noqa: E402

from app.ingest.formats import detect_and_parse  # noqa: E402
from app.matching.settlement import reconcile_settlements  # noqa: E402
from app.metrics import score_batch  # noqa: E402
from app.models import Source  # noqa: E402
from app.pipeline.realistic import run_realistic_batch  # noqa: E402


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    sc = build_scenario("d2c-brand", payments=250, seed=7)
    d = tmp_path_factory.mktemp("rw")
    files = {}
    for key in ("razorpay", "ledger", "hdfc"):
        fname, fn = EMITTERS[key]
        (d / fname).write_text(fn(sc), encoding="utf-8")
        files[key] = str(d / fname)
    return sc, files


def test_format_detection(dataset):
    _sc, f = dataset
    assert detect_and_parse(f["razorpay"], "b")[1] == "razorpay"
    assert detect_and_parse(f["ledger"], "b")[1] == "ledger_csv"
    assert detect_and_parse(f["hdfc"], "b")[1] == "bank_csv"


@pytest.mark.parametrize("bank", ["mt940", "camt", "hdfc", "icici"])
def test_all_bank_formats_parse(bank, tmp_path):
    sc = build_scenario("d2c-brand", payments=120, seed=3)
    fname, fn = EMITTERS[bank]
    p = tmp_path / fname
    p.write_text(fn(sc), encoding="utf-8")
    src, _fmt, rows = detect_and_parse(str(p), "b")
    assert src is Source.BANK
    assert rows and all(r.amount_net != 0 for r in rows)
    # most rows carry a UTR; terse RTGS lines (esp. ICICI) may not — the
    # reconciler's amount+date fuzzy fallback covers those.
    assert sum(1 for r in rows if r.utr) >= len(rows) * 0.55


def test_razorpay_paise_and_unix(dataset):
    _sc, f = dataset
    _src, _fmt, rows = detect_and_parse(f["razorpay"], "b")
    payments = [r for r in rows if r.kind == "payment"]
    assert payments
    r = payments[0]
    assert 1 < r.amount_gross < 1_000_000          # rupees, not paise
    assert r.txn_date and r.txn_date.year == 2026   # unix -> datetime
    assert r.settlement_id and r.utr


def test_settlement_reconciliation_matches_most_batches(dataset):
    sc, f = dataset
    txns = []
    for path in (f["ledger"], f["razorpay"], f["hdfc"]):
        txns += detect_and_parse(path, "b")[2]
    res = reconcile_settlements(txns, sla_days=2)
    rep = res.batch_report
    assert rep["reconciled"] >= rep["batches"] * 0.8
    assert res.groups                                   # lines auto-matched


def test_end_to_end_scores_well(dataset):
    sc, f = dataset
    result = run_realistic_batch(f["razorpay"], f["hdfc"], f["ledger"])
    card = score_batch(result, sc.truth)
    d = card.to_dict()
    assert d["throughput"]["auto_match_rate"] >= 0.85
    assert d["detection"]["recall"] >= 0.75
    assert d["detection"]["precision"] >= 0.75
