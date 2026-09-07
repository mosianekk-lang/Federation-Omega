"""Durable local state store for FUSE AURORA-Ω v1.

The store is intentionally provider-neutral and effect-local. It uses SQLite/WAL,
payload integrity hashes and optional optimistic concurrency to make long-horizon
mission state restart-safe without treating model context as canonical storage.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from federation.aurora_omega_v1 import (
    AgentEvent,
    AppreciationFinding,
    AuroraOmegaAgent,
    Evidence,
    Lens,
    MissionContract,
    MissionPhase,
    MissionState,
    RouteCandidate,
    SpecialistRole,
    TerminalEvent,
)


class StateIntegrityError(RuntimeError):
    pass


class StateConflictError(RuntimeError):
    pass


class MissionStateCodec:
    SCHEMA = "FUSE-AURORA-STATE-V1"

    @classmethod
    def encode(cls, state: MissionState) -> str:
        payload: dict[str, Any] = {
            "schema": cls.SCHEMA,
            "mission_id": state.mission_id,
            "version": state.version,
            "phase": state.phase.value,
            "contract": {
                "objective": state.contract.objective,
                "completion_predicates": list(state.contract.completion_predicates),
                "lens": state.contract.lens.value,
                "authority_ceiling": state.contract.authority_ceiling,
                "external_effects_allowed": state.contract.external_effects_allowed,
                "require_independent_verification": state.contract.require_independent_verification,
                "require_root_cause_on_failure": state.contract.require_root_cause_on_failure,
            },
            "routes": [asdict(route) for route in state.routes],
            "selected_route_ids": list(state.selected_route_ids),
            "appreciation_findings": [asdict(item) for item in state.appreciation_findings],
            "open_unknowns": list(state.open_unknowns),
            "root_causes": dict(state.root_causes),
            "failure_counts": dict(state.failure_counts),
            "failure_fingerprints": dict(state.failure_fingerprints),
            "banned_routes": sorted(state.banned_routes),
            "evidence": [asdict(item) for item in state.evidence],
            "specialist_roster": [role.value for role in state.specialist_roster],
            "events": [
                {
                    "sequence": event.sequence,
                    "event_type": event.event_type.value,
                    "payload": dict(event.payload),
                    "previous_hash": event.previous_hash,
                    "event_hash": event.event_hash,
                }
                for event in state.events
            ],
            "satisfied_predicates": sorted(state.satisfied_predicates),
            "critical_unknowns": sorted(state.critical_unknowns),
            "artifacts": list(state.artifacts),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def decode(cls, payload_json: str) -> MissionState:
        payload = json.loads(payload_json)
        if payload.get("schema") != cls.SCHEMA:
            raise StateIntegrityError("unsupported state schema")

        c = payload["contract"]
        contract = MissionContract(
            objective=c["objective"],
            completion_predicates=tuple(c["completion_predicates"]),
            lens=Lens(c["lens"]),
            authority_ceiling=c["authority_ceiling"],
            external_effects_allowed=bool(c["external_effects_allowed"]),
            require_independent_verification=bool(c["require_independent_verification"]),
            require_root_cause_on_failure=bool(c["require_root_cause_on_failure"]),
        )

        return MissionState(
            mission_id=payload["mission_id"],
            contract=contract,
            version=int(payload["version"]),
            phase=MissionPhase(payload["phase"]),
            routes=[RouteCandidate(**route) for route in payload["routes"]],
            selected_route_ids=list(payload["selected_route_ids"]),
            appreciation_findings=[
                AppreciationFinding(
                    finding_id=item["finding_id"],
                    kind=item["kind"],
                    claim=item["claim"],
                    evidence_refs=tuple(item.get("evidence_refs", ())),
                    confidence=float(item.get("confidence", 0.5)),
                )
                for item in payload["appreciation_findings"]
            ],
            open_unknowns=list(payload["open_unknowns"]),
            root_causes=dict(payload["root_causes"]),
            failure_counts={k: int(v) for k, v in payload["failure_counts"].items()},
            failure_fingerprints=dict(payload["failure_fingerprints"]),
            banned_routes=set(payload["banned_routes"]),
            evidence=[Evidence(**item) for item in payload["evidence"]],
            specialist_roster=[SpecialistRole(role) for role in payload["specialist_roster"]],
            events=[
                AgentEvent(
                    sequence=int(event["sequence"]),
                    event_type=TerminalEvent(event["event_type"]),
                    payload=dict(event["payload"]),
                    previous_hash=event["previous_hash"],
                    event_hash=event["event_hash"],
                )
                for event in payload["events"]
            ],
            satisfied_predicates=set(payload["satisfied_predicates"]),
            critical_unknowns=set(payload["critical_unknowns"]),
            artifacts=list(payload["artifacts"]),
        )


class AuroraStateStore:
    """SQLite/WAL mission store with content integrity and CAS-style saves."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS aurora_missions (
                    mission_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    @staticmethod
    def _digest(payload_json: str) -> str:
        return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    def save(self, state: MissionState, *, expected_stored_version: int | None = None) -> str:
        payload_json = MissionStateCodec.encode(state)
        digest = self._digest(payload_json)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT version FROM aurora_missions WHERE mission_id = ?",
                (state.mission_id,),
            ).fetchone()
            existing_version = None if row is None else int(row[0])
            if expected_stored_version is not None and existing_version != expected_stored_version:
                raise StateConflictError(
                    f"mission {state.mission_id} stored version {existing_version!r} "
                    f"does not match expected {expected_stored_version}"
                )
            if existing_version is not None and state.version < existing_version:
                raise StateConflictError(
                    f"mission {state.mission_id} attempted version regression "
                    f"{state.version} < {existing_version}"
                )
            conn.execute(
                """
                INSERT INTO aurora_missions
                    (mission_id, version, payload_json, payload_sha256, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(mission_id) DO UPDATE SET
                    version=excluded.version,
                    payload_json=excluded.payload_json,
                    payload_sha256=excluded.payload_sha256,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (state.mission_id, state.version, payload_json, digest),
            )
        return digest

    def load(self, mission_id: str) -> MissionState:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT version, payload_json, payload_sha256
                FROM aurora_missions WHERE mission_id = ?
                """,
                (mission_id,),
            ).fetchone()
        if row is None:
            raise KeyError(mission_id)
        stored_version, payload_json, stored_hash = int(row[0]), row[1], row[2]
        if self._digest(payload_json) != stored_hash:
            raise StateIntegrityError(f"mission {mission_id} payload hash mismatch")
        state = MissionStateCodec.decode(payload_json)
        if state.version != stored_version:
            raise StateIntegrityError(f"mission {mission_id} version projection mismatch")
        if not AuroraOmegaAgent().verify_event_chain(state):
            raise StateIntegrityError(f"mission {mission_id} event chain invalid")
        return state

    def list_missions(self) -> tuple[tuple[str, int], ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT mission_id, version FROM aurora_missions ORDER BY mission_id"
            ).fetchall()
        return tuple((str(row[0]), int(row[1])) for row in rows)
