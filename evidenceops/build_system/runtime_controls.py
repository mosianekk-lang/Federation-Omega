#!/usr/bin/env python3
"""Runtime-bound continuity controls for the existing CFRE Omega package.

These controls are local and provider-disabled by default.  They do not claim
control over ChatGPT, a browser, a network, or a third-party provider.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from typing import Any, Callable, Iterable


SYSTEM_IDENTITY = "CFRE-OMEGA"
ORPHANED_UNACKNOWLEDGED = "ORPHANED_UNACKNOWLEDGED"
ACKNOWLEDGED = "ACKNOWLEDGED"


class RuntimeControlError(RuntimeError):
    """Base exception for fail-closed runtime-control decisions."""


class CooperativeCancellation(RuntimeControlError):
    """Raised at a cooperative checkpoint after cancellation is requested."""


class NoSafeRoute(RuntimeControlError):
    """Raised when no distinct, authorized route remains."""


class IntegrityError(RuntimeControlError):
    """Raised when durable state fails exact readback verification."""


class PolicyDenied(RuntimeControlError):
    """Raised when an action exceeds the local runtime policy."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canonical_json(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    return connection


@dataclass(frozen=True)
class Heartbeat:
    identity: str
    sequence: int
    monotonic_time: float
    emitted_at: str


