"""Round-trip tests: region-aware generator -> real-format files -> parsers ->
settlement reconciliation -> scorecard, for IN / US / EU."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data.realworld.emit import EMITTERS  # noqa: E402
from data.realworld.regions import REGIONS  # noqa: E402
from data.realworld.scenario import build_scenario  # noqa: E402

from app.ingest.formats import detect_and_parse  # noqa: E402
from app.ingest.formats._locale import parse_amount  # noqa: E402
from app.matching.region_rules import region_rules  # noqa: E402
from app.metrics import score_batch  # noqa: E402
from app.models import Source  # noqa: E402
from app.pipeline.realistic import run_realistic_batch  # noqa: E402

REGION_FILES = {
    "IN": ("razorpay", "hdfc"),
    "US": ("stripe", "us_csv"),
    "EU": ("stripe", "camt"),
}


def _write(region, seed, payments, tmp):
    pg_key, bank_key = REGION_FILES[region]
    sc = build_scenario("d2c-brand", region, payments=payments, seed=seed)
    files = {}
    for key in (pg_key, "ledger", bank_key):
        fname, fn = EMITTERS[key]
        (tmp / fname).write_text(fn(sc), encoding="utf-8")
        files[key] = str(tmp / fname)
    return sc, files, pg_key, bank_key


def test_locale_amount_parsing():
    assert parse_amount("1,234.56") == 1234.56       # US / IN
    assert parse_amount("1.234,56") == 1234.56       # EU
    assert parse_amount("12,34,567.89") == 1234567.89  # Indian grouping
    assert parse_amount("(45.00)") == -45.0


@pytest.mark.parametrize("region", ["IN", "US", "EU"])
def test_formats_detect_and_carry_currency(region, tmp_path):
    sc, files, pg_key, bank_key = _write(region, 3, 200, tmp_path)
    ccy = REGIONS[region].currency
    srcs = {}
    for path in files.values():
        src, fmt, rows = detect_and_parse(path, "b")
        srcs[src] = (fmt, rows)
    assert Source.PG in srcs and Source.BANK in srcs and Source.LEDGER in srcs
    pg_rows = [r for r in srcs[Source.PG][1] if r.kind == "payment"]
    bank_rows = srcs[Source.BANK][1]
    assert {r.currency for r in pg_rows} == {ccy}
    assert {r.currency for r in bank_rows} == {ccy}


@pytest.mark.parametrize("region", ["IN", "US", "EU"])
def test_cross_border_flows_through(region, tmp_path):
    sc, files, *_ = _write(region, 3, 300, tmp_path)
    assert sc.stats["cross_border_payments"] > 0
    _src, _fmt, pg = detect_and_parse(files[REGION_FILES[region][0]], "b")
    assert any(r.presentment_currency and r.presentment_currency != r.currency for r in pg)


@pytest.mark.parametrize("region", ["IN", "US", "EU"])
def test_end_to_end_scores(region, tmp_path):
    sc, files, pg_key, bank_key = _write(region, 7, 300, tmp_path)
    result = run_realistic_batch(files[pg_key], files[bank_key], files["ledger"], region=region)
    card = score_batch(result, sc.truth).to_dict()
    assert result["summary"]["currency"] == REGIONS[region].currency
    assert card["throughput"]["auto_match_rate"] >= 0.82
    assert card["detection"]["recall"] >= 0.7
    assert card["detection"]["precision"] >= 0.85


def test_region_rules_match_generator():
    for code, rules in region_rules.__globals__["RULES"].items():
        assert rules.currency == REGIONS[code].currency
