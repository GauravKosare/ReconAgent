"""FastAPI routes.

POST /batches            upload 3 files, run reconciliation, return summary
GET  /batches/{id}       batch summary + metrics
GET  /batches/{id}/exceptions?routed_to=pending_approval
GET  /batches/{id}/audit
POST /approvals          reviewer decision on one exception
GET  /health
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..audit.log import audit
from ..config import get_settings
from ..pipeline.realistic import run_realistic_batch
from ..pipeline.runner import run_batch

router = APIRouter()

_SAMPLES_DIR = Path(__file__).resolve().parents[3] / "data" / "samples" / "realworld"
_MARKETPLACE_DEDUCTIONS = {"marketplace": (1.0, 5.0)}  # (tds%, reserve%)


def _load_index() -> list[dict[str, Any]]:
    idx = _SAMPLES_DIR / "index.json"
    return json.loads(idx.read_text()) if idx.exists() else []


@router.get("/health")
def health() -> dict[str, Any]:
    s = get_settings()
    return {"status": "ok", "llm_chain": s.llm_chain, "llm_available": s.llm_available}


@router.post("/batches")
async def create_batch(
    pg: UploadFile = File(...),
    bank: UploadFile = File(...),
    ledger: UploadFile = File(...),
) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="reconagent_"))
    paths = {}
    for name, upload in {"pg": pg, "bank": bank, "ledger": ledger}.items():
        dest = tmp / f"{name}.csv"
        dest.write_bytes(await upload.read())
        paths[name] = str(dest)
    return run_batch(paths["pg"], paths["bank"], paths["ledger"])


@router.post("/batches/realistic")
async def create_realistic_batch(
    pg: UploadFile = File(...),
    bank: UploadFile = File(...),
    ledger: UploadFile = File(...),
    region: str = Form("IN"),
    tds_percent: float | None = Form(None),
    reserve_percent: float | None = Form(None),
) -> dict[str, Any]:
    """Reconcile real-format statements (Razorpay recon / Stripe balance / MT940 /
    CAMT.053 / bank CSV). Formats are auto-detected; ``region`` picks currency + tax."""
    if region not in {"IN", "US", "EU"}:
        raise HTTPException(422, "region must be IN, US or EU")
    tmp = Path(tempfile.mkdtemp(prefix="reconagent_rw_"))
    paths = {}
    for name, upload in {"pg": pg, "bank": bank, "ledger": ledger}.items():
        suffix = Path(upload.filename or f"{name}.csv").suffix or ".csv"
        dest = tmp / f"{name}{suffix}"
        dest.write_bytes(await upload.read())
        paths[name] = str(dest)
    return run_realistic_batch(
        paths["pg"], paths["bank"], paths["ledger"],
        persist=True, region=region,
        tds_percent=tds_percent, reserve_percent=reserve_percent,
    )


@router.get("/samples")
def list_samples() -> list[dict[str, Any]]:
    return _load_index()


@router.post("/batches/realistic/sample")
def run_sample_batch(folder: str = Form(...)) -> dict[str, Any]:
    """Run one committed sample dataset from data/samples/realworld/ end to end."""
    entry = next((e for e in _load_index() if e["folder"] == folder), None)
    if entry is None:
        raise HTTPException(404, f"unknown sample dataset: {folder}")
    d = _SAMPLES_DIR / folder
    files = json.loads((d / "dataset_manifest.json").read_text())["files"]
    tds, reserve = _MARKETPLACE_DEDUCTIONS.get(entry["profile"], (0.0, 0.0))
    return run_realistic_batch(
        str(d / files["pg"]), str(d / files["bank"]), str(d / files["ledger"]),
        persist=True, region=entry["region"],
        tds_percent=tds, reserve_percent=reserve,
    )


@router.get("/batches")
def list_batches(limit: int = 20) -> list[dict[str, Any]]:
    from ..db import get_db

    return list(
        get_db().batches.find({}, {"_id": 1, "started_at": 1, "finished_at": 1,
                                   "rows_ingested": 1, "auto_match_rate": 1,
                                   "exceptions": 1, "auto_resolved": 1,
                                   "pending_approval": 1, "flagged_amount_inr": 1,
                                   "llm_used": 1, "runtime_seconds": 1,
                                   "region": 1, "currency": 1, "formats": 1})
        .sort("started_at", -1)
        .limit(limit)
    )


@router.get("/batches/{batch_id}")
def get_batch(batch_id: str) -> dict[str, Any]:
    from ..db import get_db

    doc = get_db().batches.find_one({"_id": batch_id})
    if not doc:
        raise HTTPException(404, "batch not found")
    return doc


@router.get("/batches/{batch_id}/exceptions")
def list_exceptions(batch_id: str, routed_to: str | None = None) -> list[dict[str, Any]]:
    from ..db import get_db

    q: dict[str, Any] = {"batch_id": batch_id}
    if routed_to:
        q["routed_to"] = routed_to
    return list(get_db().exceptions.find(q, {"_id": 0}))


@router.get("/batches/{batch_id}/audit")
def list_audit(batch_id: str) -> list[dict[str, Any]]:
    from ..db import get_db

    return list(get_db().audit_log.find({"batch_id": batch_id}, {"_id": 0}).sort("created_at", 1))


@router.post("/approvals")
def submit_approval(
    exception_cluster_id: str = Form(...),
    reviewer: str = Form(...),
    decision: str = Form(...),          # approve | reject | edit
    note: str = Form(""),
) -> dict[str, Any]:
    from ..db import get_db

    db = get_db()
    exc = db.exceptions.find_one({"cluster_id": exception_cluster_id})
    if not exc:
        raise HTTPException(404, "exception not found")

    db.approvals.insert_one(
        {
            "cluster_id": exception_cluster_id,
            "reviewer": reviewer,
            "decision": decision,
            "note": note,
        }
    )
    db.exceptions.update_one(
        {"cluster_id": exception_cluster_id},
        {"$set": {"routed_to": "resolved" if decision != "reject" else "rejected"}},
    )
    audit(exc["batch_id"], reviewer, f"approval:{decision}", "exception",
          exception_cluster_id, before=exc, after={"note": note})
    return {"ok": True}
