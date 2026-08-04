from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from .ledger import AppendOnlyLedger
from .models import (
    AttemptStatus,
    EvidenceJob,
    ExecutionLane,
    FailureClass,
    LaneResult,
    ProofLevel,
    ResolvePolicy,
)


IndependentVerifier = Callable[[EvidenceJob, dict[str, Any]], dict[str, Any]]


class ResolveEngine:
    def __init__(self, workspace: str | Path, policy: ResolvePolicy | None = None) -> None:
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.policy = policy or ResolvePolicy()
        self.ledger = AppendOnlyLedger(self.workspace / "resolve_ledger.jsonl")
        self.discrepancies = AppendOnlyLedger(self.workspace / "discrepancies.jsonl")
        self.lanes: dict[str, ExecutionLane] = {}
        self.failure_counts: dict[str, int] = {}
        self.failure_fingerprints: set[str] = set()
        self.learned_rules: dict[str, dict[str, Any]] = {}

    @staticmethod
    def idempotency_key(operation: str, source: dict[str, Any], outputs: list[dict[str, Any]]) -> str:
        canonical = json.dumps(
            {"operation": operation, "source": source, "outputs": outputs},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def register_lane(self, lane: ExecutionLane) -> None:
        self.lanes[lane.lane_id] = lane
        self.ledger.append("LANE_REGISTERED", {"lane_id": lane.lane_id, "score": lane.score(), "tags": sorted(lane.tags)})

    def available_lanes(self) -> list[ExecutionLane]:
        lanes = [lane for lane in self.lanes.values() if lane.enabled]
        lanes.sort(key=lambda lane: lane.score(), reverse=True)
        return lanes

    def _fingerprint(self, lane_id: str, result: LaneResult) -> str:
        details = json.dumps(result.details, sort_keys=True, default=str)
        return hashlib.sha256(f"{lane_id}|{result.failure_class}|{details}".encode()).hexdigest()

    def _open_circuit(self, lane_id: str) -> None:
        lane = self.lanes[lane_id]
        lane.enabled = False
        self.ledger.append("CIRCUIT_OPENED", {"lane_id": lane_id, "failures": self.failure_counts[lane_id]})

    def restore_lane(self, lane_id: str, changed_condition: str) -> None:
        self.lanes[lane_id].enabled = True
        self.failure_counts[lane_id] = 0
        self.ledger.append("CIRCUIT_RESTORED", {"lane_id": lane_id, "changed_condition": changed_condition})

    def _learn(self, lane: ExecutionLane, result: LaneResult) -> None:
        failure_class = (result.failure_class or FailureClass.UNKNOWN).value
        key = f"{failure_class}:{lane.lane_id}"
        self.learned_rules[key] = {
            "avoid_lane": lane.lane_id,
            "failure_class": failure_class,
            "next_preference": "alternate lane with higher capacity or authority",
            "details": result.details,
        }
        self.ledger.append("CAPABILITY_LEARNED", {"rule_id": key, **self.learned_rules[key]})

    def execute(self, job: EvidenceJob, verifier: IndependentVerifier | None = None) -> dict[str, Any]:
        self.ledger.append("JOB_STARTED", job.to_dict())
        attempts = []
        provider_result: dict[str, Any] | None = None

        for attempt_number, lane in enumerate(self.available_lanes(), 1):
            if attempt_number > self.policy.max_attempts:
                break
            self.ledger.append("ATTEMPT_STARTED", {"job_id": job.job_id, "lane_id": lane.lane_id, "attempt": attempt_number})
            try:
                result = lane.executor(job)
            except Exception as exc:
                result = LaneResult(
                    status=AttemptStatus.FAILED,
                    failure_class=FailureClass.UNKNOWN,
                    details={"exception": type(exc).__name__, "message": str(exc)},
                    retryable=False,
                )

            attempt = {
                "attempt": attempt_number,
                "lane_id": lane.lane_id,
                "status": result.status.value,
                "failure_class": result.failure_class.value if result.failure_class else None,
                "details": result.details,
            }
            attempts.append(attempt)
            self.ledger.append("ATTEMPT_FINISHED", {"job_id": job.job_id, **attempt})

            if result.status == AttemptStatus.SUCCESS:
                provider_result = result.details
                break

            fingerprint = self._fingerprint(lane.lane_id, result)
            is_repeat = fingerprint in self.failure_fingerprints
            self.failure_fingerprints.add(fingerprint)
            self.failure_counts[lane.lane_id] = self.failure_counts.get(lane.lane_id, 0) + 1
            self._learn(lane, result)
            self.discrepancies.append("EXECUTION_FAILURE", {"job_id": job.job_id, **attempt, "repeated": is_repeat})

            if self.failure_counts[lane.lane_id] >= self.policy.circuit_breaker_threshold:
                self._open_circuit(lane.lane_id)

        if provider_result is None:
            receipt = self._receipt(job, attempts, ProofLevel.DECLARED, "BLOCKED", {}, "No execution lane completed successfully")
            self._write_receipt(job.job_id, receipt)
            return receipt

        provider_gate = next((gate for gate in job.gates if gate.gate_id == "provider_readback"), None)
        if provider_gate:
            provider_gate.passed = True
            provider_gate.evidence = provider_result

        proof_level = ProofLevel.PROVIDER_READBACK
        independent_result: dict[str, Any] = {}
        if self.policy.require_independent_readback:
            if verifier is None:
                receipt = self._receipt(job, attempts, proof_level, "PARTIAL", provider_result, "Independent verifier not supplied")
                self._write_receipt(job.job_id, receipt)
                return receipt
            independent_result = verifier(job, provider_result)
            independent_ok = bool(independent_result.get("ok"))
            gate = next((item for item in job.gates if item.gate_id == "independent_readback"), None)
            if gate:
                gate.passed = independent_ok
                gate.evidence = independent_result
            if not independent_ok:
                self.discrepancies.append("INDEPENDENT_VERIFICATION_FAILED", {"job_id": job.job_id, "result": independent_result})
                receipt = self._receipt(job, attempts, proof_level, "PARTIAL", provider_result, "Independent verification failed", independent_result)
                self._write_receipt(job.job_id, receipt)
                return receipt
            proof_level = ProofLevel.INDEPENDENT_READBACK

        mandatory_passed = all(gate.passed for gate in job.gates if gate.mandatory)
        status = "COMPLETE_VERIFIED" if mandatory_passed else "PARTIAL"
        if mandatory_passed:
            proof_level = ProofLevel.COMPLETE_VERIFIED
        receipt = self._receipt(job, attempts, proof_level, status, provider_result, "", independent_result)
        self._write_receipt(job.job_id, receipt)
        self.ledger.append("JOB_FINISHED", {"job_id": job.job_id, "status": status, "proof_level": proof_level.value})
        return receipt

    def _receipt(
        self,
        job: EvidenceJob,
        attempts: list[dict[str, Any]],
        proof_level: ProofLevel,
        status: str,
        provider_result: dict[str, Any],
        reason: str,
        independent_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema": "RESOLVE-RECEIPT-1",
            "job_id": job.job_id,
            "idempotency_key": job.idempotency_key,
            "status": status,
            "proof_level": proof_level.value,
            "reason": reason,
            "attempts": attempts,
            "provider_result": provider_result,
            "independent_result": independent_result or {},
            "gates": [asdict(gate) for gate in job.gates],
            "learned_rules": self.learned_rules,
        }

    def _write_receipt(self, job_id: str, receipt: dict[str, Any]) -> None:
        path = self.workspace / "receipts" / f"{job_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
