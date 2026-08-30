"""Append-only audit log. Every state change — ingest, match, adjudication,
route, human approval — lands here with before/after snapshots.

Falls back to stdout when the DB is unreachable so a local dry run still works.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any


def audit(
    batch_id: str,
    actor: str,               # system | agent | <reviewer email>
    action: str,
    target_type: str,
    target_id: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    entry = {
        "batch_id": batch_id,
        "actor": actor,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "before": before,
        "after": after,
        "created_at": datetime.utcnow(),
    }
    # Offline / eval mode: skip the DB round-trip entirely.
    if os.getenv("RECONAGENT_AUDIT_SINK") == "stderr":
        print("[audit]", json.dumps(entry, default=str), file=sys.stderr)
        return
    if os.getenv("RECONAGENT_AUDIT_SINK") == "none":
        return

    try:
        from ..db import get_db

        get_db().audit_log.insert_one(dict(entry))
    except Exception:  # noqa: BLE001 — audit must never break the pipeline
        print("[audit]", json.dumps(entry, default=str), file=sys.stderr)
