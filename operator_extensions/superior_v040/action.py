from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

ACTION = "DEPLOY_SUPERIOR_V040_CANARY"
ARTIFACT_SHA256 = "3c43cec61dd69ae6dfe256a9d3ba38983b849ec35639b7f246d78307735e88da"
SERVICE = "superior-doctrine-v040-canary"


class CanaryFailure(RuntimeError):
    pass


class CloudRunBackend(Protocol):
    def snapshot(self, service: str) -> dict[str, Any]: ...
    def deploy_canary(self, service: str, artifact_sha256: str, config: dict[str, Any], idempotency_key: str) -> dict[str, Any]: ...
    def readback(self, service: str, revision: str) -> dict[str, Any]: ...
    def rollback(self, service: str, snapshot: dict[str, Any]) -> dict[str, Any]: ...


class KDVWriter(Protocol):
    def append(self, record: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class CanaryRequest:
    action: str
    artifact_sha256: str
    service: str
    idempotency_key: str
    formation_permit_receipt: str
    min_instances: int = 0
    max_instances: int = 1
    traffic_percent: int = 0
    expected_version: str = "0.4.0"


@dataclass(frozen=True)
class CanaryResult:
    state: str
    service: str
    revision: str
    artifact_sha256: str
    heartbeat_proof: str
    kdv_receipt: str
    watchman_proof: str
    idempotency_key: str
    traffic_percent: int = 0


class ReceiptStore:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS canary_receipts(key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, state TEXT NOT NULL, result TEXT NOT NULL, created REAL NOT NULL)")
        self.db.commit()

    def get(self, key: str, request_hash: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT request_hash,state,result FROM canary_receipts WHERE key=?", (key,)).fetchone()
        if not row: return None
        if row[0] != request_hash: raise CanaryFailure("IDEMPOTENCY_CONFLICT")
        if row[1] != "PROVEN": raise CanaryFailure("PRIOR_ATTEMPT_NOT_PROVEN")
        return json.loads(row[2])

    def put(self, key: str, request_hash: str, state: str, result: dict[str, Any]) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO canary_receipts VALUES(?,?,?,?,?)", (key, request_hash, state, json.dumps(result, sort_keys=True), time.time()))


class LockedCanaryAction:
    def __init__(self, backend: CloudRunBackend, kdv: KDVWriter, receipts: ReceiptStore,
                 watchman: Callable[[str, str, dict[str, Any], dict[str, Any]], dict[str, Any]]):
        self.backend, self.kdv, self.receipts, self.watchman = backend, kdv, receipts, watchman

    @staticmethod
    def _request_hash(req: CanaryRequest) -> str:
        return hashlib.sha256(json.dumps(asdict(req), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _validate(req: CanaryRequest) -> None:
        if req.action != ACTION: raise CanaryFailure("ACTION_NOT_ALLOWLISTED")
        if req.artifact_sha256 != ARTIFACT_SHA256: raise CanaryFailure("ARTIFACT_HASH_MISMATCH")
        if req.service != SERVICE: raise CanaryFailure("SERVICE_SCOPE_MISMATCH")
        if not req.idempotency_key or not req.formation_permit_receipt: raise CanaryFailure("PERMIT_AND_IDEMPOTENCY_REQUIRED")
        if (req.min_instances, req.max_instances, req.traffic_percent) != (0, 1, 0): raise CanaryFailure("ZERO_COST_CANARY_POLICY_VIOLATION")
        if req.expected_version != "0.4.0": raise CanaryFailure("VERSION_LOCK_MISMATCH")

    def execute(self, req: CanaryRequest) -> CanaryResult:
        self._validate(req); request_hash = self._request_hash(req)
        prior = self.receipts.get(req.idempotency_key, request_hash)
        if prior: return CanaryResult(**prior)
        snapshot = self.backend.snapshot(req.service)
        try:
            deploy = self.backend.deploy_canary(req.service, req.artifact_sha256, {
                "min_instances": 0, "max_instances": 1, "traffic_percent": 0,
                "cost_policy": "ZERO_NEW_RECURRING_COST", "formation_permit_receipt": req.formation_permit_receipt,
            }, req.idempotency_key)
            revision = str(deploy.get("revision") or "")
            if not revision: raise CanaryFailure("DEPLOYMENT_REVISION_MISSING")
            fruit = self.backend.readback(req.service, revision)
            required = {
                "ready": True, "version": "0.4.0", "artifact_sha256": ARTIFACT_SHA256,
                "traffic_percent": 0, "min_instances": 0, "max_instances": 1,
                "cost_policy": "ZERO_NEW_RECURRING_COST", "heartbeat_state": "PROVEN",
            }
            if any(fruit.get(k) != v for k, v in required.items()): raise CanaryFailure("SEMANTIC_READBACK_MISMATCH")
            heartbeat = str(fruit.get("heartbeat_proof") or "")
            if not heartbeat: raise CanaryFailure("HEARTBEAT_PROOF_MISSING")
            kdv_record = {"action": ACTION, "service": req.service, "revision": revision, "artifact_sha256": ARTIFACT_SHA256,
                          "idempotency_key": req.idempotency_key, "heartbeat_proof": heartbeat, "state": "CANARY_READY_ZERO_TRAFFIC"}
            kdv_result = self.kdv.append(kdv_record); kdv_receipt = str(kdv_result.get("proof_ref") or "")
            if not kdv_receipt or kdv_result.get("readback_match") is not True: raise CanaryFailure("KDV_READBACK_UNPROVEN")
            claim = {**required, "service": req.service, "revision": revision, "kdv_receipt": kdv_receipt}
            proof = self.watchman("omega-operator", "independent-watchman", claim, {**fruit, "service": req.service, "revision": revision, "kdv_receipt": kdv_receipt})
            watchman_ref = str(proof.get("proof_ref") or "")
            if proof.get("state") != "PROVEN" or not watchman_ref: raise CanaryFailure("WATCHMAN_REJECTED")
            result = CanaryResult("CANARY_PROVEN_ZERO_TRAFFIC", req.service, revision, ARTIFACT_SHA256, heartbeat, kdv_receipt, watchman_ref, req.idempotency_key)
            self.receipts.put(req.idempotency_key, request_hash, "PROVEN", asdict(result)); return result
        except Exception as exc:
            rollback = self.backend.rollback(req.service, snapshot)
            self.receipts.put(req.idempotency_key, request_hash, "ROLLED_BACK", {"error": str(exc), "rollback": rollback})
            if isinstance(exc, CanaryFailure): raise
            raise CanaryFailure(type(exc).__name__) from exc
