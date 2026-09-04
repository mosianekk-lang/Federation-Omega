from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json

from .models import CompletionDecision, CompletionEvidence
from .objective import ObjectiveContract


class CompletionTheorem:
    def evaluate(self, contract: ObjectiveContract, evidence: CompletionEvidence) -> CompletionDecision:
        defects: list[str] = []
        if evidence.objective_fingerprint != contract.fingerprint:
            defects.append("OBJECTIVE_FINGERPRINT_MISMATCH")
        missing = set(contract.mandatory_requirements) - set(evidence.satisfied_requirements)
        defects.extend(f"UNSATISFIED_REQUIREMENT:{x}" for x in sorted(missing))
        failed = set(contract.acceptance_tests) - set(evidence.passed_acceptance_tests)
        defects.extend(f"FAILED_ACCEPTANCE_TEST:{x}" for x in sorted(failed))
        missing_inv = set(contract.invariants) - set(evidence.preserved_invariants)
        defects.extend(f"UNPROVEN_INVARIANT:{x}" for x in sorted(missing_inv))
        if evidence.unresolved_contradictions:
            defects.append("UNRESOLVED_CONTRADICTIONS")
        if not evidence.rollback_viable:
            defects.append("ROLLBACK_UNPROVEN")
        if not evidence.within_budget:
            defects.append("BURDEN_OR_BUDGET_EXCEEDED")
        if "live external effects" in contract.mandatory_requirements and not evidence.native_effect_readbacks:
            defects.append("NATIVE_EFFECT_READBACK_MISSING")
        payload = {"contract": contract.fingerprint, "evidence": asdict(evidence), "defects": defects}
        proof_hash = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return CompletionDecision(not defects, tuple(defects), proof_hash)
