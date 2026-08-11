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
from .operations import OperationJournal, normalize_operation_id
from .slrk import (
    ActivationState,
    CapabilityAssessment,
    CapabilityContract,
    CapabilityState,
    EnginePromotionRequest,
    EnginePromotionResult,
    FaultRecord,
    PreservationState,
    PromotionDecision,
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
        self.operation_journal = OperationJournal(self.db)
        self.db.commit()

    def close(self) -> None:
        with self._lock:
            self.db.close()

    @staticmethod
    def _operation_id(operation_id: str | None) -> str:
        return normalize_operation_id(operation_id) if operation_id else uuid.uuid4().hex

    def _insert_event_locked(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert one proof event using the caller's open transaction and lock."""
        payload_json = canonical_json(payload)
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
        return {"event_id": event_id, "payload_hash": payload_hash}

    def append_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            with self.db:
                return self._insert_event_locked(event_type, payload)

    def operation_receipt(self, operation_id: str) -> dict[str, Any] | None:
        with self._lock:
            receipt = self.operation_journal.get(operation_id)
        return receipt.to_dict() if receipt else None

    def create_mission(
        self,
        owner: str,
        instruction: str,
        *,
        operation_id: str | None = None,
        principal: str = "system",
    ) -> str:
        operation_id = self._operation_id(operation_id)
        request_payload = {"owner": owner, "instruction": instruction}
        operation_type = "MISSION_CREATE"
        with self._lock:
            with self.db:
                replay = self.operation_journal.replay(
                    operation_id, operation_type, request_payload
                )
                if replay:
                    return str(replay.result["mission_id"])

                mission_id = str(uuid.uuid4())
                self.db.execute(
                    "INSERT INTO missions(mission_id,owner,instruction,state,created_at) VALUES(?,?,?,?,?)",
                    (mission_id, owner, instruction, "RECEIVED", utcnow()),
                )
                event_payload = {
                    "mission_id": mission_id,
                    "owner": owner,
                    "operation_id": operation_id,
                    "principal": principal,
                    "target": mission_id,
                    "previous_state": "ABSENT",
                    "new_state": "RECEIVED",
                }
                event = self._insert_event_locked("MISSION_CREATED", event_payload)
                self.operation_journal.record(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    request_payload=request_payload,
                    principal=principal,
                    target=mission_id,
                    event_id=event["event_id"],
                    result={"mission_id": mission_id},
                )
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

    def register_capability(
        self,
        contract: CapabilityContract,
        *,
        operation_id: str | None = None,
        principal: str = "system",
    ) -> None:
        operation_id = self._operation_id(operation_id)
        payload = contract.to_dict()
        operation_type = "CAPABILITY_REGISTER"
        with self._lock:
            with self.db:
                replay = self.operation_journal.replay(operation_id, operation_type, payload)
                if replay:
                    return
                previous = self.db.execute(
                    "SELECT contract_json FROM capability_contracts WHERE capability_id=?",
                    (contract.capability_id,),
                ).fetchone()
                previous_state = (
                    json.loads(previous["contract_json"]).get("state", "UNKNOWN")
                    if previous
                    else "ABSENT"
                )
                self.db.execute(
                    "INSERT INTO capability_contracts(capability_id,contract_json,updated_at) VALUES(?,?,?) "
                    "ON CONFLICT(capability_id) DO UPDATE SET contract_json=excluded.contract_json,updated_at=excluded.updated_at",
                    (contract.capability_id, canonical_json(payload), utcnow()),
                )
                event_payload = {
                    "capability_id": contract.capability_id,
                    "state": contract.state.value,
                    "preservation_state": contract.preservation_state.value,
                    "activation_state": contract.activation_state.value,
                    "permanent_exclusion_requested": contract.permanent_exclusion_requested,
                    "operation_id": operation_id,
                    "principal": principal,
                    "target": contract.capability_id,
                    "previous_state": previous_state,
                    "new_state": contract.state.value,
                }
                event = self._insert_event_locked("CAPABILITY_REGISTERED", event_payload)
                self.operation_journal.record(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    request_payload=payload,
                    principal=principal,
                    target=contract.capability_id,
                    event_id=event["event_id"],
                    result={
                        "status": "CAPABILITY_REGISTERED",
                        "capability_id": contract.capability_id,
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

    def register_fault(
        self,
        record: FaultRecord,
        *,
        operation_id: str | None = None,
        principal: str = "system",
    ) -> None:
        operation_id = self._operation_id(operation_id)
        payload = {**record.__dict__, "severity": record.severity.value}
        operation_type = "FAULT_REGISTER"
        with self._lock:
            with self.db:
                replay = self.operation_journal.replay(operation_id, operation_type, payload)
                if replay:
                    return
                previous_fault = self.db.execute(
                    "SELECT status FROM fault_records WHERE fault_id=?", (record.fault_id,)
                ).fetchone()
                previous_route = self.route_state(record.route_id) if record.route_id else None
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
                event_payload = {
                    "fault_id": record.fault_id,
                    "route_id": record.route_id,
                    "operation_id": operation_id,
                    "principal": principal,
                    "target": record.fault_id,
                    "previous_state": {
                        "fault": previous_fault["status"] if previous_fault else "ABSENT",
                        "route": previous_route["state"] if previous_route else "NOT_APPLICABLE",
                    },
                    "new_state": {
                        "fault": "ACTIVE",
                        "route": (
                            RouteState.BANNED_UNLESS_CLEARED.value
                            if record.route_id
                            else "NOT_APPLICABLE"
                        ),
                    },
                }
                event = self._insert_event_locked("FAULT_REGISTERED", event_payload)
                self.operation_journal.record(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    request_payload=payload,
                    principal=principal,
                    target=record.fault_id,
                    event_id=event["event_id"],
                    result={"status": "FAULT_REGISTERED", "fault_id": record.fault_id},
                )

    def route_state(self, route_id: str | None) -> dict[str, str]:
        if not route_id:
            return {"route_id": "", "state": RouteState.AVAILABLE.value, "reason": "", "updated_at": ""}
        with self._lock:
            row = self.db.execute(
                "SELECT route_id,state,reason,updated_at FROM route_memory WHERE route_id=?", (route_id,)
            ).fetchone()
        if row is None:
            return {"route_id": route_id, "state": RouteState.AVAILABLE.value, "reason": "", "updated_at": ""}
        return dict(row)

    def clear_route(
        self,
        route_id: str,
        reason: str,
        *,
        conditions_changed: bool,
        operation_id: str | None = None,
        principal: str = "system",
    ) -> dict[str, str]:
        if not conditions_changed:
            raise ValueError("A banned route may be cleared only after material conditions change.")
        operation_id = self._operation_id(operation_id)
        request_payload = {
            "route_id": route_id,
            "reason": reason,
            "conditions_changed": conditions_changed,
        }
        operation_type = "ROUTE_CLEAR"
        with self._lock:
            with self.db:
                replay = self.operation_journal.replay(
                    operation_id, operation_type, request_payload
                )
                if replay:
                    return dict(replay.result["route"])
                previous = self.route_state(route_id)
                self.db.execute(
                    "INSERT INTO route_memory(route_id,state,reason,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(route_id) DO UPDATE SET state=excluded.state,reason=excluded.reason,updated_at=excluded.updated_at",
                    (route_id, RouteState.AVAILABLE.value, reason, utcnow()),
                )
                current = dict(
                    self.db.execute(
                        "SELECT route_id,state,reason,updated_at FROM route_memory WHERE route_id=?",
                        (route_id,),
                    ).fetchone()
                )
                event_payload = {
                    "route_id": route_id,
                    "reason": reason,
                    "operation_id": operation_id,
                    "principal": principal,
                    "target": route_id,
                    "previous_state": previous["state"],
                    "new_state": current["state"],
                }
                event = self._insert_event_locked("ROUTE_CLEARED", event_payload)
                self.operation_journal.record(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    request_payload=request_payload,
                    principal=principal,
                    target=route_id,
                    event_id=event["event_id"],
                    result={"route": current},
                )
        return current

    @staticmethod
    def _promotion_from_dict(value: dict[str, Any]) -> EnginePromotionResult:
        return EnginePromotionResult(
            decision=PromotionDecision(value["decision"]),
            missing_gates=tuple(value["missing_gates"]),
            claim_language=value["claim_language"],
        )

    def evaluate_engine_promotion(
        self,
        request: EnginePromotionRequest,
        *,
        operation_id: str | None = None,
        principal: str = "system",
    ) -> EnginePromotionResult:
        operation_id = self._operation_id(operation_id)
        result = evaluate_engine_promotion(request)
        request_payload = {**request.__dict__, "target_environment": request.target_environment.value}
        operation_type = "ENGINE_PROMOTION_EVALUATE"
        with self._lock:
            with self.db:
                replay = self.operation_journal.replay(
                    operation_id, operation_type, request_payload
                )
                if replay:
                    return self._promotion_from_dict(replay.result["promotion"])
                self.db.execute(
                    "INSERT INTO engine_promotions(engine_id,request_json,result_json,created_at) VALUES(?,?,?,?)",
                    (request.engine_id, canonical_json(request_payload), canonical_json(result.to_dict()), utcnow()),
                )
                event_payload = {
                    "engine_id": request.engine_id,
                    **result.to_dict(),
                    "operation_id": operation_id,
                    "principal": principal,
                    "target": request.engine_id,
                    "previous_state": "NO_EVALUATION_FOR_OPERATION",
                    "new_state": result.decision.value,
                }
                event = self._insert_event_locked("ENGINE_PROMOTION_EVALUATED", event_payload)
                self.operation_journal.record(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    request_payload=request_payload,
                    principal=principal,
                    target=request.engine_id,
                    event_id=event["event_id"],
                    result={"promotion": result.to_dict()},
                )
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
            operation_count = self.db.execute("SELECT COUNT(*) FROM operation_receipts").fetchone()[0]
            active_fault_count = self.db.execute("SELECT COUNT(*) FROM fault_records WHERE status='ACTIVE'").fetchone()[0]
            banned_route_count = self.db.execute(
                "SELECT COUNT(*) FROM route_memory WHERE state=?", (RouteState.BANNED_UNLESS_CLEARED.value,)
            ).fetchone()[0]
        return {
            "event_count": event_count,
            "mission_count": mission_count,
            "capability_count": capability_count,
            "operation_count": operation_count,
            "active_fault_count": active_fault_count,
            "banned_route_count": banned_route_count,
            "event_chain_valid": self.verify_event_chain(),
            "non_dilution_policy": "POL-ECASP-NONDILUTION-20260729-001",
        }
