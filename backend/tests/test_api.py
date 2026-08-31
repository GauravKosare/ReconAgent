"""API surface tests. The reconciliation pipelines have their own deep tests;
here we only check the HTTP wiring (routing, validation, response shape)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert isinstance(body["llm_chain"], list)


def test_samples_index_served():
    rows = client.get("/samples").json()
    assert rows, "run scripts/gen_samples.py"
    entry = rows[0]
    assert {"folder", "region", "currency", "pg_format", "bank_format"} <= entry.keys()
    assert all(r["region"] in {"IN", "US", "EU"} for r in rows)


def test_realistic_rejects_bad_region():
    files = {k: (f"{k}.csv", b"a,b\n1,2\n", "text/csv") for k in ("pg", "bank", "ledger")}
    r = client.post("/batches/realistic", files=files, data={"region": "ZZ"})
    assert r.status_code == 422


def test_sample_run_unknown_folder():
    r = client.post("/batches/realistic/sample", data={"folder": "nope"})
    assert r.status_code == 404


def test_sample_run_end_to_end():
    """Full pipeline through the HTTP layer. Persistence is best-effort — the
    response must carry the reconciliation result even when Atlas is unreachable."""
    folder = client.get("/samples").json()[0]["folder"]
    r = client.post("/batches/realistic/sample", data={"folder": folder})
    assert r.status_code == 200
    s = r.json()["summary"]
    assert s["settlement_batches"] > 0
    assert s["currency"] in {"INR", "USD", "EUR"}
    assert "persisted" in s
    assert 0.0 <= s["auto_match_rate"] <= 1.0
