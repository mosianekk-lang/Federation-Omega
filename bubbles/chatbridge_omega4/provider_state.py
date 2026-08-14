from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


def _now() -> float:
    return time.time()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProviderReceipt:
    receipt_id: str
    namespace_id: str
    generation_id: str
    handoff_id: str
    checkpoint_fingerprint: str
    provider: str
    continuation_mode: str
    continuation_id: str
    response_id: str
    operation: str
    semantic_state: str
    output_sha256: str
    run_state_id: str = ""
    metadata: Dict[str, Any] | None = None
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["metadata"] = dict(self.metadata or {})
        return payload


class ProviderRunStateConflict(RuntimeError):
    pass


class ProviderStateStore:
    """Provider-bound receipts and resumable approval state for ChatBridge Ω4.

    This store is deliberately separate from the provider-neutral namespace/generation
    store. It can share the same SQLite file, while preserving a clean proof boundary
    between durable ChatBridge lineage and OpenAI provider execution evidence.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._local = threading.local()
        self._bootstrap()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            self._local.conn = conn
        return conn

    def _bootstrap(self) -> None:
        conn = sqlite3.connect(self.path)
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;

            CREATE TABLE IF NOT EXISTS provider_receipts(
                receipt_id TEXT PRIMARY KEY,
                namespace_id TEXT NOT NULL,
                generation_id TEXT NOT NULL,
                handoff_id TEXT NOT NULL,
                checkpoint_fingerprint TEXT NOT NULL,
                provider TEXT NOT NULL,
                continuation_mode TEXT NOT NULL,
                continuation_id TEXT NOT NULL,
                response_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                semantic_state TEXT NOT NULL,
                output_sha256 TEXT NOT NULL,
                run_state_id TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS provider_run_states(
                run_state_id TEXT PRIMARY KEY,
                namespace_id TEXT NOT NULL,
                generation_id TEXT NOT NULL,
                handoff_id TEXT NOT NULL,
                checkpoint_fingerprint TEXT NOT NULL,
                provider TEXT NOT NULL,
                continuation_id TEXT NOT NULL,
                state_json TEXT NOT NULL,
                state_sha256 TEXT NOT NULL,
                interruptions_json TEXT NOT NULL,
                status TEXT NOT NULL,
                fencing_token TEXT,
                claimed_at REAL,
                resumed_at REAL,
                resume_receipt_id TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_provider_receipts_generation
                ON provider_receipts(namespace_id, generation_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_provider_run_states_generation
                ON provider_run_states(namespace_id, generation_id, created_at DESC);
            """
        )
        conn.close()

    def save_receipt(
        self,
        *,
        namespace_id: str,
        generation_id: str,
        handoff_id: str,
        checkpoint_fingerprint: str,
        provider: str,
        continuation_mode: str,
        continuation_id: str,
        response_id: str,
        operation: str,
        semantic_state: str,
        output_text: str = "",
        run_state_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderReceipt:
        receipt = ProviderReceipt(
            receipt_id=f"cb4pr_{uuid.uuid4().hex}",
            namespace_id=namespace_id,
            generation_id=generation_id,
            handoff_id=handoff_id,
            checkpoint_fingerprint=checkpoint_fingerprint,
            provider=provider,
            continuation_mode=continuation_mode,
            continuation_id=continuation_id,
            response_id=response_id,
            operation=operation,
            semantic_state=semantic_state,
            output_sha256=_sha256_text(output_text),
            run_state_id=run_state_id,
            metadata=dict(metadata or {}),
            created_at=_now(),
        )
        payload = receipt.to_dict()
        conn = self._conn()
        with conn:
            conn.execute(
                """INSERT INTO provider_receipts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    receipt.receipt_id,
                    receipt.namespace_id,
                    receipt.generation_id,
                    receipt.handoff_id,
                    receipt.checkpoint_fingerprint,
                    receipt.provider,
                    receipt.continuation_mode,
                    receipt.continuation_id,
                    receipt.response_id,
                    receipt.operation,
                    receipt.semantic_state,
                    receipt.output_sha256,
                    receipt.run_state_id,
                    _canonical_json(payload["metadata"]),
                    receipt.created_at,
                ),
            )
        row = conn.execute(
            "SELECT * FROM provider_receipts WHERE receipt_id=?", (receipt.receipt_id,)
        ).fetchone()
        if not row or row["checkpoint_fingerprint"] != checkpoint_fingerprint:
            raise RuntimeError("provider receipt readback failed")
        return receipt

    def save_run_state(
        self,
        *,
        namespace_id: str,
        generation_id: str,
        handoff_id: str,
        checkpoint_fingerprint: str,
        provider: str,
        continuation_id: str,
        state_json: str,
        interruptions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        run_state_id = f"cb4rs_{uuid.uuid4().hex}"
        now = _now()
        digest = _sha256_text(state_json)
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO provider_run_states(
                    run_state_id,namespace_id,generation_id,handoff_id,checkpoint_fingerprint,
                    provider,continuation_id,state_json,state_sha256,interruptions_json,status,
                    fencing_token,claimed_at,resumed_at,resume_receipt_id,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_state_id, namespace_id, generation_id, handoff_id,
                    checkpoint_fingerprint, provider, continuation_id, state_json, digest,
                    _canonical_json(interruptions), "WAITING_APPROVAL", None, None, None,
                    None, now, now,
                ),
            )
        return self.get_run_state(run_state_id)

    def get_run_state(self, run_state_id: str) -> Dict[str, Any]:
        row = self._conn().execute(
            "SELECT * FROM provider_run_states WHERE run_state_id=?", (run_state_id,)
        ).fetchone()
        if not row:
            raise KeyError(run_state_id)
        out = dict(row)
        if _sha256_text(out["state_json"]) != out["state_sha256"]:
            raise ProviderRunStateConflict("persisted RunState digest mismatch")
        out["interruptions"] = json.loads(out.pop("interruptions_json"))
        return out

    def claim_run_state(self, run_state_id: str) -> Dict[str, Any]:
        """Atomically fence one approval-resume attempt.

        A previously resumed state is never replayed. A currently claimed state is also
        rejected so two workers cannot resume the same approval boundary concurrently.
        """
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT * FROM provider_run_states WHERE run_state_id=?", (run_state_id,)
            ).fetchone()
            if not row:
                raise KeyError(run_state_id)
            if row["status"] == "RESUMED":
                conn.execute("ROLLBACK")
                raise ProviderRunStateConflict("RunState already resumed")
            if row["status"] == "CLAIMED":
                conn.execute("ROLLBACK")
                raise ProviderRunStateConflict("RunState already claimed by another resume attempt")
            if row["status"] != "WAITING_APPROVAL":
                conn.execute("ROLLBACK")
                raise ProviderRunStateConflict(f"RunState cannot be resumed from {row['status']}")
            token = uuid.uuid4().hex
            now = _now()
            conn.execute(
                """UPDATE provider_run_states SET status='CLAIMED',fencing_token=?,claimed_at=?,updated_at=?
                   WHERE run_state_id=? AND status='WAITING_APPROVAL'""",
                (token, now, now, run_state_id),
            )
            readback = conn.execute(
                "SELECT * FROM provider_run_states WHERE run_state_id=?", (run_state_id,)
            ).fetchone()
            if not readback or readback["status"] != "CLAIMED" or readback["fencing_token"] != token:
                raise ProviderRunStateConflict("RunState claim readback failed")
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        return self.get_run_state(run_state_id)

    def release_claim(self, run_state_id: str, fencing_token: str) -> None:
        with self._conn() as conn:
            changed = conn.execute(
                """UPDATE provider_run_states SET status='WAITING_APPROVAL',fencing_token=NULL,
                   claimed_at=NULL,updated_at=? WHERE run_state_id=? AND status='CLAIMED'
                   AND fencing_token=?""",
                (_now(), run_state_id, fencing_token),
            ).rowcount
        if changed != 1:
            raise ProviderRunStateConflict("RunState claim could not be released")

    def mark_resumed(self, run_state_id: str, fencing_token: str, receipt_id: str) -> Dict[str, Any]:
        now = _now()
        with self._conn() as conn:
            changed = conn.execute(
                """UPDATE provider_run_states SET status='RESUMED',resumed_at=?,resume_receipt_id=?,
                   updated_at=? WHERE run_state_id=? AND status='CLAIMED' AND fencing_token=?""",
                (now, receipt_id, now, run_state_id, fencing_token),
            ).rowcount
        if changed != 1:
            raise ProviderRunStateConflict("RunState resume completion lost its fencing claim")
        return self.get_run_state(run_state_id)

    def latest_receipt(self, namespace_id: str, generation_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn().execute(
            """SELECT * FROM provider_receipts WHERE namespace_id=? AND generation_id=?
               ORDER BY created_at DESC LIMIT 1""",
            (namespace_id, generation_id),
        ).fetchone()
        if not row:
            return None
        out = dict(row)
        out["metadata"] = json.loads(out.pop("metadata_json"))
        return out
