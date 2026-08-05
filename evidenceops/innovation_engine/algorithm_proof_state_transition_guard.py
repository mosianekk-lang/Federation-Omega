from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class ProofStateTransitionGuard:
    algorithm_id = "ALG-EOPS-PSTG-001"
    name = "Proof-State Transition Guard"

    states = (
        "NO_EVIDENCE", "INFERRED", "USER_CONFIRMED", "SOURCE_SUPPORTED",
        "DESIGN_ONLY", "CREATED_LOCALLY", "STORED_IN_REPOSITORY",
        "STATICALLY_VALIDATED", "STAGED_NOT_RUNNING", "DIRECT_CONNECTOR_ACTIVE",
        "CREATED_AND_READ_BACK", "CONTROL_LOG_VERIFIED", "PROTOTYPE_PASSED",
        "SIMULATION_PASSED", "LIVE_READBACK", "RED_TEAM_PASSED",
        "USER_VERIFIED", "WORKFLOW_VERIFIED", "AUTONOMOUS_RUNTIME_VERIFIED",
        "FEDERATION_VERIFIED", "RELEASED",
    )
    proof_requirements: Mapping[str, tuple[str, ...]] = {
        "SOURCE_SUPPORTED": ("source_evidence",),
        "CREATED_LOCALLY": ("artifact_hash",),
        "STORED_IN_REPOSITORY": ("repository_readback",),
        "STATICALLY_VALIDATED": ("validation_receipt",),
        "DIRECT_CONNECTOR_ACTIVE": ("connector_receipt", "target_readback"),
        "CREATED_AND_READ_BACK": ("artifact_hash", "target_readback"),
        "CONTROL_LOG_VERIFIED": ("control_log", "target_readback"),
        "PROTOTYPE_PASSED": ("prototype_receipt", "rollback_test"),
        "SIMULATION_PASSED": ("simulation_receipt", "failure_path_test", "rollback_test"),
        "LIVE_READBACK": ("execution_receipt", "target_readback"),
        "RED_TEAM_PASSED": ("red_team_receipt",),
        "USER_VERIFIED": ("user_verification",),
        "WORKFLOW_VERIFIED": ("workflow_receipt", "target_readback", "rollback_test"),
        "AUTONOMOUS_RUNTIME_VERIFIED": ("runtime_receipt", "recurrence_receipt", "fresh_logs", "target_readback", "rollback_test"),
        "FEDERATION_VERIFIED": ("federation_receipt", "member_scope_proof", "no_trust_transfer_test"),
        "RELEASED": ("owner_approval", "release_receipt", "target_readback"),
    }
    direct_evidence_targets = set(proof_requirements)

    def run(self, *, current_state: str, target_state: str, proof: Mapping[str, Any]) -> AlgorithmResult:
        current = text(current_state).upper()
        target = text(target_state).upper()
        violations: list[str] = []
        if current not in self.states:
            violations.append("UNKNOWN_CURRENT_STATE")
        if target not in self.states:
            violations.append("UNKNOWN_TARGET_STATE")
        required = self.proof_requirements.get(target, ())
        missing = [field for field in required if proof.get(field) in (None, "", [], {})]
        violations.extend(f"MISSING_PROOF:{field}" for field in missing)
        state_skip_detected = False
        if current in self.states and target in self.states:
            distance = self.states.index(target) - self.states.index(current)
            state_skip_detected = distance > 3
            if distance < 0 and target not in {"NO_EVIDENCE", "INFERRED"}:
                violations.append("UNEXPLAINED_MATURITY_DOWNGRADE")
            if state_skip_detected and target not in self.direct_evidence_targets:
                violations.append("UNJUSTIFIED_MULTI_STATE_JUMP")
            if state_skip_detected and target in self.direct_evidence_targets and missing:
                violations.append("DIRECT_PROOF_JUMP_INCOMPLETE")
        permitted = not violations
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status="TRANSITION_PERMITTED" if permitted else "TRANSITION_BLOCKED",
            maturity="TESTED_LOCAL",
            output={
                "current_state": current,
                "target_state": target,
                "required_proof": list(required),
                "missing_proof": missing,
                "state_skip_detected": state_skip_detected,
                "transition_permitted": permitted,
                "promotion_rule": "state names never substitute for target-specific proof",
            },
            violations=tuple(sorted(set(violations))),
            metrics={"proof_coverage": (len(required) - len(missing)) / len(required) if required else 1.0},
            evidence_refs=tuple(unique_text(sequence(proof.get("evidence_refs")))),
        )