class HeartbeatScheduler:
    """Emit heartbeats on a real non-daemon thread until explicitly stopped."""

    def __init__(
        self,
        interval_seconds: float,
        callback: Callable[[Heartbeat], None],
        *,
        identity: str = SYSTEM_IDENTITY,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.interval_seconds = float(interval_seconds)
        self.callback = callback
        self.identity = identity
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._sequence = 0
        self._callback_error: BaseException | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def callback_error(self) -> BaseException | None:
        return self._callback_error

    def start(self) -> None:
        with self._lock:
            if self.is_running:
                return
            self._stop.clear()
            self._callback_error = None
            self._thread = threading.Thread(
                target=self._run,
                name=f"{self.identity}-heartbeat",
                daemon=False,
            )
            self._thread.start()

    def _run(self) -> None:
        deadline = time.monotonic() + self.interval_seconds
        while not self._stop.is_set():
            remaining = max(0.0, deadline - time.monotonic())
            if self._stop.wait(remaining):
                break
            self._sequence += 1
            heartbeat = Heartbeat(
                identity=self.identity,
                sequence=self._sequence,
                monotonic_time=time.monotonic(),
                emitted_at=_utc_now(),
            )
            try:
                self.callback(heartbeat)
            except BaseException as exc:  # fail visibly without killing stop/join
                self._callback_error = exc
                self._stop.set()
                break
            deadline += self.interval_seconds

    def stop(self, timeout: float = 2.0) -> bool:
        self._stop.set()
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()


class CancellationToken:
    """A shared cooperative cancellation token persisted in SQLite."""

    def __init__(self, database: str | Path, mission_id: str) -> None:
        if not mission_id:
            raise ValueError("mission_id is required")
        self.database = Path(database)
        self.mission_id = mission_id
        with _connect(self.database) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS cancellation ("
                "mission_id TEXT PRIMARY KEY, cancelled INTEGER NOT NULL, "
                "reason TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO cancellation VALUES (?, 0, '', ?)",
                (self.mission_id, _utc_now()),
            )

    def cancel(self, reason: str) -> None:
        if not reason.strip():
            raise ValueError("cancellation reason is required")
        with _connect(self.database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE cancellation SET cancelled=1, reason=?, updated_at=? "
                "WHERE mission_id=?",
                (reason, _utc_now(), self.mission_id),
            )
            connection.commit()

    def state(self) -> dict[str, Any]:
        with _connect(self.database) as connection:
            row = connection.execute(
                "SELECT cancelled, reason, updated_at FROM cancellation WHERE mission_id=?",
                (self.mission_id,),
            ).fetchone()
        if row is None:
            raise IntegrityError("cancellation state disappeared")
        return {"cancelled": bool(row[0]), "reason": row[1], "updated_at": row[2]}

    def checkpoint(self) -> None:
        state = self.state()
        if state["cancelled"]:
            raise CooperativeCancellation(state["reason"])


@dataclass(frozen=True)
class Route:
    route_id: str
    priority: int
    authorized: bool = True
    provider_effect: bool = False


class DistinctRouteCircuit:
    """Persist circuit state and choose a different authorized route."""

    def __init__(self, database: str | Path, routes: Iterable[Route]) -> None:
        self.database = Path(database)
        supplied = tuple(routes)
        if not supplied:
            raise ValueError("at least one route is required")
        with _connect(self.database) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS routes ("
                "route_id TEXT PRIMARY KEY, priority INTEGER NOT NULL, "
                "authorized INTEGER NOT NULL, provider_effect INTEGER NOT NULL, "
                "circuit_open INTEGER NOT NULL DEFAULT 0, fingerprint TEXT NOT NULL DEFAULT '')"
            )
            connection.execute("BEGIN IMMEDIATE")
            for route in supplied:
                connection.execute(
                    "INSERT INTO routes(route_id, priority, authorized, provider_effect) "
                    "VALUES (?, ?, ?, ?) ON CONFLICT(route_id) DO UPDATE SET "
                    "priority=excluded.priority, authorized=excluded.authorized, "
                    "provider_effect=excluded.provider_effect",
                    (route.route_id, route.priority, int(route.authorized), int(route.provider_effect)),
                )
            connection.commit()

    def open(self, route_id: str, fingerprint: str) -> None:
        if not fingerprint:
            raise ValueError("failure fingerprint is required")
        with _connect(self.database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                "UPDATE routes SET circuit_open=1, fingerprint=? WHERE route_id=?",
                (fingerprint, route_id),
            ).rowcount
            if updated != 1:
                connection.rollback()
                raise NoSafeRoute(f"unknown route: {route_id}")
            connection.commit()

    def select_distinct(self, failed_route_id: str, *, providers_enabled: bool = False) -> Route:
        with _connect(self.database) as connection:
            rows = connection.execute(
                "SELECT route_id, priority, authorized, provider_effect FROM routes "
                "WHERE route_id<>? AND circuit_open=0 AND authorized=1 "
                "ORDER BY priority DESC, route_id ASC",
                (failed_route_id,),
            ).fetchall()
        for row in rows:
            route = Route(row[0], row[1], bool(row[2]), bool(row[3]))
            if route.provider_effect and not providers_enabled:
                continue
            return route
        raise NoSafeRoute("no distinct authorized route remains")


class HandoffStore:
    """Persist a hash-bound handoff with atomic replace and exact readback."""

    def __init__(self, path: str | Path, *, identity: str = SYSTEM_IDENTITY) -> None:
        self.path = Path(path)
        self.identity = identity

    def write(self, transaction_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not transaction_id:
            raise ValueError("transaction_id is required")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "schema": "CFRE-OMEGA-HANDOFF-1",
            "identity": self.identity,
            "transaction_id": transaction_id,
            "payload": payload,
            "payload_sha256": _sha256(payload),
            "written_at": _utc_now(),
        }
        envelope["envelope_sha256"] = _sha256(envelope)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.path.parent, delete=False
        ) as handle:
            json.dump(envelope, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, self.path)
        readback = self.read(transaction_id)
        if readback != payload:
            raise IntegrityError("handoff readback mismatch")
        return envelope

    def read(self, transaction_id: str | None = None) -> dict[str, Any]:
        envelope = json.loads(self.path.read_text(encoding="utf-8"))
        observed_envelope_sha = envelope.pop("envelope_sha256", None)
        if observed_envelope_sha != _sha256(envelope):
            raise IntegrityError("handoff envelope hash mismatch")
        if envelope.get("identity") != self.identity:
            raise IntegrityError("handoff identity mismatch")
        if transaction_id is not None and envelope.get("transaction_id") != transaction_id:
            raise IntegrityError("handoff transaction mismatch")
        payload = envelope.get("payload")
        if envelope.get("payload_sha256") != _sha256(payload):
            raise IntegrityError("handoff payload hash mismatch")
        return payload


