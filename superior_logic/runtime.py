from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ecasp import ECASPRequest, ECASPResult, evaluate_ecasp
from .slrk import (
    ActivationState,
    CapabilityAssessment,
    CapabilityContract,
    CapabilityState,
    EnginePromotionRequest,
    EnginePromotionResult,
    FaultRecord,
    PreservationState,
    ProofLevel,
    RouteState,
    assess_capabilities,
    evaluate_engine_promotion,
    govern_claim,
)

DONE_PREDICATES = (
    "operation_occurred", "target_resolved", "semantic_success", "payload_present",
    "result_stored", "source_readback_verified", "integrity_verified",
    "independent_observation_verified", "delivery_confirmed", "audit_complete",
    "no_invalidating_contradiction",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SuperiorLogicRuntime:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._lock = threading.RLock()
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS events(
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT UNIQUE NOT NULL,
              event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              payload_hash TEXT NOT NULL,
              predecessor_hash TEXT,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS missions(
              mission_id TEXT PRIMARY KEY,
              owner TEXT NOT NULL,
              instruction TEXT NOT NULL,
              state TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS capability_contracts(
              capability_id TEXT PRIMARY KEY,
              contract_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fault_records(
              fault_id TEXT PRIMARY KEY,
              record_json TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS route_memory(
              route_id TEXT PRIMARY KEY,
              state TEXT NOT NULL,
              reason TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS engine_promotions(
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              engine_id TEXT NOT NULL,
              request_json TEXT NOT NULL,
              result_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def close(self) -> None:
        with self._lock:
            self.db.close()

    def append_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload_json = canonical_json(payload)
        with self._lock:
            previous = self.db.execute(
                "SELECT payload_hash FROM events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            predecessor_hash = previous["payload_hash"] if previous else None
            envelope = canonical_json(
                {"event_type": event_type, "payload": payload, "predecessor_hash": predecessor_hash}
            )
            payload_hash = sha256_text(envelope)
            event_id = str(uuid.uuid4())
            self.db.execute(
                "INSERT INTO events(event_id,event_type,payload_json,payload_hash,predecessor_hash,created_at) VALUES(?,?,?,?,?,?)",
                (event_id, event_type, payload_json, payload_hash, predecessor_hash, utcnow()),
            )
            self.db.commit()
        return {"event_id": event_id, "payload_hash": payload_hash}

    def create_mission(self, owner: str, instruction: str) -> str:
        mission_id = str(uuid.uuid4())
        with self._lock:
            self.db.execute(
                "INSERT INTO missions(mission_id,owner,instruction,state,created_at) VALUES(?,?,?,?,?)",
                (mission_id, owner, instruction, "RECEIVED", utcnow()),
            )
            self.db.commit()
        self.append_event("MISSION_CREATED", {"mission_id": mission_id, "owner": owner})
        return mission_id

    def derive_done(self, predicates: dict[str, bool]) -> tuple[bool, list[str]]:
        missing = [name for name in DONE_PREDICATES if not predicates.get(name, False)]
        return (not missing, missing)

    def evaluate_corpus_selection(self, request: ECASPRequest) -> ECASPResult:
        result = evaluate_ecasp(request)
        self.append_event(
            "ECASP_EVALUATED",
            {
                "algorithm_id": result.algorithm_id,
                "status": result.status.value,
                "triggered": result.triggered,
                "allow_exhaustive_final": result.allow_exhaustive_final,
                "missing_gates": list(result.missing_gates),
                "object_counts": result.object_counts,
                "release_language": result.release_language,
                "non_dilution_policy": "POL-ECASP-NONDILUTION-20260729-001",
            },
        )
        return result

    def register_capability(self, contract: CapabilityContract) -> None:
        payload = contract.to_dict()
        with self._lock:
            self.db.execute(
                "INSERT INTO capability_contracts(capability_id,contract_json,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(capability_id) DO UPDATE SET contract_json=excluded.contract_json,updated_at=excluded.updated_at",
                (contract.capability_id, canonical_json(payload), utcnow()),
            )
            self.db.commit()
        self.append_event(
            "CAPABILITY_REGISTERED",
            {
                "capability_id": contract.capability_id,
                "state": contract.state.value,
                "preservation_state": contract.preservation_state.value,
                "activation_state": contract.activation_state.value,
                "permanent_exclusion_requested": contract.permanent_exclusion_requested,
            },
        )

    def _capability_contracts(self) -> list[CapabilityContract]:
        with self._lock:
            rows = list(self.db.execute("SELECT contract_json FROM capability_contracts ORDER BY capability_id"))
        result = []
        for row in rows:
            payload = json.loads(row["contract_json"])
            payload.pop("preserved", None)
            payload.pop("activation_allows_execution", None)
            payload["state"] = CapabilityState(payload["state"])
            payload["preservation_state"] = PreservationState(
                payload.get("preservation_state", PreservationState.FULL_PRESERVED.value)
            )
            payload["activation_state"] = ActivationState(
                payload.get("activation_state", ActivationState.PRESERVED_DORMANT.value)
            )
            payload["carrier_ids"] = tuple(payload.get("carrier_ids", ()))
            result.append(CapabilityContract(**payload))
        return result

    def assess_capabilities(self, required: tuple[str, ...]) -> CapabilityAssessment:
        result = assess_capabilities(required, self._capability_contracts())
        self.append_event("CAPABILITY_ASSESSED", result.to_dict())
        return result

    def govern_claim(
        self,
        claim: str,
        proof_level: ProofLevel,
        *,
        execution_verified: bool = False,
        gap_scan_complete: bool = False,
        lifecycle_complete: bool = False,
    ):
        result = govern_claim(
            claim,
            proof_level,
            execution_verified=execution_verified,
            gap_scan_complete=gap_scan_complete,
            lifecycle_complete=lifecycle_complete,
        )
        self.append_event("CLAIM_GOVERNED", result.to_dict())
        return result

    def register_fault(self, record: FaultRecord) -> None:
        payload = {**record.__dict__, "severity": record.severity.value}
        with self._lock:
            self.db.execute(
                "INSERT INTO fault_records(fault_id,record_json,status,created_at) VALUES(?,?,?,?) "
                "ON CONFLICT(fault_id) DO UPDATE SET record_json=excluded.record_json,status=excluded.status,created_at=excluded.created_at",
                (record.fault_id, canonical_json(payload), "ACTIVE", utcnow()),
            )
            if record.route_id:
                self.db.execute(
                    "INSERT INTO route_memory(route_id,state,reason,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(route_id) DO UPDATE SET state=excluded.state,reason=excluded.reason,updated_at=excluded.updated_at",
                    (record.route_id, RouteState.BANNED_UNLESS_CLEARED.value, record.detected_problem, utcnow()),
                )
            self.db.commit()
        self.append_event("FAULT_REGISTERED", {"fault_id": record.fault_id, "route_id": record.route_id})

    def route_state(self, route_id: str) -> dict[str, str]:
        with self._lock:
            row = self.db.execute(
                "SELECT route_id,state,reason,updated_at FROM route_memory WHERE route_id=?", (route_id,)
            ).fetchone()
        if row is None:
            return {"route_id": route_id, "state": RouteState.AVAILABLE.value, "reason": "", "updated_at": ""}
        return dict(row)

    def clear_route(self, route_id: str, reason: str, *, conditions_changed: bool) -> dict[str, str]:
        if not conditions_changed:
            raise ValueError("A banned route may be cleared only after material conditions change.")
        with self._lock:
            self.db.execute(
                "INSERT INTO route_memory(route_id,state,reason,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(route_id) DO UPDATE SET state=excluded.state,reason=excluded.reason,updated_at=excluded.updated_at",
                (route_id, RouteState.AVAILABLE.value, reason, utcnow()),
            )
            self.db.commit()
        self.append_event("ROUTE_CLEARED", {"route_id": route_id, "reason": reason})
        return self.route_state(route_id)

    def evaluate_engine_promotion(self, request: EnginePromotionRequest) -> EnginePromotionResult:
        result = evaluate_engine_promotion(request)
        request_payload = {**request.__dict__, "target_environment": request.target_environment.value}
        with self._lock:
            self.db.execute(
                "INSERT INTO engine_promotions(engine_id,request_json,result_json,created_at) VALUES(?,?,?,?)",
                (request.engine_id, canonical_json(request_payload), canonical_json(result.to_dict()), utcnow()),
            )
            self.db.commit()
        self.append_event("ENGINE_PROMOTION_EVALUATED", {"engine_id": request.engine_id, **result.to_dict()})
        return result

    def verify_event_chain(self) -> bool:
        with self._lock:
            rows = list(self.db.execute("SELECT * FROM events ORDER BY seq"))
        previous = None
        for row in rows:
            if row["predecessor_hash"] != previous:
                return False
            envelope = canonical_json(
                {
                    "event_type": row["event_type"],
                    "payload": json.loads(row["payload_json"]),
                    "predecessor_hash": row["predecessor_hash"],
                }
            )
            if sha256_text(envelope) != row["payload_hash"]:
                return False
            previous = row["payload_hash"]
        return True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            event_count = self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            mission_count = self.db.execute("SELECT COUNT(*) FROM missions").fetchone()[0]
            capability_count = self.db.execute("SELECT COUNT(*) FROM capability_contracts").fetchone()[0]
            active_fault_count = self.db.execute("SELECT COUNT(*) FROM fault_records WHERE status='ACTIVE'").fetchone()[0]
            banned_route_count = self.db.execute(
                "SELECT COUNT(*) FROM route_memory WHERE state=?", (RouteState.BANNED_UNLESS_CLEARED.value,)
            ).fetchone()[0]
        return {
            "event_count": event_count,
            "mission_count": mission_count,
            "capability_count": capability_count,
            "active_fault_count": active_fault_count,
            "banned_route_count": banned_route_count,
            "event_chain_valid": self.verify_event_chain(),
            "non_dilution_policy": "POL-ECASP-NONDILUTION-20260729-001",
        }
