"""Incremental transactional persistence for the Omega completion control plane.

The store keeps each top-level control record in its own SQLite row, appends
hash-chained events, reserves idempotency keys transactionally, and exposes a
durable admission outbox.  It never modifies a legacy ``control-state.json``
during migration.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Mapping, Sequence


SCHEMA_VERSION = 2
STATE_COLLECTIONS = (
    "missions",
    "tasks",
    "workers",
    "leases",
    "fences",
    "dispatch_counts",
    "effects",
    "permits",
    "certificates",
)


class TransactionStoreError(RuntimeError):
    """Base persistence error."""


class StateRevisionConflict(TransactionStoreError):
    """The caller attempted to commit from a stale control-state revision."""


class IdempotencyReservationConflict(TransactionStoreError):
    """An idempotency key or task key is already bound differently."""


class LegacyMigrationError(TransactionStoreError):
    """A legacy snapshot could not be imported without uncertainty."""


class InjectedStorageFault(TransactionStoreError):
    """Deterministic failure used only by failure-first courts."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CommitReceipt:
    revision_before: int
    revision_after: int
    rows_upserted: int
    rows_deleted: int
    events_appended: int
    logical_changed_bytes: int
    reservations_added: int
    outbox_added: int
    transition_outbox_added: int


class SQLiteStateStore:
    """SQLite WAL store with optimistic revisions and single-writer commits."""

    def __init__(self, path: str | Path, *, timeout_seconds: float = 5.0) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds
        self.last_commit: CommitReceipt | None = None
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=self.timeout_seconds,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute(f"PRAGMA busy_timeout={max(1, int(self.timeout_seconds * 1000))}")
        return connection

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            mode = str(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
            if mode != "wal":
                raise TransactionStoreError(f"WAL_MODE_UNAVAILABLE:{mode}")
            connection.execute("PRAGMA synchronous=FULL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS state_rows (
                    collection TEXT NOT NULL,
                    row_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (collection, row_key)
                );
                CREATE INDEX IF NOT EXISTS state_rows_collection
                    ON state_rows(collection);
                CREATE TABLE IF NOT EXISTS control_events (
                    seq INTEGER PRIMARY KEY,
                    event_hash TEXT NOT NULL UNIQUE,
                    previous_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS idempotency_reservations (
                    idempotency_key TEXT PRIMARY KEY,
                    task_key TEXT NOT NULL UNIQUE,
                    mission_id TEXT NOT NULL,
                    mission_version INTEGER NOT NULL CHECK (mission_version > 0),
                    reserved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS admission_outbox (
                    outbox_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    mission_version INTEGER NOT NULL CHECK (mission_version > 0),
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('PENDING','APPLYING','APPLIED','FAILED')),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    claim_token TEXT,
                    claimed_at TEXT,
                    applied_at TEXT
                );
                CREATE INDEX IF NOT EXISTS admission_outbox_status
                    ON admission_outbox(status, created_at, outbox_id);
                CREATE TABLE IF NOT EXISTS transition_outbox (
                    transition_id TEXT PRIMARY KEY,
                    transition_kind TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    mission_version INTEGER NOT NULL CHECK (mission_version > 0),
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('PENDING','APPLYING','APPLIED','FAILED')),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    claim_token TEXT,
                    claimed_at TEXT,
                    applied_at TEXT
                );
                CREATE INDEX IF NOT EXISTS transition_outbox_status
                    ON transition_outbox(status, created_at, transition_id);
                CREATE TABLE IF NOT EXISTS legacy_migrations (
                    source_sha256 TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    source_bytes INTEGER NOT NULL CHECK (source_bytes >= 0),
                    imported_rows INTEGER NOT NULL CHECK (imported_rows >= 0),
                    imported_events INTEGER NOT NULL CHECK (imported_events >= 0),
                    imported_at TEXT NOT NULL
                );
                """
            )
            connection.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
            connection.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES('revision','0')")
            observed = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if observed == 0:
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                observed = SCHEMA_VERSION
            elif observed == 1:
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                observed = SCHEMA_VERSION
            if observed != SCHEMA_VERSION:
                raise TransactionStoreError(f"UNSUPPORTED_SCHEMA_VERSION:{observed}")
            connection.execute("UPDATE metadata SET value=? WHERE key='schema_version'", (str(SCHEMA_VERSION),))
        finally:
            connection.close()

    @contextmanager
    def _write_transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _revision(connection: sqlite3.Connection) -> int:
        row = connection.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()
        return int(row[0]) if row else 0

    def current_revision(self) -> int:
        connection = self._connect()
        try:
            return self._revision(connection)
        finally:
            connection.close()

    def load(self, blank: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
        state: dict[str, Any] = {}
        for key, value in blank.items():
            state[key] = [] if isinstance(value, list) else {}
        connection = self._connect()
        try:
            for row in connection.execute(
                "SELECT collection,row_key,payload_json FROM state_rows ORDER BY collection,row_key"
            ):
                collection = str(row["collection"])
                if collection not in state or not isinstance(state[collection], dict):
                    raise TransactionStoreError(f"UNKNOWN_STATE_COLLECTION:{collection}")
                state[collection][str(row["row_key"])] = json.loads(row["payload_json"])
            state["events"] = [
                json.loads(row["payload_json"])
                for row in connection.execute("SELECT payload_json FROM control_events ORDER BY seq")
            ]
            return state, self._revision(connection)
        finally:
            connection.close()

    @staticmethod
    def _desired_rows(state: Mapping[str, Any]) -> dict[tuple[str, str], tuple[str, str]]:
        desired: dict[tuple[str, str], tuple[str, str]] = {}
        for collection in STATE_COLLECTIONS:
            rows = state.get(collection) or {}
            if not isinstance(rows, Mapping):
                raise TransactionStoreError(f"STATE_COLLECTION_NOT_MAPPING:{collection}")
            for row_key, payload in rows.items():
                encoded = canonical_json(payload)
                desired[(collection, str(row_key))] = (
                    encoded,
                    hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                )
        return desired

    def _sync_state(self, connection: sqlite3.Connection, state: Mapping[str, Any]) -> tuple[int, int, int, int]:
        existing = {
            (str(row["collection"]), str(row["row_key"])): str(row["payload_sha256"])
            for row in connection.execute("SELECT collection,row_key,payload_sha256 FROM state_rows")
        }
        desired = self._desired_rows(state)
        upserts = 0
        deletes = 0
        changed_bytes = 0
        now = utc_now()
        for identity, (encoded, row_hash) in desired.items():
            if existing.get(identity) == row_hash:
                continue
            connection.execute(
                """INSERT INTO state_rows(collection,row_key,payload_json,payload_sha256,updated_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(collection,row_key) DO UPDATE SET
                     payload_json=excluded.payload_json,
                     payload_sha256=excluded.payload_sha256,
                     updated_at=excluded.updated_at""",
                (identity[0], identity[1], encoded, row_hash, now),
            )
            upserts += 1
            changed_bytes += len(encoded.encode("utf-8"))
        for identity in sorted(set(existing) - set(desired)):
            connection.execute(
                "DELETE FROM state_rows WHERE collection=? AND row_key=?",
                identity,
            )
            deletes += 1

        events = state.get("events") or []
        if not isinstance(events, list):
            raise TransactionStoreError("EVENTS_NOT_LIST")
        stored = list(connection.execute("SELECT seq,event_hash FROM control_events ORDER BY seq"))
        if len(stored) > len(events):
            raise TransactionStoreError("EVENT_HISTORY_TRUNCATION_PROHIBITED")
        for index, row in enumerate(stored):
            if str(events[index].get("hash")) != str(row["event_hash"]):
                raise TransactionStoreError(f"EVENT_HISTORY_DIVERGENCE:{index + 1}")
        appended = 0
        for index in range(len(stored), len(events)):
            event = events[index]
            event_hash = str(event.get("hash") or "")
            previous_hash = str(event.get("previous") or "")
            if not event_hash or canonical_digest({k: v for k, v in event.items() if k != "hash"}) != event_hash:
                raise TransactionStoreError(f"EVENT_HASH_INVALID:{index + 1}")
            expected_previous = "GENESIS" if index == 0 else str(events[index - 1]["hash"])
            if previous_hash != expected_previous:
                raise TransactionStoreError(f"EVENT_PREVIOUS_HASH_INVALID:{index + 1}")
            encoded = canonical_json(event)
            connection.execute(
                "INSERT INTO control_events(seq,event_hash,previous_hash,payload_json,recorded_at) VALUES(?,?,?,?,?)",
                (index + 1, event_hash, previous_hash, encoded, str(event.get("at") or utc_now())),
            )
            appended += 1
            changed_bytes += len(encoded.encode("utf-8"))
        return upserts, deletes, appended, changed_bytes

    @staticmethod
    def _reserve(
        connection: sqlite3.Connection,
        reservations: Sequence[Mapping[str, Any]],
    ) -> int:
        added = 0
        for reservation in reservations:
            key = str(reservation["idempotency_key"])
            task_key = str(reservation["task_key"])
            existing = connection.execute(
                "SELECT task_key,mission_id,mission_version FROM idempotency_reservations WHERE idempotency_key=?",
                (key,),
            ).fetchone()
            if existing:
                if (
                    str(existing["task_key"]) != task_key
                    or str(existing["mission_id"]) != str(reservation["mission_id"])
                    or int(existing["mission_version"]) != int(reservation["mission_version"])
                ):
                    raise IdempotencyReservationConflict("IDEMPOTENCY_KEY_CONFLICT")
                continue
            task_existing = connection.execute(
                "SELECT idempotency_key FROM idempotency_reservations WHERE task_key=?",
                (task_key,),
            ).fetchone()
            if task_existing and str(task_existing["idempotency_key"]) != key:
                raise IdempotencyReservationConflict("TASK_KEY_RESERVATION_CONFLICT")
            connection.execute(
                """INSERT INTO idempotency_reservations
                   (idempotency_key,task_key,mission_id,mission_version,reserved_at)
                   VALUES(?,?,?,?,?)""",
                (key, task_key, str(reservation["mission_id"]), int(reservation["mission_version"]), utc_now()),
            )
            added += 1
        return added

    @staticmethod
    def _enqueue_outbox(connection: sqlite3.Connection, outbox: Mapping[str, Any] | None) -> int:
        if not outbox:
            return 0
        outbox_id = str(outbox["outbox_id"])
        payload = outbox["payload"]
        encoded = canonical_json(payload)
        payload_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        existing = connection.execute(
            "SELECT payload_sha256 FROM admission_outbox WHERE outbox_id=?",
            (outbox_id,),
        ).fetchone()
        if existing:
            if str(existing["payload_sha256"]) != payload_hash:
                raise TransactionStoreError("OUTBOX_ID_CONFLICT")
            return 0
        connection.execute(
            """INSERT INTO admission_outbox
               (outbox_id,mission_id,mission_version,payload_json,payload_sha256,status,attempts,created_at)
               VALUES(?,?,?,?,?,'PENDING',0,?)""",
            (
                outbox_id,
                str(outbox["mission_id"]),
                int(outbox["mission_version"]),
                encoded,
                payload_hash,
                utc_now(),
            ),
        )
        return 1

    @staticmethod
    def _enqueue_transition_outbox(
        connection: sqlite3.Connection,
        transition: Mapping[str, Any] | None,
    ) -> int:
        if not transition:
            return 0
        transition_id = str(transition["transition_id"])
        payload = transition["payload"]
        encoded = canonical_json(payload)
        payload_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        existing = connection.execute(
            "SELECT transition_kind,payload_sha256 FROM transition_outbox WHERE transition_id=?",
            (transition_id,),
        ).fetchone()
        if existing:
            if (
                str(existing["transition_kind"]) != str(transition["transition_kind"])
                or str(existing["payload_sha256"]) != payload_hash
            ):
                raise TransactionStoreError("TRANSITION_OUTBOX_ID_CONFLICT")
            return 0
        connection.execute(
            """INSERT INTO transition_outbox
               (transition_id,transition_kind,mission_id,mission_version,payload_json,payload_sha256,status,attempts,created_at)
               VALUES(?,?,?,?,?,?,'PENDING',0,?)""",
            (
                transition_id,
                str(transition["transition_kind"]),
                str(transition["mission_id"]),
                int(transition["mission_version"]),
                encoded,
                payload_hash,
                utc_now(),
            ),
        )
        return 1

    def commit(
        self,
        state: Mapping[str, Any],
        *,
        expected_revision: int,
        reservations: Sequence[Mapping[str, Any]] = (),
        outbox: Mapping[str, Any] | None = None,
        transition_outbox: Mapping[str, Any] | None = None,
        applied_transition: Mapping[str, Any] | None = None,
        fault_at: str | None = None,
    ) -> CommitReceipt:
        with self._write_transaction() as connection:
            current = self._revision(connection)
            if current != expected_revision:
                raise StateRevisionConflict(f"STATE_REVISION_CONFLICT:{expected_revision}:{current}")
            reservations_added = self._reserve(connection, reservations)
            outbox_added = self._enqueue_outbox(connection, outbox)
            transition_outbox_added = self._enqueue_transition_outbox(connection, transition_outbox)
            upserts, deletes, appended, changed_bytes = self._sync_state(connection, state)
            if applied_transition is not None:
                self._mark_transition_applied_in_transaction(
                    connection,
                    str(applied_transition["transition_id"]),
                    str(applied_transition["claim_token"]),
                )
            next_revision = current + 1
            connection.execute(
                "UPDATE metadata SET value=? WHERE key='revision'",
                (str(next_revision),),
            )
            if fault_at == "before_commit":
                raise InjectedStorageFault("INJECTED_BEFORE_COMMIT")
        receipt = CommitReceipt(
            current,
            next_revision,
            upserts,
            deletes,
            appended,
            changed_bytes,
            reservations_added,
            outbox_added,
            transition_outbox_added,
        )
        self.last_commit = receipt
        return receipt

    def migrate_legacy(self, legacy_path: str | Path, blank: Mapping[str, Any], *, fault_at: str | None = None) -> dict[str, Any] | None:
        path = Path(legacy_path)
        if not path.exists():
            return None
        source_bytes = path.read_bytes()
        source_hash = hashlib.sha256(source_bytes).hexdigest()
        try:
            loaded = json.loads(source_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LegacyMigrationError("LEGACY_JSON_INVALID") from exc
        if not isinstance(loaded, dict):
            raise LegacyMigrationError("LEGACY_STATE_NOT_OBJECT")
        state: dict[str, Any] = {}
        for key, value in blank.items():
            state[key] = loaded.get(key, [] if isinstance(value, list) else {})
        if not isinstance(state.get("events"), list):
            raise LegacyMigrationError("LEGACY_EVENTS_NOT_LIST")

        with self._write_transaction() as connection:
            populated = connection.execute("SELECT 1 FROM state_rows LIMIT 1").fetchone()
            has_events = connection.execute("SELECT 1 FROM control_events LIMIT 1").fetchone()
            if populated or has_events or self._revision(connection) > 0:
                return None
            existing = connection.execute(
                "SELECT source_sha256 FROM legacy_migrations WHERE source_sha256=?",
                (source_hash,),
            ).fetchone()
            if existing:
                return None
            try:
                upserts, _, appended, _ = self._sync_state(connection, state)
            except TransactionStoreError as exc:
                raise LegacyMigrationError(str(exc)) from exc
            reservations = []
            for task_key, task_row in (state.get("tasks") or {}).items():
                spec = task_row.get("spec") or {}
                reservations.append(
                    {
                        "idempotency_key": spec.get("idempotency_key") or task_key,
                        "task_key": task_key,
                        "mission_id": spec.get("mission_id"),
                        "mission_version": int(str(task_key).split(":v", 1)[1].split(":", 1)[0]),
                    }
                )
            self._reserve(connection, reservations)
            connection.execute(
                """INSERT INTO legacy_migrations
                   (source_sha256,source_path,source_bytes,imported_rows,imported_events,imported_at)
                   VALUES(?,?,?,?,?,?)""",
                (source_hash, str(path.resolve()), len(source_bytes), upserts, appended, utc_now()),
            )
            connection.execute("UPDATE metadata SET value='1' WHERE key='revision'")
            if fault_at == "before_commit":
                raise InjectedStorageFault("INJECTED_MIGRATION_BEFORE_COMMIT")
        return {
            "source_sha256": source_hash,
            "source_path": str(path.resolve()),
            "source_bytes": len(source_bytes),
            "imported_rows": upserts,
            "imported_events": appended,
        }

    def pending_outbox(self) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            return [
                {
                    "outbox_id": str(row["outbox_id"]),
                    "mission_id": str(row["mission_id"]),
                    "mission_version": int(row["mission_version"]),
                    "payload": json.loads(row["payload_json"]),
                    "attempts": int(row["attempts"]),
                    "status": str(row["status"]),
                    "claim_token": row["claim_token"],
                    "claimed_at": row["claimed_at"],
                }
                for row in connection.execute(
                    "SELECT * FROM admission_outbox WHERE status!='APPLIED' ORDER BY created_at,outbox_id"
                )
            ]
        finally:
            connection.close()

    def claim_outbox(self, claim_token: str) -> dict[str, Any] | None:
        if not claim_token.strip():
            raise ValueError("CLAIM_TOKEN_REQUIRED")
        with self._write_transaction() as connection:
            row = connection.execute(
                "SELECT * FROM admission_outbox WHERE status IN ('PENDING','FAILED') ORDER BY created_at,outbox_id LIMIT 1"
            ).fetchone()
            if not row:
                return None
            changed = connection.execute(
                """UPDATE admission_outbox
                   SET status='APPLYING',claim_token=?,claimed_at=?,last_error=NULL
                   WHERE outbox_id=? AND status IN ('PENDING','FAILED')""",
                (claim_token, utc_now(), row["outbox_id"]),
            ).rowcount
            if changed != 1:
                return None
            return {
                "outbox_id": str(row["outbox_id"]),
                "mission_id": str(row["mission_id"]),
                "mission_version": int(row["mission_version"]),
                "payload": json.loads(row["payload_json"]),
                "attempts": int(row["attempts"]),
                "claim_token": claim_token,
            }

    def recover_stale_outbox(self, *, max_age_seconds: int = 30, as_of: str | None = None) -> tuple[str, ...]:
        point = datetime.fromisoformat(as_of.replace("Z", "+00:00")) if as_of else datetime.now(timezone.utc)
        if point.tzinfo is None:
            point = point.replace(tzinfo=timezone.utc)
        threshold = point.astimezone(timezone.utc) - timedelta(seconds=max(0, max_age_seconds))
        recovered: list[str] = []
        with self._write_transaction() as connection:
            for row in connection.execute("SELECT outbox_id,claimed_at FROM admission_outbox WHERE status='APPLYING'"):
                claimed_at = str(row["claimed_at"] or "")
                if not claimed_at:
                    stale = True
                else:
                    observed = datetime.fromisoformat(claimed_at.replace("Z", "+00:00"))
                    if observed.tzinfo is None:
                        observed = observed.replace(tzinfo=timezone.utc)
                    stale = observed.astimezone(timezone.utc) <= threshold
                if stale:
                    connection.execute(
                        """UPDATE admission_outbox
                           SET status='FAILED',claim_token=NULL,claimed_at=NULL,last_error='STALE_OUTBOX_CLAIM_RECOVERED'
                           WHERE outbox_id=? AND status='APPLYING'""",
                        (row["outbox_id"],),
                    )
                    recovered.append(str(row["outbox_id"]))
        return tuple(recovered)

    def mark_outbox_applied(self, outbox_id: str, claim_token: str) -> None:
        with self._write_transaction() as connection:
            changed = connection.execute(
                """UPDATE admission_outbox
                   SET status='APPLIED',attempts=attempts+1,last_error=NULL,applied_at=?,claim_token=NULL,claimed_at=NULL
                   WHERE outbox_id=? AND status='APPLYING' AND claim_token=?""",
                (utc_now(), outbox_id, claim_token),
            ).rowcount
            if changed != 1:
                row = connection.execute(
                    "SELECT status FROM admission_outbox WHERE outbox_id=?",
                    (outbox_id,),
                ).fetchone()
                if not row or str(row["status"]) != "APPLIED":
                    raise TransactionStoreError("OUTBOX_APPLY_TARGET_MISSING")

    def mark_outbox_failed(self, outbox_id: str, claim_token: str, error: str) -> None:
        with self._write_transaction() as connection:
            changed = connection.execute(
                """UPDATE admission_outbox
                   SET status='FAILED',attempts=attempts+1,last_error=?,claim_token=NULL,claimed_at=NULL
                   WHERE outbox_id=? AND status='APPLYING' AND claim_token=?""",
                (error[:1000], outbox_id, claim_token),
            ).rowcount
            if changed != 1:
                raise TransactionStoreError("OUTBOX_FAILURE_TARGET_MISSING")

    def pending_transitions(self) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            return [
                {
                    "transition_id": str(row["transition_id"]),
                    "transition_kind": str(row["transition_kind"]),
                    "mission_id": str(row["mission_id"]),
                    "mission_version": int(row["mission_version"]),
                    "payload": json.loads(row["payload_json"]),
                    "attempts": int(row["attempts"]),
                    "status": str(row["status"]),
                    "claim_token": row["claim_token"],
                    "claimed_at": row["claimed_at"],
                }
                for row in connection.execute(
                    "SELECT * FROM transition_outbox WHERE status!='APPLIED' ORDER BY created_at,transition_id"
                )
            ]
        finally:
            connection.close()

    def claim_transition(self, claim_token: str) -> dict[str, Any] | None:
        if not claim_token.strip():
            raise ValueError("CLAIM_TOKEN_REQUIRED")
        with self._write_transaction() as connection:
            row = connection.execute(
                "SELECT * FROM transition_outbox WHERE status IN ('PENDING','FAILED') ORDER BY created_at,transition_id LIMIT 1"
            ).fetchone()
            if not row:
                return None
            changed = connection.execute(
                """UPDATE transition_outbox
                   SET status='APPLYING',claim_token=?,claimed_at=?,last_error=NULL
                   WHERE transition_id=? AND status IN ('PENDING','FAILED')""",
                (claim_token, utc_now(), row["transition_id"]),
            ).rowcount
            if changed != 1:
                return None
            return {
                "transition_id": str(row["transition_id"]),
                "transition_kind": str(row["transition_kind"]),
                "mission_id": str(row["mission_id"]),
                "mission_version": int(row["mission_version"]),
                "payload": json.loads(row["payload_json"]),
                "attempts": int(row["attempts"]),
                "claim_token": claim_token,
            }

    def recover_stale_transitions(self, *, max_age_seconds: int = 30, as_of: str | None = None) -> tuple[str, ...]:
        point = datetime.fromisoformat(as_of.replace("Z", "+00:00")) if as_of else datetime.now(timezone.utc)
        if point.tzinfo is None:
            point = point.replace(tzinfo=timezone.utc)
        threshold = point.astimezone(timezone.utc) - timedelta(seconds=max(0, max_age_seconds))
        recovered: list[str] = []
        with self._write_transaction() as connection:
            for row in connection.execute("SELECT transition_id,claimed_at FROM transition_outbox WHERE status='APPLYING'"):
                claimed_at = str(row["claimed_at"] or "")
                observed = datetime.fromisoformat(claimed_at.replace("Z", "+00:00")) if claimed_at else None
                if observed is not None and observed.tzinfo is None:
                    observed = observed.replace(tzinfo=timezone.utc)
                if observed is None or observed.astimezone(timezone.utc) <= threshold:
                    connection.execute(
                        """UPDATE transition_outbox
                           SET status='FAILED',claim_token=NULL,claimed_at=NULL,last_error='STALE_TRANSITION_CLAIM_RECOVERED'
                           WHERE transition_id=? AND status='APPLYING'""",
                        (row["transition_id"],),
                    )
                    recovered.append(str(row["transition_id"]))
        return tuple(recovered)

    def mark_transition_applied(self, transition_id: str, claim_token: str) -> None:
        with self._write_transaction() as connection:
            self._mark_transition_applied_in_transaction(connection, transition_id, claim_token)

    @staticmethod
    def _mark_transition_applied_in_transaction(
        connection: sqlite3.Connection,
        transition_id: str,
        claim_token: str,
    ) -> None:
        """Fence and acknowledge a claimed transition inside its caller's transaction."""
        changed = connection.execute(
            """UPDATE transition_outbox
               SET status='APPLIED',attempts=attempts+1,last_error=NULL,applied_at=?,claim_token=NULL,claimed_at=NULL
               WHERE transition_id=? AND status='APPLYING' AND claim_token=?""",
            (utc_now(), transition_id, claim_token),
        ).rowcount
        if changed != 1:
            row = connection.execute(
                "SELECT status FROM transition_outbox WHERE transition_id=?",
                (transition_id,),
            ).fetchone()
            if not row or str(row["status"]) != "APPLIED":
                raise TransactionStoreError("TRANSITION_APPLY_TARGET_MISSING")

    def mark_transition_failed(self, transition_id: str, claim_token: str, error: str) -> None:
        with self._write_transaction() as connection:
            changed = connection.execute(
                """UPDATE transition_outbox
                   SET status='FAILED',attempts=attempts+1,last_error=?,claim_token=NULL,claimed_at=NULL
                   WHERE transition_id=? AND status='APPLYING' AND claim_token=?""",
                (error[:1000], transition_id, claim_token),
            ).rowcount
            if changed != 1:
                raise TransactionStoreError("TRANSITION_FAILURE_TARGET_MISSING")

    def reservation(self, idempotency_key: str) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM idempotency_reservations WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def backup_to(self, destination: str | Path) -> dict[str, Any]:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        source = self._connect()
        destination_connection = sqlite3.connect(target)
        try:
            source.execute("PRAGMA wal_checkpoint(FULL)")
            source.backup(destination_connection)
            destination_connection.commit()
        finally:
            destination_connection.close()
            source.close()
        backup = SQLiteStateStore(target, timeout_seconds=self.timeout_seconds)
        if not backup.verify_integrity():
            raise TransactionStoreError("BACKUP_INTEGRITY_FAILED")
        return {"path": str(target), "bytes": target.stat().st_size, "integrity_valid": True}

    def verify_integrity(self) -> bool:
        connection = self._connect()
        try:
            if str(connection.execute("PRAGMA integrity_check").fetchone()[0]).lower() != "ok":
                return False
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                return False
            for row in connection.execute("SELECT payload_json,payload_sha256 FROM state_rows"):
                observed = hashlib.sha256(str(row["payload_json"]).encode("utf-8")).hexdigest()
                if observed != str(row["payload_sha256"]):
                    return False
            previous = "GENESIS"
            for row in connection.execute("SELECT seq,event_hash,previous_hash,payload_json FROM control_events ORDER BY seq"):
                event = json.loads(row["payload_json"])
                if int(row["seq"]) < 1 or str(row["previous_hash"]) != previous:
                    return False
                event_hash = str(row["event_hash"])
                if str(event.get("hash")) != event_hash:
                    return False
                if canonical_digest({k: v for k, v in event.items() if k != "hash"}) != event_hash:
                    return False
                previous = event_hash
            return True
        except (json.JSONDecodeError, sqlite3.DatabaseError, ValueError):
            return False
        finally:
            connection.close()

    def status(self) -> dict[str, Any]:
        connection = self._connect()
        try:
            journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).upper()
            rows = int(connection.execute("SELECT COUNT(*) FROM state_rows").fetchone()[0])
            events = int(connection.execute("SELECT COUNT(*) FROM control_events").fetchone()[0])
            pending_admission = int(connection.execute("SELECT COUNT(*) FROM admission_outbox WHERE status!='APPLIED'").fetchone()[0])
            pending_transitions = int(connection.execute("SELECT COUNT(*) FROM transition_outbox WHERE status!='APPLIED'").fetchone()[0])
            migrations = [dict(row) for row in connection.execute("SELECT * FROM legacy_migrations ORDER BY imported_at")]
            return {
                "backend": "SQLITE_WAL_INCREMENTAL",
                "schema_version": int(connection.execute("PRAGMA user_version").fetchone()[0]),
                "journal_mode": journal_mode,
                "revision": self._revision(connection),
                "state_rows": rows,
                "events": events,
                "pending_outbox": pending_admission + pending_transitions,
                "pending_admission_outbox": pending_admission,
                "pending_transition_outbox": pending_transitions,
                "migrations": migrations,
                "last_commit": asdict(self.last_commit) if self.last_commit else None,
                "integrity_valid": self.verify_integrity(),
            }
        finally:
            connection.close()
