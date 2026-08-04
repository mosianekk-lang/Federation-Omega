from __future__ import annotations

import hashlib
from contextlib import closing, contextmanager
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

STATES = {
    "CAPTURED", "TRIAGED", "READY", "ACTIVE", "CHECKPOINTED", "PAUSED",
    "BLOCKED", "RESUMABLE", "VERIFYING", "PROTOTYPE_COMPLETE",
    "TEST_PASSED", "PILOT_APPROVED", "DEPLOYMENT_APPROVED", "LIVE_LIMITED",
    "LIVE_FULL", "MONITORING", "MAINTENANCE_REQUIRED", "ROLLED_BACK",
    "COMPLETE", "SUPERSEDED", "RETIRED",
}

GATES: dict[str, set[str]] = {
    "PILOT_APPROVED": {"hypothesis", "success_metrics", "bounded_test", "rollback_plan"},
    "DEPLOYMENT_APPROVED": {
        "pilot_evidence", "privacy_review", "security_review",
        "maintenance_owner", "rollback_test",
    },
    "LIVE_FULL": {
        "limited_live_metrics", "monitoring_active",
        "no_unresolved_critical_defect", "support_ready",
    },
}


@dataclass(frozen=True)
class TransitionReceipt:
    event_id: str
    lane_id: str
    prior_state: str
    target_state: str
    evidence: tuple[str, ...]
    reason: str
    created_at: str
    previous_hash: str | None
    receipt_hash: str


@dataclass(frozen=True)
class BackupReceipt:
    database_sha256: str
    lane_count: int
    event_count: int
    chain_verified: bool
    integrity_check: str
    created_at: str


