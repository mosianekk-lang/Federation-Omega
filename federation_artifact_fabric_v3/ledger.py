"""SQLite-backed transactional event ledger for Artifact Fabric v3."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
import json
import sqlite3
from threading import RLock
from typing import Any, Iterator, Mapping
import uuid

from .canonical import canonical_json_bytes, merkle_root, sha256_bytes
from .model import (
    ArtifactRequest,
    IdempotencyCollision,
    InvalidTransition,
    ProviderObject,
    SignatureEnvelope,
    TransactionState,
    ensure_transition_allowed,
)


SCHEMA_VERSION = "FAF3-SQLITE-LEDGER-1"
GENESIS_HASH = "0" * 64


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _json(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8").rstrip("\n")


class ArtifactLedger:
    """Durable transaction/event ledger with hash-linked append-only events."""

    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self._lock = RLock()
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA synchronous = FULL")
        self._create_schema()

    def close(self) -> None:
        try:
            self._connection.close()
        except sqlite3.ProgrammingError:
            pass

    def __enter__(self) -> "ArtifactLedger":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield self._connection
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS fabric_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    artifact_name TEXT NOT NULL,
                    workstream TEXT NOT NULL,
                    version TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    destination_alias TEXT NOT NULL,
                    retention_class TEXT NOT NULL,
                    sensitivity TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    resume_state TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    generation INTEGER NOT NULL DEFAULT 1,
                    provider_object_json TEXT,
                    projection_json TEXT,
                    scan_report_json TEXT,
                    receipt_json TEXT,
                    signature_json TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    transaction_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY(transaction_id) REFERENCES transactions(transaction_id)
                );
                CREATE INDEX IF NOT EXISTS idx_events_transaction
                    ON events(transaction_id, sequence);
                CREATE TABLE IF NOT EXISTS dead_letters (
                    transaction_id TEXT PRIMARY KEY,
                    reason TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY(transaction_id) REFERENCES transactions(transaction_id)
                );
                """
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO fabric_meta(key, value) VALUES('schema_version', ?)",
                (SCHEMA_VERSION,),
            )

    @staticmethod
    def idempotency_key(request: ArtifactRequest, content_sha256: str) -> str:
        value = {
            "artifact_name": request.artifact_name,
            "content_sha256": content_sha256,
            "version": request.version,
            "workstream": request.workstream,
        }
        return sha256_bytes(canonical_json_bytes(value))

    def _last_event_hash(self, connection: sqlite3.Connection) -> str:
        row = connection.execute(
            "SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return str(row["event_hash"]) if row else GENESIS_HASH

    def _append_event(
        self,
        connection: sqlite3.Connection,
        *,
        transaction_id: str,
        event_type: str,
        from_state: TransactionState | None,
        to_state: TransactionState,
        payload: Mapping[str, Any] | None = None,
    ) -> str:
        recorded_at = utc_now()
        event_id = f"FAF3-EVT-{uuid.uuid4()}"
        previous_hash = self._last_event_hash(connection)
        body = {
            "event_id": event_id,
            "event_type": event_type,
            "from_state": str(from_state) if from_state is not None else None,
            "payload": dict(payload or {}),
            "previous_hash": previous_hash,
            "recorded_at": recorded_at,
            "to_state": str(to_state),
            "transaction_id": transaction_id,
        }
        event_hash = sha256_bytes(canonical_json_bytes(body))
        connection.execute(
            """
            INSERT INTO events(
                event_id, transaction_id, event_type, from_state, to_state,
                payload_json, previous_hash, event_hash, recorded_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                transaction_id,
                event_type,
                str(from_state) if from_state is not None else None,
                str(to_state),
                _json(dict(payload or {})),
                previous_hash,
                event_hash,
                recorded_at,
            ),
        )
        return event_hash

    def get_or_create(
        self,
        request: ArtifactRequest,
        *,
        content_sha256: str,
        size_bytes: int,
    ) -> tuple[dict[str, Any], bool]:
        key = self.idempotency_key(request, content_sha256)
        with self._tx() as connection:
            existing = connection.execute(
                "SELECT * FROM transactions WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if existing:
                facts = {
                    "artifact_name": request.artifact_name,
                    "workstream": request.workstream,
                    "version": request.version,
                    "content_sha256": content_sha256,
                    "size_bytes": size_bytes,
                    "media_type": request.media_type,
                    "destination_alias": request.destination_alias,
                }
                for field, expected in facts.items():
                    if str(existing[field]) != str(expected):
                        raise IdempotencyCollision(
                            f"idempotency collision on {field}: {existing[field]!r} != {expected!r}"
                        )
                return self._row(existing), False

            transaction_id = f"FAF3-TX-{uuid.uuid4()}"
            now = utc_now()
            connection.execute(
                """
                INSERT INTO transactions(
                    transaction_id, idempotency_key, artifact_name, workstream,
                    version, media_type, destination_alias, retention_class,
                    sensitivity, source_ref, metadata_json, content_sha256,
                    size_bytes, state, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction_id,
                    key,
                    request.artifact_name,
                    request.workstream,
                    request.version,
                    request.media_type,
                    request.destination_alias,
                    str(request.retention_class),
                    str(request.sensitivity),
                    request.source_ref,
                    _json(dict(request.metadata)),
                    content_sha256,
                    size_bytes,
                    str(TransactionState.RECEIVED),
                    now,
                    now,
                ),
            )
            self._append_event(
                connection,
                transaction_id=transaction_id,
                event_type="TRANSACTION_CREATED",
                from_state=None,
                to_state=TransactionState.RECEIVED,
                payload={"idempotency_key": key},
            )
            row = connection.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
            ).fetchone()
            assert row is not None
            return self._row(row), True

    def transition(
        self,
        transaction_id: str,
        target: TransactionState,
        *,
        event_type: str,
        payload: Mapping[str, Any] | None = None,
        expected_generation: int | None = None,
        provider_object: ProviderObject | None = None,
        scan_report: Mapping[str, Any] | None = None,
        projection: Mapping[str, Any] | None = None,
        receipt: Mapping[str, Any] | None = None,
        signature: SignatureEnvelope | Mapping[str, Any] | None = None,
        last_error: str | None = None,
    ) -> dict[str, Any]:
        with self._tx() as connection:
            row = connection.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
            ).fetchone()
            if row is None:
                raise KeyError(transaction_id)
            current = TransactionState(str(row["state"]))
            ensure_transition_allowed(current, target)
            generation = int(row["generation"])
            if expected_generation is not None and generation != expected_generation:
                raise InvalidTransition(
                    f"stale generation for {transaction_id}: {expected_generation} != {generation}"
                )
            updates: dict[str, Any] = {
                "state": str(target),
                "generation": generation + 1,
                "updated_at": utc_now(),
            }
            if provider_object is not None:
                updates["provider_object_json"] = _json(asdict(provider_object))
            if scan_report is not None:
                updates["scan_report_json"] = _json(dict(scan_report))
            if projection is not None:
                updates["projection_json"] = _json(dict(projection))
            if receipt is not None:
                updates["receipt_json"] = _json(dict(receipt))
            if signature is not None:
                updates["signature_json"] = _json(
                    asdict(signature) if isinstance(signature, SignatureEnvelope) else dict(signature)
                )
            if last_error is not None:
                updates["last_error"] = last_error
            assignments = ", ".join(f"{key} = ?" for key in updates)
            connection.execute(
                f"UPDATE transactions SET {assignments} WHERE transaction_id = ?",
                tuple(updates.values()) + (transaction_id,),
            )
            self._append_event(
                connection,
                transaction_id=transaction_id,
                event_type=event_type,
                from_state=current,
                to_state=target,
                payload=payload,
            )
            updated = connection.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
            ).fetchone()
            assert updated is not None
            return self._row(updated)

    def hold(
        self,
        transaction_id: str,
        *,
        reason: str,
        retryable: bool,
        max_attempts: int,
    ) -> dict[str, Any]:
        with self._tx() as connection:
            row = connection.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
            ).fetchone()
            if row is None:
                raise KeyError(transaction_id)
            current = TransactionState(str(row["state"]))
            if current in {TransactionState.DELIVERED, TransactionState.FAILED, TransactionState.DEAD_LETTER}:
                return self._row(row)
            attempts = int(row["attempts"]) + 1
            target = (
                TransactionState.DEAD_LETTER
                if retryable and attempts >= max_attempts
                else TransactionState.HOLD
            )
            if current != TransactionState.HOLD:
                ensure_transition_allowed(current, TransactionState.HOLD)
            now = utc_now()
            connection.execute(
                """
                UPDATE transactions
                SET state = ?, resume_state = ?, attempts = ?, generation = generation + 1,
                    last_error = ?, updated_at = ?
                WHERE transaction_id = ?
                """,
                (str(target), str(current), attempts, reason, now, transaction_id),
            )
            self._append_event(
                connection,
                transaction_id=transaction_id,
                event_type="DEAD_LETTERED" if target == TransactionState.DEAD_LETTER else "HELD",
                from_state=current,
                to_state=target,
                payload={"reason": reason, "attempts": attempts, "retryable": retryable},
            )
            if target == TransactionState.DEAD_LETTER:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO dead_letters(transaction_id, reason, attempts, recorded_at)
                    VALUES(?, ?, ?, ?)
                    """,
                    (transaction_id, reason, attempts, now),
                )
            updated = connection.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
            ).fetchone()
            assert updated is not None
            return self._row(updated)

    def resume_hold(self, transaction_id: str) -> dict[str, Any]:
        with self._tx() as connection:
            row = connection.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
            ).fetchone()
            if row is None:
                raise KeyError(transaction_id)
            current = TransactionState(str(row["state"]))
            if current != TransactionState.HOLD:
                return self._row(row)
            resume_raw = row["resume_state"]
            if not resume_raw:
                raise InvalidTransition("held transaction has no resume_state")
            resume_state = TransactionState(str(resume_raw))
            now = utc_now()
            connection.execute(
                """
                UPDATE transactions
                SET state = ?, resume_state = NULL, generation = generation + 1,
                    updated_at = ?
                WHERE transaction_id = ?
                """,
                (str(resume_state), now, transaction_id),
            )
            self._append_event(
                connection,
                transaction_id=transaction_id,
                event_type="RESUMED",
                from_state=TransactionState.HOLD,
                to_state=resume_state,
                payload={},
            )
            updated = connection.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
            ).fetchone()
            assert updated is not None
            return self._row(updated)

    def get(self, transaction_id: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
        ).fetchone()
        return self._row(row) if row else None

    def get_by_idempotency(self, key: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT * FROM transactions WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return self._row(row) if row else None

    def list_transactions(self, *, state: TransactionState | None = None) -> list[dict[str, Any]]:
        if state is None:
            rows = self._connection.execute(
                "SELECT * FROM transactions ORDER BY created_at, transaction_id"
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM transactions WHERE state = ? ORDER BY created_at, transaction_id",
                (str(state),),
            ).fetchall()
        return [self._row(row) for row in rows]

    def list_events(self, transaction_id: str | None = None) -> list[dict[str, Any]]:
        if transaction_id is None:
            rows = self._connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM events WHERE transaction_id = ? ORDER BY sequence",
                (transaction_id,),
            ).fetchall()
        return [self._event_row(row) for row in rows]

    def event_chain_head(self) -> str:
        row = self._connection.execute(
            "SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return str(row["event_hash"]) if row else GENESIS_HASH

    def verify_event_chain(self) -> bool:
        previous = GENESIS_HASH
        for event in self.list_events():
            body = {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "from_state": event["from_state"],
                "payload": event["payload"],
                "previous_hash": previous,
                "recorded_at": event["recorded_at"],
                "to_state": event["to_state"],
                "transaction_id": event["transaction_id"],
            }
            expected = sha256_bytes(canonical_json_bytes(body))
            if event["previous_hash"] != previous or event["event_hash"] != expected:
                return False
            previous = event["event_hash"]
        return True

    def delivered_merkle_root(self) -> str:
        rows = self._connection.execute(
            "SELECT receipt_json FROM transactions WHERE state = ? AND receipt_json IS NOT NULL",
            (str(TransactionState.DELIVERED),),
        ).fetchall()
        hashes = [sha256_bytes(str(row["receipt_json"]).encode("utf-8")) for row in rows]
        return merkle_root(hashes)

    def tamper_event_for_test(self, sequence: int, payload_json: str) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE events SET payload_json = ? WHERE sequence = ?",
                (payload_json, sequence),
            )

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for key in (
            "metadata_json", "provider_object_json", "projection_json",
            "scan_report_json", "receipt_json", "signature_json",
        ):
            value = result.pop(key, None)
            result[key.removesuffix("_json")] = json.loads(value) if value else None
        result["state"] = TransactionState(str(result["state"]))
        if result.get("resume_state"):
            result["resume_state"] = TransactionState(str(result["resume_state"]))
        return result

    @staticmethod
    def _event_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result
