from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class ActionSpecificProofValidator:
    algorithm_id = "ALG-EOPS-ASPV-001"
    name = "Action-Specific Proof Validator"

    generic_terms = {
        "health", "healthy", "ok", "running", "service alive", "http 200",
        "queued", "dispatched", "accepted", "configuration loaded",
    }

    def run(self, action: Mapping[str, Any], proof: Mapping[str, Any]) -> AlgorithmResult:
        violations: list[str] = []
        required_action = text(action.get("action"))
        action_id = text(action.get("action_id"))
        target_id = text(action.get("target_id"))
        returned_action = text(proof.get("action"))
        returned_target = text(proof.get("target_id"))
        response = text(proof.get("provider_response")).lower()
        readback = proof.get("target_readback")
        semantic_match = proof.get("semantic_match") is True
        executed = proof.get("executed") is True
        for field, value in (
            ("ACTION_ID", action_id), ("REQUESTED_ACTION", required_action),
            ("TARGET_ID", target_id), ("PROVIDER_RESPONSE", proof.get("provider_response")),
            ("TARGET_READBACK", readback), ("CHECKED_AT", proof.get("checked_at")),
        ):
            if value in (None, "", [], {}):
                violations.append(f"MISSING_{field}")
        if returned_action != required_action:
            violations.append("ACTION_SEMANTICS_MISMATCH")
        if returned_target != target_id:
            violations.append("TARGET_IDENTITY_MISMATCH")
        if any(term == response or response.startswith(term + " ") for term in self.generic_terms):
            violations.append("GENERIC_HEALTH_OR_QUEUE_RESPONSE_NOT_ACTION_PROOF")
        if not executed:
            violations.append("EXECUTION_NOT_PROVEN")
        if not semantic_match:
            violations.append("SEMANTIC_READBACK_MISMATCH")
        passed = not violations
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status="ACTION_SPECIFIC_PROOF_PASSED" if passed else "ACTION_PROOF_REJECTED",
            maturity="TESTED_LOCAL",
            output={
                "action_id": action_id,
                "requested_action": required_action,
                "returned_action": returned_action,
                "target_id": target_id,
                "returned_target_id": returned_target,
                "executed": executed,
                "semantic_match": semantic_match,
                "promotion_permitted": passed,
            },
            violations=tuple(sorted(set(violations))),
            metrics={"proof_complete": 1.0 if passed else 0.0},
            evidence_refs=tuple(unique_text(sequence(proof.get("evidence_refs")))),
        )