class InnovationRegistry:
    def __init__(self, database: str | Path = "innovation_engine.db") -> None:
        self.database = str(database)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS lanes(
                    lane_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    state TEXT NOT NULL,
                    priority REAL NOT NULL,
                    next_action TEXT NOT NULL,
                    proof_state TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    lane_id TEXT NOT NULL,
                    prior_state TEXT NOT NULL,
                    target_state TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    previous_hash TEXT,
                    receipt_hash TEXT UNIQUE NOT NULL
                );
                """
            )

    @staticmethod
    def _canonical_hash(payload: Mapping[str, object]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _file_sha256(path: str | Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def upsert_lane(
        self,
        lane_id: str,
        title: str,
        objective: str,
        state: str,
        priority: float,
        next_action: str,
        proof_state: str,
    ) -> None:
        if state not in STATES:
            raise ValueError(f"Unsupported state: {state}")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO lanes VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(lane_id) DO UPDATE SET
                    title=excluded.title,
                    objective=excluded.objective,
                    state=excluded.state,
                    priority=excluded.priority,
                    next_action=excluded.next_action,
                    proof_state=excluded.proof_state,
                    updated_at=excluded.updated_at
                """,
                (lane_id, title, objective, state, priority, next_action, proof_state, now),
            )

    def transition(
        self,
        lane_id: str,
        target_state: str,
        evidence: Iterable[str],
        reason: str,
    ) -> TransitionReceipt:
        if target_state not in STATES:
            raise ValueError(f"Unsupported target state: {target_state}")

        evidence_set = tuple(sorted({item.strip() for item in evidence if item.strip()}))
        required = GATES.get(target_state, set())
        missing = sorted(required - set(evidence_set))
        if missing:
            raise ValueError(f"Proof gate failed for {target_state}; missing: {', '.join(missing)}")

        with self._connect() as connection:
            lane = connection.execute(
                "SELECT state FROM lanes WHERE lane_id=?", (lane_id,)
            ).fetchone()
            if lane is None:
                raise KeyError(f"Unknown lane: {lane_id}")

            previous = connection.execute(
                "SELECT receipt_hash FROM events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous_hash = previous["receipt_hash"] if previous else None
            created_at = datetime.now(timezone.utc).isoformat()
            event_id = f"EVT-{uuid.uuid4().hex.upper()}"
            receipt_payload = {
                "event_id": event_id,
                "lane_id": lane_id,
                "prior_state": lane["state"],
                "target_state": target_state,
                "evidence": evidence_set,
                "reason": reason,
                "created_at": created_at,
                "previous_hash": previous_hash,
            }
            receipt_hash = self._canonical_hash(receipt_payload)
            connection.execute(
                "UPDATE lanes SET state=?, updated_at=? WHERE lane_id=?",
                (target_state, created_at, lane_id),
            )
            connection.execute(
                "INSERT INTO events(event_id,lane_id,prior_state,target_state,evidence_json,reason,created_at,previous_hash,receipt_hash) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    event_id, lane_id, lane["state"], target_state,
                    json.dumps(evidence_set), reason, created_at,
                    previous_hash, receipt_hash,
                ),
            )

        return TransitionReceipt(
            event_id=event_id,
            lane_id=lane_id,
            prior_state=lane["state"],
            target_state=target_state,
            evidence=evidence_set,
            reason=reason,
            created_at=created_at,
            previous_hash=previous_hash,
            receipt_hash=receipt_hash,
        )

    def verify_chain(self) -> bool:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
        prior: str | None = None
        for row in rows:
            evidence = tuple(json.loads(row["evidence_json"]))
            payload = {
                "event_id": row["event_id"],
                "lane_id": row["lane_id"],
                "prior_state": row["prior_state"],
                "target_state": row["target_state"],
                "evidence": evidence,
                "reason": row["reason"],
                "created_at": row["created_at"],
                "previous_hash": row["previous_hash"],
            }
            if row["previous_hash"] != prior or self._canonical_hash(payload) != row["receipt_hash"]:
                return False
            prior = row["receipt_hash"]
        return True

    def ranked_open_lanes(self) -> Sequence[sqlite3.Row]:
        terminal = ("COMPLETE", "SUPERSEDED", "RETIRED")
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM lanes WHERE state NOT IN (?,?,?) ORDER BY priority DESC, updated_at ASC",
                terminal,
            ).fetchall()

    def backup(self, destination: str | Path) -> BackupReceipt:
        """Create a transactionally consistent SQLite backup and verify it."""
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = destination_path.with_suffix(destination_path.suffix + ".tmp")
        temporary_path.unlink(missing_ok=True)

        with self._connect() as source, closing(sqlite3.connect(temporary_path)) as target:
            source.backup(target)
            target.commit()

        with closing(sqlite3.connect(temporary_path)) as connection:
            integrity_check = connection.execute("PRAGMA integrity_check").fetchone()[0]
            lane_count = connection.execute("SELECT COUNT(*) FROM lanes").fetchone()[0]
            event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        if integrity_check != "ok":
            temporary_path.unlink(missing_ok=True)
            raise RuntimeError(f"Backup integrity check failed: {integrity_check}")

        backup_registry = InnovationRegistry(temporary_path)
        chain_verified = backup_registry.verify_chain()
        if not chain_verified:
            temporary_path.unlink(missing_ok=True)
            raise RuntimeError("Backup receipt chain verification failed")

        os.replace(temporary_path, destination_path)
        return BackupReceipt(
            database_sha256=self._file_sha256(destination_path),
            lane_count=lane_count,
            event_count=event_count,
            chain_verified=chain_verified,
            integrity_check=integrity_check,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def restore(
        cls,
        source: str | Path,
        destination: str | Path,
        expected_sha256: str | None = None,
    ) -> "InnovationRegistry":
        """Verify a backup before atomically restoring it to a new database."""
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        actual_sha256 = cls._file_sha256(source_path)
        if expected_sha256 and actual_sha256 != expected_sha256:
            raise ValueError("Backup SHA-256 mismatch")

        with closing(sqlite3.connect(source_path)) as source_connection:
            integrity_check = source_connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity_check != "ok":
            raise RuntimeError(f"Source integrity check failed: {integrity_check}")
        source_registry = cls(source_path)
        if not source_registry.verify_chain():
            raise RuntimeError("Source receipt chain verification failed")

        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = destination_path.with_suffix(destination_path.suffix + ".restore.tmp")
        temporary_path.unlink(missing_ok=True)
        with closing(sqlite3.connect(source_path)) as source_connection, closing(sqlite3.connect(temporary_path)) as target:
            source_connection.backup(target)
            target.commit()
        os.replace(temporary_path, destination_path)

        restored = cls(destination_path)
        if not restored.verify_chain():
            destination_path.unlink(missing_ok=True)
            raise RuntimeError("Restored receipt chain verification failed")
        return restored
