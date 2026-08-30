"""MongoDB Atlas client and collection helpers.

Collections
-----------
batches           one reconciliation run
raw_records       verbatim source rows (immutable) — heterogeneous documents
normalized_txns   source rows mapped to the common transaction schema
match_groups      three-way links (ledger <-> pg <-> bank)
exceptions        classified mismatches with agent verdict + confidence
resolutions       recommended action + routing decision
approvals         human decisions on the approval queue
audit_log         append-only record of every state change
agent_runs        per-cluster LLM call metadata (model, tokens, latency, tools)
"""

from __future__ import annotations

from functools import lru_cache

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database

from .config import get_settings

COLLECTIONS = [
    "batches",
    "raw_records",
    "normalized_txns",
    "match_groups",
    "exceptions",
    "resolutions",
    "approvals",
    "audit_log",
    "agent_runs",
]


@lru_cache
def get_client() -> MongoClient:
    settings = get_settings()
    return MongoClient(settings.mongodb_uri, tz_aware=True)


def get_db() -> Database:
    return get_client()[get_settings().mongodb_db]


def ensure_indexes() -> None:
    db = get_db()
    db.raw_records.create_index([("batch_id", ASCENDING), ("source", ASCENDING)])
    db.normalized_txns.create_index([("batch_id", ASCENDING), ("source", ASCENDING)])
    db.normalized_txns.create_index([("utr", ASCENDING)])
    db.normalized_txns.create_index([("external_id", ASCENDING)])
    db.match_groups.create_index([("batch_id", ASCENDING), ("status", ASCENDING)])
    db.exceptions.create_index([("batch_id", ASCENDING), ("code", ASCENDING)])
    db.resolutions.create_index([("exception_id", ASCENDING)])
    db.approvals.create_index([("resolution_id", ASCENDING)])
    db.audit_log.create_index([("batch_id", ASCENDING), ("created_at", ASCENDING)])
    db.agent_runs.create_index([("cluster_id", ASCENDING)])
    # NOTE: create the Atlas Vector Search index on normalized_txns.narration_embedding
    # from the Atlas UI or the search-index API (not creatable via this driver call).
