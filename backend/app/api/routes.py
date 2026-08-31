"""FastAPI routes.

POST /batches            upload 3 files, run reconciliation, return summary
GET  /batches/{id}       batch summary + metrics
GET  /batches/{id}/exceptions?routed_to=pending_approval
GET  /batches/{id}/audit
POST /approvals          reviewer decision on one exception
GET  /health
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..audit.log import audit
from ..config import get_settings
from ..pipeline.runner import run_batch

router = APIRouter()


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


@router.get("/batches")
def list_batches(limit: int = 20) -> list[dict[str, Any]]:
    from ..db import get_db

    return list(
        get_db().batches.find({}, {"_id": 1, "started_at": 1, "finished_at": 1,
                                   "rows_ingested": 1, "auto_match_rate": 1,
                                   "exceptions": 1, "auto_resolved": 1,
                                   "pending_approval": 1, "flagged_amount_inr": 1,
                                   "llm_used": 1, "runtime_seconds": 1})
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