class DeliveryJournal:
    """Journal artifact and acknowledgement under one transaction identity."""

    def __init__(self, database: str | Path, *, identity: str = SYSTEM_IDENTITY) -> None:
        self.database = Path(database)
        self.identity = identity
        with _connect(self.database) as connection:
            connection.executescript(
                "CREATE TABLE IF NOT EXISTS deliveries ("
                "transaction_id TEXT PRIMARY KEY, identity TEXT NOT NULL, "
                "artifact_id TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, "
                "acknowledgement TEXT, state TEXT NOT NULL, updated_at TEXT NOT NULL);"
                "CREATE TABLE IF NOT EXISTS events ("
                "sequence INTEGER PRIMARY KEY AUTOINCREMENT, transaction_id TEXT NOT NULL, "
                "event_kind TEXT NOT NULL, payload_json TEXT NOT NULL, "
                "previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL);"
            )

    def _append_event(
        self,
        connection: sqlite3.Connection,
        transaction_id: str,
        event_kind: str,
        payload: dict[str, Any],
    ) -> str:
        row = connection.execute(
            "SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous = row[0] if row else "GENESIS"
        body = {
            "identity": self.identity,
            "transaction_id": transaction_id,
            "event_kind": event_kind,
            "payload": payload,
            "previous_hash": previous,
        }
        event_hash = _sha256(body)
        connection.execute(
            "INSERT INTO events(transaction_id, event_kind, payload_json, previous_hash, event_hash) "
            "VALUES (?, ?, ?, ?, ?)",
            (transaction_id, event_kind, _canonical_json(payload), previous, event_hash),
        )
        return event_hash

    def deliver(
        self,
        transaction_id: str,
        artifact_id: str,
        artifact_sha256: str,
        *,
        acknowledgement: str | None,
    ) -> dict[str, Any]:
        if not transaction_id or not artifact_id or not artifact_sha256:
            raise ValueError("transaction_id, artifact_id and artifact_sha256 are required")
        state = ACKNOWLEDGED if acknowledgement else ORPHANED_UNACKNOWLEDGED
        with _connect(self.database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT artifact_id, artifact_sha256, acknowledgement, state FROM deliveries "
                "WHERE transaction_id=?",
                (transaction_id,),
            ).fetchone()
            expected = (artifact_id, artifact_sha256, acknowledgement, state)
            if prior is not None and tuple(prior) != expected:
                connection.rollback()
                raise IntegrityError("transaction identity was reused with different delivery content")
            if prior is None:
                connection.execute(
                    "INSERT INTO deliveries VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        transaction_id,
                        self.identity,
                        artifact_id,
                        artifact_sha256,
                        acknowledgement,
                        state,
                        _utc_now(),
                    ),
                )
                self._append_event(
                    connection,
                    transaction_id,
                    "TERMINAL_DELIVERY",
                    {"artifact_id": artifact_id, "artifact_sha256": artifact_sha256, "state": state},
                )
            connection.commit()
        return self.readback(transaction_id)

    def readback(self, transaction_id: str) -> dict[str, Any]:
        with _connect(self.database) as connection:
            row = connection.execute(
                "SELECT transaction_id, identity, artifact_id, artifact_sha256, "
                "acknowledgement, state, updated_at FROM deliveries WHERE transaction_id=?",
                (transaction_id,),
            ).fetchone()
        if row is None:
            raise IntegrityError("delivery transaction not found")
        keys = (
            "transaction_id", "identity", "artifact_id", "artifact_sha256",
            "acknowledgement", "state", "updated_at",
        )
        return dict(zip(keys, row))

    def verify_event_chain(self) -> bool:
        previous = "GENESIS"
        with _connect(self.database) as connection:
            rows = connection.execute(
                "SELECT transaction_id, event_kind, payload_json, previous_hash, event_hash "
                "FROM events ORDER BY sequence ASC"
            ).fetchall()
        for transaction_id, event_kind, payload_json, observed_previous, event_hash in rows:
            if observed_previous != previous:
                return False
            body = {
                "identity": self.identity,
                "transaction_id": transaction_id,
                "event_kind": event_kind,
                "payload": json.loads(payload_json),
                "previous_hash": previous,
            }
            if _sha256(body) != event_hash:
                return False
            previous = event_hash
        return True


@dataclass(frozen=True)
class RuntimePolicy:
    """Fail closed on provider effects and system-identity expansion."""

    identity: str = SYSTEM_IDENTITY
    providers_enabled: bool = False
    allow_new_system_identity: bool = False

    def admit(self, action_kind: str, *, target_identity: str = SYSTEM_IDENTITY) -> None:
        if target_identity != self.identity and not self.allow_new_system_identity:
            raise PolicyDenied("new system identity is not authorized")
        if action_kind.startswith("PROVIDER_") and not self.providers_enabled:
            raise PolicyDenied("provider actions are disabled")


__all__ = [
    "ACKNOWLEDGED",
    "ORPHANED_UNACKNOWLEDGED",
    "SYSTEM_IDENTITY",
    "CancellationToken",
    "CooperativeCancellation",
    "DeliveryJournal",
    "DistinctRouteCircuit",
    "Heartbeat",
    "HeartbeatScheduler",
    "HandoffStore",
    "IntegrityError",
    "NoSafeRoute",
    "PolicyDenied",
    "Route",
    "RuntimePolicy",
]
