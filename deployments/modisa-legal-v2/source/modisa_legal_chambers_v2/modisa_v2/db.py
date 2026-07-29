from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Iterator, Sequence


class Repository:
    """Transactional SQLite repository with an append-first schema.

    SQLite is the verified local runtime. The data model is intentionally portable to
    PostgreSQL; production deployment should use a managed database and migration tool.
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init_schema()

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat()

    @contextmanager
    def connect(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=10000")
            if immediate:
                conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=FULL;

                CREATE TABLE IF NOT EXISTS matters (
                    matter_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    jurisdiction TEXT NOT NULL,
                    forum TEXT NOT NULL,
                    privacy_tier TEXT NOT NULL DEFAULT 'P2_CONFIDENTIAL',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence_objects (
                    evidence_id TEXT PRIMARY KEY,
                    matter_id TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    media_type TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    encrypted INTEGER NOT NULL,
                    parent_evidence_id TEXT,
                    nested_depth INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    tainted_untrusted_content INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(matter_id) REFERENCES matters(matter_id),
                    FOREIGN KEY(parent_evidence_id) REFERENCES evidence_objects(evidence_id),
                    UNIQUE(matter_id, sha256, parent_evidence_id, original_name)
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_matter_sha ON evidence_objects(matter_id, sha256);

                CREATE TABLE IF NOT EXISTS proof_records (
                    proof_id TEXT PRIMARY KEY,
                    matter_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    proof_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    source_ids_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    chain_index INTEGER NOT NULL,
                    previous_hash TEXT NOT NULL,
                    chain_hash TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(matter_id) REFERENCES matters(matter_id),
                    UNIQUE(matter_id, chain_index),
                    UNIQUE(chain_hash)
                );
                CREATE INDEX IF NOT EXISTS idx_proof_mission ON proof_records(matter_id, mission_id, proof_type);
                CREATE INDEX IF NOT EXISTS idx_proof_subject ON proof_records(subject_id, proof_type);

                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    matter_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    proposition TEXT NOT NULL,
                    proof_state TEXT NOT NULL,
                    materiality TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(matter_id) REFERENCES matters(matter_id)
                );
                CREATE INDEX IF NOT EXISTS idx_claims_mission ON claims(matter_id, mission_id);

                CREATE TABLE IF NOT EXISTS claim_links (
                    link_id TEXT PRIMARY KEY,
                    claim_id TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    link_type TEXT NOT NULL,
                    weight REAL NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(claim_id) REFERENCES claims(claim_id),
                    UNIQUE(claim_id, object_id, link_type)
                );

                CREATE TABLE IF NOT EXISTS authorities (
                    authority_id TEXT PRIMARY KEY,
                    matter_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    citation TEXT NOT NULL,
                    title TEXT NOT NULL,
                    authority_type TEXT NOT NULL,
                    jurisdiction TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    source_domain TEXT NOT NULL,
                    proposition TEXT NOT NULL,
                    binding_level TEXT NOT NULL,
                    effective_from TEXT,
                    effective_to TEXT,
                    content_hash TEXT NOT NULL,
                    superseded_by TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(matter_id) REFERENCES matters(matter_id),
                    UNIQUE(matter_id, citation, proposition, content_hash)
                );

                CREATE TABLE IF NOT EXISTS legal_documents (
                    document_id TEXT PRIMARY KEY,
                    authority_id TEXT NOT NULL,
                    matter_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    effective_from TEXT,
                    effective_to TEXT,
                    superseded_by TEXT,
                    chunk_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(authority_id) REFERENCES authorities(authority_id),
                    FOREIGN KEY(matter_id) REFERENCES matters(matter_id),
                    UNIQUE(authority_id, source_hash)
                );

                CREATE TABLE IF NOT EXISTS legal_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES legal_documents(document_id),
                    UNIQUE(document_id, ordinal)
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS legal_chunks_fts USING fts5(
                    chunk_id UNINDEXED,
                    document_id UNINDEXED,
                    text,
                    tokenize='unicode61 remove_diacritics 2'
                );

                CREATE TABLE IF NOT EXISTS connector_contracts (
                    connector_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    credential_ref TEXT NOT NULL,
                    least_privilege_scopes_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_canary_at TEXT,
                    last_canary_proof_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    matter_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    action_digest TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    decided_by TEXT,
                    decision_reason TEXT,
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    decided_at TEXT,
                    consumed_at TEXT,
                    FOREIGN KEY(matter_id) REFERENCES matters(matter_id)
                );
                CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status, expires_at);

                CREATE TABLE IF NOT EXISTS action_receipts (
                    action_receipt_id TEXT PRIMARY KEY,
                    approval_id TEXT NOT NULL,
                    matter_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    action_digest TEXT NOT NULL,
                    provider_action_id TEXT NOT NULL,
                    provider_status TEXT NOT NULL,
                    readback_status TEXT NOT NULL,
                    execution_proof_id TEXT NOT NULL,
                    readback_proof_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(approval_id) REFERENCES approvals(approval_id),
                    FOREIGN KEY(matter_id) REFERENCES matters(matter_id),
                    UNIQUE(approval_id),
                    UNIQUE(provider_action_id, action_type)
                );

                CREATE TABLE IF NOT EXISTS workflows (
                    workflow_id TEXT PRIMARY KEY,
                    matter_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    workflow_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    lease_owner TEXT,
                    lease_expires_at TEXT,
                    next_run_at TEXT NOT NULL,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(matter_id) REFERENCES matters(matter_id)
                );
                CREATE INDEX IF NOT EXISTS idx_workflow_ready ON workflows(status, next_run_at, lease_expires_at);

                CREATE TABLE IF NOT EXISTS workflow_events (
                    event_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(workflow_id) REFERENCES workflows(workflow_id)
                );

                CREATE TABLE IF NOT EXISTS pending_agent_runs (
                    mission_id TEXT PRIMARY KEY,
                    matter_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    run_state_json TEXT NOT NULL,
                    approval_items_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(matter_id) REFERENCES matters(matter_id)
                );

                CREATE TABLE IF NOT EXISTS council_opinions (
                    opinion_id TEXT PRIMARY KEY,
                    matter_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    disposition TEXT NOT NULL,
                    conclusion TEXT NOT NULL,
                    supported_claims_json TEXT NOT NULL,
                    challenged_claims_json TEXT NOT NULL,
                    proof_ids_json TEXT NOT NULL,
                    risks_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(matter_id) REFERENCES matters(matter_id),
                    UNIQUE(matter_id, mission_id, role)
                );

                CREATE TABLE IF NOT EXISTS release_receipts (
                    release_receipt_id TEXT PRIMARY KEY,
                    matter_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    claim_ids_json TEXT NOT NULL,
                    proof_ids_json TEXT NOT NULL,
                    chain_head TEXT NOT NULL,
                    caveats_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(matter_id) REFERENCES matters(matter_id)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    matter_id TEXT,
                    actor_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    object_id TEXT,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(event_hash)
                );
                """
            )

    def ensure_matter(
        self,
        matter_id: str,
        title: str | None = None,
        jurisdiction: str = "South Africa",
        forum: str = "UNKNOWN",
        privacy_tier: str = "P2_CONFIDENTIAL",
    ) -> None:
        now = self.now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO matters(matter_id,title,jurisdiction,forum,privacy_tier,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(matter_id) DO UPDATE SET
                  title=excluded.title,
                  jurisdiction=excluded.jurisdiction,
                  forum=excluded.forum,
                  privacy_tier=excluded.privacy_tier,
                  updated_at=excluded.updated_at
                """,
                (matter_id, title or matter_id, jurisdiction, forum, privacy_tier, now, now),
            )

    @staticmethod
    def dumps(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def loads(value: str | None, default: Any = None) -> Any:
        if value is None:
            return default
        return json.loads(value)

    def fetch_one(self, query: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(query, tuple(params)).fetchone()

    def fetch_all(self, query: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(query, tuple(params)).fetchall())

    def execute(self, query: str, params: Sequence[Any] = ()) -> None:
        with self.connect() as conn:
            conn.execute(query, tuple(params))

    def count(self, table: str) -> int:
        allowed = {
            "matters", "evidence_objects", "proof_records", "claims", "claim_links",
            "authorities", "legal_documents", "legal_chunks", "connector_contracts", "approvals", "action_receipts", "workflows", "workflow_events",
            "pending_agent_runs", "council_opinions", "release_receipts", "audit_events",
        }
        if table not in allowed:
            raise ValueError("Unknown table")
        row = self.fetch_one(f"SELECT COUNT(*) AS n FROM {table}")
        return int(row["n"] if row else 0)

    def counts(self) -> dict[str, int]:
        return {name: self.count(name) for name in (
            "matters", "evidence_objects", "proof_records", "claims", "authorities",
            "approvals", "action_receipts", "workflows", "council_opinions",
            "release_receipts", "audit_events",
        )}
