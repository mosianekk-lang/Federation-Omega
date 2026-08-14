from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    ContinuationMode,
    GovernanceCapsule,
    ProviderContinuationRef,
    RestoreEnvelope,
    RestorePreviewReason,
)


class NamespaceCollision(RuntimeError):
    pass


class NamespaceNotFound(KeyError):
    pass


def _now() -> float:
    return time.time()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _namespace_key(display: str) -> str:
    value = display.strip()
    if not value:
        raise ValueError("namespace cannot be blank")
    return value.casefold()


def _fingerprint(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


class ChatBridgeStore:
    """SQLite WAL control-plane kernel for ChatBridge Ω4.

    The store is provider-neutral. It persists immutable generations, active namespace
    pointers, governance capsules, provider continuation references and session-bound
    restore leases. External provider execution remains a separate adapter/proof gate.
    """

    def __init__(self, path: str = "chatbridge_omega4.sqlite3") -> None:
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
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def _bootstrap(self) -> None:
        conn = sqlite3.connect(self.path)
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS namespaces(
                namespace_id TEXT PRIMARY KEY,
                namespace_key TEXT NOT NULL UNIQUE,
                namespace_display TEXT NOT NULL,
                owner TEXT NOT NULL,
                status TEXT NOT NULL,
                active_generation_id TEXT,
                project TEXT NOT NULL,
                workstream TEXT NOT NULL,
                adapter TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                lifecycle_state TEXT NOT NULL,
                released_at REAL,
                tombstone_state TEXT NOT NULL,
                scope_lock TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS generations(
                generation_id TEXT PRIMARY KEY,
                namespace_id TEXT NOT NULL REFERENCES namespaces(namespace_id),
                namespace_key_snapshot TEXT NOT NULL,
                namespace_display_snapshot TEXT NOT NULL,
                generation_number INTEGER NOT NULL,
                handoff_id TEXT NOT NULL UNIQUE,
                checkpoint_fingerprint TEXT NOT NULL,
                governance_json TEXT NOT NULL,
                hot_json TEXT NOT NULL,
                warm_json TEXT NOT NULL,
                cold_json TEXT NOT NULL,
                provider_ref_json TEXT NOT NULL,
                parent_generation_id TEXT,
                branch_origin_namespace_id TEXT,
                branch_origin_generation_id TEXT,
                created_at REAL NOT NULL,
                state TEXT NOT NULL,
                supersedes_generation_id TEXT,
                restore_eligible INTEGER NOT NULL,
                UNIQUE(namespace_id, generation_number)
            );

            CREATE TABLE IF NOT EXISTS restore_leases(
                lease_id TEXT PRIMARY KEY,
                namespace_id TEXT NOT NULL REFERENCES namespaces(namespace_id),
                generation_id TEXT NOT NULL REFERENCES generations(generation_id),
                destination_session_key TEXT NOT NULL,
                checkpoint_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                acquired_at REAL NOT NULL,
                last_used_at REAL NOT NULL,
                UNIQUE(namespace_id, generation_id, destination_session_key)
            );

            CREATE TABLE IF NOT EXISTS events(
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                namespace_id TEXT,
                generation_id TEXT,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_generations_namespace
                ON generations(namespace_id, generation_number DESC);
            CREATE INDEX IF NOT EXISTS idx_leases_lookup
                ON restore_leases(namespace_id, generation_id, destination_session_key);
            """
        )
        conn.close()

    def _event(self, conn: sqlite3.Connection, event_type: str, namespace_id: str, generation_id: str, payload: Any) -> None:
        conn.execute(
            "INSERT INTO events VALUES(?,?,?,?,?,?)",
            (f"evt_{uuid.uuid4().hex}", event_type, namespace_id, generation_id, _canonical_json(payload), _now()),
        )

    def _namespace_row(self, namespace: str) -> Optional[sqlite3.Row]:
        return self._conn().execute(
            "SELECT * FROM namespaces WHERE namespace_key=?", (_namespace_key(namespace),)
        ).fetchone()

    def _generation_row(self, generation_id: str) -> sqlite3.Row:
        row = self._conn().execute(
            "SELECT * FROM generations WHERE generation_id=?", (generation_id,)
        ).fetchone()
        if not row:
            raise NamespaceNotFound(generation_id)
        return row

    def _scope(self, capsule: GovernanceCapsule) -> Tuple[str, str, str]:
        return (capsule.owner, capsule.project, capsule.workstream)

    def backup(
        self,
        namespace: str,
        capsule: GovernanceCapsule,
        *,
        hot_state: Dict[str, Any],
        warm_pointers: List[str],
        cold_pointers: List[str],
        provider_ref: ProviderContinuationRef = ProviderContinuationRef(),
        branch_origin_namespace_id: str = "",
        branch_origin_generation_id: str = "",
    ) -> Dict[str, Any]:
        display = namespace.strip()
        key = _namespace_key(display)
        material = {
            "owner": capsule.owner,
            "project": capsule.project,
            "workstream": capsule.workstream,
            "adapter": capsule.adapter,
            "governance": capsule.to_dict(),
            "hot": hot_state,
            "warm": warm_pointers,
            "cold": cold_pointers,
            "provider_ref": provider_ref.to_dict(),
            "branch_origin_namespace_id": branch_origin_namespace_id,
            "branch_origin_generation_id": branch_origin_generation_id,
        }
        fingerprint = _fingerprint(material)
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute("SELECT * FROM namespaces WHERE namespace_key=?", (key,)).fetchone()
            if existing:
                existing_scope = (existing["owner"], existing["project"], existing["workstream"])
                if existing_scope != self._scope(capsule):
                    raise NamespaceCollision(
                        f"namespace {display!r} is already bound to a different governed scope"
                    )
                if existing["lifecycle_state"] == "RELEASED":
                    raise NamespaceCollision(
                        f"namespace {display!r} is tombstoned; rename or explicitly create a new namespace"
                    )
                active_id = existing["active_generation_id"]
                if active_id:
                    active = conn.execute("SELECT * FROM generations WHERE generation_id=?", (active_id,)).fetchone()
                    if active and active["checkpoint_fingerprint"] == fingerprint:
                        conn.execute("COMMIT")
                        return {
                            "namespace_id": existing["namespace_id"],
                            "generation_id": active_id,
                            "generation_number": int(active["generation_number"]),
                            "handoff_id": active["handoff_id"],
                            "checkpoint_fingerprint": fingerprint,
                            "reused": True,
                        }
                namespace_id = existing["namespace_id"]
                next_number = int(conn.execute(
                    "SELECT COALESCE(MAX(generation_number),0)+1 AS n FROM generations WHERE namespace_id=?",
                    (namespace_id,),
                ).fetchone()["n"])
                supersedes = existing["active_generation_id"] or ""
            else:
                namespace_id = f"ns_{uuid.uuid4().hex}"
                next_number = 1
                supersedes = ""
                now = _now()
                conn.execute(
                    """INSERT INTO namespaces(
                        namespace_id,namespace_key,namespace_display,owner,status,active_generation_id,
                        project,workstream,adapter,created_at,updated_at,lifecycle_state,released_at,
                        tombstone_state,scope_lock
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        namespace_id, key, display, capsule.owner, "ACTIVE", None,
                        capsule.project, capsule.workstream, capsule.adapter, now, now,
                        "ACTIVE", None, "NONE", "OWNER+PROJECT+WORKSTREAM",
                    ),
                )

            generation_id = f"cbgen_{uuid.uuid4().hex}"
            handoff_id = f"cb4_{uuid.uuid4().hex}"
            now = _now()
            conn.execute(
                """INSERT INTO generations(
                    generation_id,namespace_id,namespace_key_snapshot,namespace_display_snapshot,
                    generation_number,handoff_id,checkpoint_fingerprint,governance_json,hot_json,
                    warm_json,cold_json,provider_ref_json,parent_generation_id,
                    branch_origin_namespace_id,branch_origin_generation_id,created_at,state,
                    supersedes_generation_id,restore_eligible
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    generation_id, namespace_id, key, display, next_number, handoff_id,
                    fingerprint, _canonical_json(capsule.to_dict()), _canonical_json(hot_state),
                    _canonical_json(warm_pointers), _canonical_json(cold_pointers),
                    _canonical_json(provider_ref.to_dict()), supersedes,
                    branch_origin_namespace_id, branch_origin_generation_id, now,
                    "ACTIVE_VERIFIED", supersedes, 1,
                ),
            )
            verify = conn.execute(
                "SELECT checkpoint_fingerprint,generation_number FROM generations WHERE generation_id=?",
                (generation_id,),
            ).fetchone()
            if not verify or verify["checkpoint_fingerprint"] != fingerprint or int(verify["generation_number"]) != next_number:
                raise RuntimeError("generation readback failed")

            conn.execute(
                """UPDATE namespaces SET active_generation_id=?,namespace_display=?,adapter=?,status='ACTIVE',
                    updated_at=?,lifecycle_state='ACTIVE',released_at=NULL,tombstone_state='NONE'
                    WHERE namespace_id=?""",
                (generation_id, display, capsule.adapter, now, namespace_id),
            )
            pointer = conn.execute(
                "SELECT active_generation_id FROM namespaces WHERE namespace_id=?", (namespace_id,)
            ).fetchone()
            if not pointer or pointer["active_generation_id"] != generation_id:
                raise RuntimeError("namespace pointer readback failed")
            self._event(conn, "CHECKPOINT_BOUND", namespace_id, generation_id, {"fingerprint": fingerprint})
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        return {
            "namespace_id": namespace_id,
            "generation_id": generation_id,
            "generation_number": next_number,
            "handoff_id": handoff_id,
            "checkpoint_fingerprint": fingerprint,
            "reused": False,
        }

    def list_namespaces(self, *, include_released: bool = False) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM namespaces"
        params: Tuple[Any, ...] = tuple()
        if not include_released:
            sql += " WHERE lifecycle_state!='RELEASED'"
        sql += " ORDER BY updated_at DESC"
        return [dict(row) for row in self._conn().execute(sql, params).fetchall()]

    def status(self, namespace: str) -> Dict[str, Any]:
        row = self._namespace_row(namespace)
        if not row:
            raise NamespaceNotFound(namespace)
        out = dict(row)
        if row["active_generation_id"]:
            gen = self._generation_row(row["active_generation_id"])
            out["active_generation_number"] = int(gen["generation_number"])
            out["checkpoint_fingerprint"] = gen["checkpoint_fingerprint"]
            out["handoff_id"] = gen["handoff_id"]
        return out

    def history(self, namespace: str) -> List[Dict[str, Any]]:
        row = self._namespace_row(namespace)
        if not row:
            raise NamespaceNotFound(namespace)
        return [dict(item) for item in self._conn().execute(
            "SELECT * FROM generations WHERE namespace_id=? ORDER BY generation_number ASC",
            (row["namespace_id"],),
        ).fetchall()]

    def rename(self, source: str, target: str) -> Dict[str, Any]:
        target_display = target.strip()
        target_key = _namespace_key(target_display)
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute("SELECT * FROM namespaces WHERE namespace_key=?", (_namespace_key(source),)).fetchone()
            if not row:
                raise NamespaceNotFound(source)
            collision = conn.execute("SELECT namespace_id FROM namespaces WHERE namespace_key=?", (target_key,)).fetchone()
            if collision and collision["namespace_id"] != row["namespace_id"]:
                raise NamespaceCollision(f"target namespace {target_display!r} already exists")
            conn.execute(
                "UPDATE namespaces SET namespace_key=?,namespace_display=?,updated_at=? WHERE namespace_id=?",
                (target_key, target_display, _now(), row["namespace_id"]),
            )
            self._event(conn, "NAMESPACE_RENAMED", row["namespace_id"], row["active_generation_id"] or "", {"from": source, "to": target_display})
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return self.status(target_display)

    def release(self, namespace: str) -> Dict[str, Any]:
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute("SELECT * FROM namespaces WHERE namespace_key=?", (_namespace_key(namespace),)).fetchone()
            if not row:
                raise NamespaceNotFound(namespace)
            now = _now()
            conn.execute(
                """UPDATE namespaces SET status='RELEASED',lifecycle_state='RELEASED',released_at=?,
                    tombstone_state='TOMBSTONED',updated_at=? WHERE namespace_id=?""",
                (now, now, row["namespace_id"]),
            )
            self._event(conn, "NAMESPACE_RELEASED", row["namespace_id"], row["active_generation_id"] or "", {})
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return self.status(namespace)

    def _provider_ref_from_json(self, payload: str) -> ProviderContinuationRef:
        data = json.loads(payload)
        data["mode"] = ContinuationMode(data.get("mode", "NONE"))
        return ProviderContinuationRef(**data)

    def restore(
        self,
        namespace: str,
        *,
        destination_session_key: str,
        generation_number: Optional[int] = None,
        material_delta: bool = False,
        governance_degraded: bool = False,
    ) -> RestoreEnvelope:
        ns = self._namespace_row(namespace)
        if not ns:
            raise NamespaceNotFound(namespace)
        if generation_number is None:
            generation_id = ns["active_generation_id"]
            if not generation_id:
                raise NamespaceNotFound(f"namespace {namespace!r} has no active generation")
            gen = self._generation_row(generation_id)
        else:
            gen = self._conn().execute(
                "SELECT * FROM generations WHERE namespace_id=? AND generation_number=?",
                (ns["namespace_id"], generation_number),
            ).fetchone()
            if not gen:
                raise NamespaceNotFound(f"generation {generation_number} for {namespace!r}")
            generation_id = gen["generation_id"]

        reasons: List[RestorePreviewReason] = []
        if generation_id != ns["active_generation_id"]:
            reasons.append(RestorePreviewReason.HISTORICAL_GENERATION)
        if ns["lifecycle_state"] == "RELEASED":
            reasons.append(RestorePreviewReason.RELEASED_NAMESPACE)
        if gen["branch_origin_namespace_id"]:
            reasons.append(RestorePreviewReason.BRANCHED_NAMESPACE)
        if material_delta:
            reasons.append(RestorePreviewReason.MATERIAL_DELTA)
        if governance_degraded:
            reasons.append(RestorePreviewReason.GOVERNANCE_DEGRADED)

        lease = self._conn().execute(
            """SELECT * FROM restore_leases WHERE namespace_id=? AND generation_id=?
               AND destination_session_key=?""",
            (ns["namespace_id"], generation_id, destination_session_key),
        ).fetchone()
        if lease and lease["checkpoint_fingerprint"] == gen["checkpoint_fingerprint"] and lease["status"] == "ACTIVE":
            lease_id = lease["lease_id"]
            self._conn().execute(
                "UPDATE restore_leases SET last_used_at=? WHERE lease_id=?", (_now(), lease_id)
            )
            lease_reused = True
        else:
            lease_id = f"lease_{uuid.uuid4().hex}"
            now = _now()
            self._conn().execute(
                """INSERT OR REPLACE INTO restore_leases(
                    lease_id,namespace_id,generation_id,destination_session_key,
                    checkpoint_fingerprint,status,acquired_at,last_used_at
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    lease_id, ns["namespace_id"], generation_id, destination_session_key,
                    gen["checkpoint_fingerprint"], "ACTIVE", now, now,
                ),
            )
            lease_reused = False

        governance = GovernanceCapsule.from_dict(json.loads(gen["governance_json"]))
        return RestoreEnvelope(
            namespace_id=ns["namespace_id"],
            namespace_display=ns["namespace_display"],
            namespace_key=ns["namespace_key"],
            generation_id=generation_id,
            generation_number=int(gen["generation_number"]),
            handoff_id=gen["handoff_id"],
            checkpoint_fingerprint=gen["checkpoint_fingerprint"],
            governance=governance,
            hot_state=json.loads(gen["hot_json"]),
            warm_pointers=json.loads(gen["warm_json"]),
            cold_pointers=json.loads(gen["cold_json"]),
            provider_ref=self._provider_ref_from_json(gen["provider_ref_json"]),
            preview_required=bool(reasons),
            preview_reasons=tuple(reasons),
            lease_id=lease_id,
            lease_reused=lease_reused,
        )

    def clone(self, source: str, target: str) -> Dict[str, Any]:
        ns = self._namespace_row(source)
        if not ns or not ns["active_generation_id"]:
            raise NamespaceNotFound(source)
        gen = self._generation_row(ns["active_generation_id"])
        governance = GovernanceCapsule.from_dict(json.loads(gen["governance_json"]))
        return self.backup(
            target,
            governance,
            hot_state=json.loads(gen["hot_json"]),
            warm_pointers=json.loads(gen["warm_json"]),
            cold_pointers=json.loads(gen["cold_json"]),
            provider_ref=self._provider_ref_from_json(gen["provider_ref_json"]),
            branch_origin_namespace_id=ns["namespace_id"],
            branch_origin_generation_id=gen["generation_id"],
        )
