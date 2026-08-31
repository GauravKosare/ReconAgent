"""Append-only audit log. Every state change — ingest, match, adjudication,
route, human approval — lands here with before/after snapshots.

By default each entry is written immediately. During a batch run the pipeline
opens a buffer (`buffered()`) so all entries flush in a single `insert_many`
instead of one network round-trip each. Falls back to stderr when the DB is
unreachable so a local dry run still works.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from datetime import datetime
from typing import Any

_buffer: list[dict] | None = None


@contextlib.contextmanager
def buffered():
    """Collect audit entries and flush them once on exit."""
    global _buffer
    _buffer = []
    try:
        yield
    finally:
        entries, _buffer = _buffer, None
        if entries:
            _write_many(entries)


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
    sink = os.getenv("RECONAGENT_AUDIT_SINK")
    if sink == "none":
        return
    if sink == "stderr":
        print("[audit]", json.dumps(entry, default=str), file=sys.stderr)
        return
    if _buffer is not None:
        _buffer.append(entry)
        return
    _write_many([entry])


def _write_many(entries: list[dict]) -> None:
    try:
        from ..db import get_db

        get_db().audit_log.insert_many([dict(e) for e in entries])
    except Exception:  # noqa: BLE001 — audit must never break the pipeline
        for e in entries:
            print("[audit]", json.dumps(e, default=str), file=sys.stderr)
