"""Core RealityGuard analysis engine."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .model import Evidence, EvidenceGrade, LifecycleState, ScanResult, Verdict
from .rules import evaluate, missing_gates
from .schema import parse_request


MINIMUM_GRADES = {
    LifecycleState.DESCRIBED: EvidenceGrade.NONE,
    LifecycleState.BUILT: EvidenceGrade.ARTIFACT,
    LifecycleState.TESTED: EvidenceGrade.TEST_RESULT,
    LifecycleState.STORED: EvidenceGrade.ARTIFACT,
    LifecycleState.REGISTERED: EvidenceGrade.PROVIDER_RECEIPT,
    LifecycleState.INSTALLED: EvidenceGrade.PROVIDER_RECEIPT,
    LifecycleState.BOUND: EvidenceGrade.PROVIDER_RECEIPT,
    LifecycleState.DEPLOYED: EvidenceGrade.PROVIDER_RECEIPT,
    LifecycleState.RUNNING: EvidenceGrade.INDEPENDENT_READBACK,
    LifecycleState.READ_BACK: EvidenceGrade.INDEPENDENT_READBACK,
    LifecycleState.ACCEPTED: EvidenceGrade.OWNER_ACCEPTED,
}


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _admissible(evidence: Evidence) -> bool:
    if not evidence.current or not evidence.passed:
        return False
    if evidence.grade < MINIMUM_GRADES[evidence.supports_state]:
        return False
    if evidence.supports_state >= LifecycleState.RUNNING and not (evidence.semantic or evidence.independent):
        return False
    if evidence.supports_state == LifecycleState.ACCEPTED and evidence.grade != EvidenceGrade.OWNER_ACCEPTED:
        return False
    return True


class RealityGuard:
    """Deterministic, fail-closed claim-versus-proof evaluator."""

    schema_version = "realityguard.scan.v1"

    def scan(self, payload: dict[str, Any]) -> ScanResult:
        claim, evidence, context = parse_request(payload)
        usable = [item for item in evidence if _admissible(item)]
        proven = max((item.supports_state for item in usable), default=LifecycleState.DESCRIBED)
        grade = max((item.grade for item in usable), default=EvidenceGrade.NONE)
        findings = evaluate(claim, evidence, context, proven)
        critical = any(item.severity == "CRITICAL" for item in findings)
        high = any(item.severity == "HIGH" for item in findings)
        scope_required = set(map(str, context.get("required_scope", claim.scope)))
        scope_observed = set(map(str, context.get("observed_scope", ())))
        scope_missing = sorted(scope_required - scope_observed)

        if critical or (claim.ownership_asserted and proven < LifecycleState.READ_BACK):
            verdict = Verdict.BLOCK_FALSE_REALITY
        elif claim.completion_asserted and (claim.claimed_state > proven or scope_missing):
            verdict = Verdict.BLOCK_COMPLETION
        elif context.get("owner_decision_required"):
            verdict = Verdict.REQUIRE_OWNER_DECISION
        elif findings:
            verdict = Verdict.REWRITE_REQUIRED
        else:
            verdict = Verdict.ALLOW_BOUNDED

        subject = claim.subject
        if claim.claimed_state == proven and not findings:
            safe = f"{subject}: {proven.name} is supported by the supplied current evidence; no broader state is asserted."
        else:
            safe = f"{subject}: evidence currently supports {proven.name}, not {claim.claimed_state.name}."
            if scope_missing:
                safe += f" Unverified scope: {', '.join(scope_missing)}."
        return ScanResult(
            schema_version=self.schema_version,
            correlation_id="rg-" + hashlib.sha256(_canonical(payload).encode()).hexdigest()[:20],
            verdict=verdict,
            claimed_state=claim.claimed_state,
            proven_state=proven,
            proof_grade=grade,
            state_gap=max(0, int(claim.claimed_state) - int(proven)),
            findings=findings,
            safe_statement=safe,
            missing_proof_gates=missing_gates(proven, claim.claimed_state),
            evidence_used=[item.reference or item.kind for item in usable],
            coverage={
                "required": sorted(scope_required),
                "observed": sorted(scope_observed),
                "missing": scope_missing,
                "complete": not scope_missing if scope_required else None,
            },
        )

    def resolve(self, payload: dict[str, Any], capability_manifest: dict[str, Any]) -> dict[str, Any]:
        """Adjudicate truth, then independently route the preserved objective."""
        from .capability import CapabilityRegistry
        from .solutions import SolutionRouter

        scan = self.scan(payload)
        registry = CapabilityRegistry.from_dict(capability_manifest)
        solution_payload = payload.get("solution")
        if not isinstance(solution_payload, dict):
            from .schema import InputError
            raise InputError("solution must be an object")
        decision = SolutionRouter().route(scan, solution_payload, registry)
        return {"truth": scan.to_dict(), "solution": decision.to_dict()}

    def prebuild(self, payload: dict[str, Any], capability_manifest: dict[str, Any]) -> dict[str, Any]:
        """Fail closed before code construction unless reuse or exact gap proof permits it."""
        from .prebuild import PrebuildGate

        return PrebuildGate().evaluate(payload, capability_manifest).to_dict()

    def upgrade(self, payload: dict[str, Any], capability_manifest: dict[str, Any]) -> dict[str, Any]:
        """Automatically assess one host-invoked material lifecycle boundary."""
        from .upgrade import GovernedUpgradeEngine

        return GovernedUpgradeEngine().evaluate(payload, capability_manifest).to_dict()
