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
    semantic_envelope_targets = {
        "LIVE_READBACK",
        "FEDERATION_VERIFIED",
        "RELEASED",
    }

    @staticmethod
    def _require_verified_mapping(
        proof: Mapping[str, Any], field: str, violations: list[str]
    ) -> Mapping[str, Any] | None:
        value = proof.get(field)
        if not isinstance(value, Mapping):
            violations.append(f"INVALID_PROOF_ENVELOPE:{field}")
            return None
        if value.get("verified") is not True:
            violations.append(f"PROOF_ENVELOPE_NOT_VERIFIED:{field}")
        return value

    def _semantic_envelope_violations(
        self, *, target: str, proof: Mapping[str, Any]
    ) -> list[str]:
        """Validate direct high-proof jumps beyond mere token presence.

        These checks are intentionally conservative and local. They prevent a
        non-empty label from masquerading as a receipt/readback/approval but do
        not claim provider, federation, owner or release truth. Those external
        semantics still require independent proof and readback in their owning
        control planes.
        """

        violations: list[str] = []
        if target == "LIVE_READBACK":
            receipt = self._require_verified_mapping(proof, "execution_receipt", violations)
            readback = self._require_verified_mapping(proof, "target_readback", violations)
            if receipt is not None:
                if not text(receipt.get("receipt_id")):
                    violations.append("MISSING_RECEIPT_ID:execution_receipt")
                if not text(receipt.get("target_id")):
                    violations.append("MISSING_TARGET_ID:execution_receipt")
                if receipt.get("executed") is not True:
                    violations.append("EXECUTION_NOT_PROVEN:execution_receipt")
                if receipt.get("semantic_match") is not True:
                    violations.append("SEMANTIC_MATCH_NOT_PROVEN:execution_receipt")
            if readback is not None:
                if not text(readback.get("target_id")):
                    violations.append("MISSING_TARGET_ID:target_readback")
                if receipt is not None and text(receipt.get("target_id")) != text(readback.get("target_id")):
                    violations.append("TARGET_IDENTITY_MISMATCH")

        elif target == "FEDERATION_VERIFIED":
            receipt = self._require_verified_mapping(proof, "federation_receipt", violations)
            scope = self._require_verified_mapping(proof, "member_scope_proof", violations)
            trust_test = self._require_verified_mapping(proof, "no_trust_transfer_test", violations)
            if receipt is not None:
                if not text(receipt.get("receipt_id")):
                    violations.append("MISSING_RECEIPT_ID:federation_receipt")
                if not text(receipt.get("system_id")):
                    violations.append("MISSING_SYSTEM_ID:federation_receipt")
            if scope is not None:
                members = unique_text(sequence(scope.get("members")))
                if not members:
                    violations.append("MISSING_MEMBER_SCOPE")
                if not text(scope.get("scope_ref")):
                    violations.append("MISSING_SCOPE_REF")
            if trust_test is not None and trust_test.get("passed") is not True:
                violations.append("NO_TRUST_TRANSFER_TEST_NOT_PASSED")

        elif target == "RELEASED":
            approval = self._require_verified_mapping(proof, "owner_approval", violations)
            receipt = self._require_verified_mapping(proof, "release_receipt", violations)
            readback = self._require_verified_mapping(proof, "target_readback", violations)
            if approval is not None:
                for key in ("approved_by", "approved_at", "scope"):
                    if not text(approval.get(key)):
                        violations.append(f"MISSING_OWNER_APPROVAL_FIELD:{key}")
            if receipt is not None:
                if not text(receipt.get("receipt_id")):
                    violations.append("MISSING_RECEIPT_ID:release_receipt")
                if not text(receipt.get("artifact_id")):
                    violations.append("MISSING_ARTIFACT_ID:release_receipt")
            if readback is not None:
                if not text(readback.get("artifact_id")):
                    violations.append("MISSING_ARTIFACT_ID:target_readback")
                if receipt is not None and text(receipt.get("artifact_id")) != text(readback.get("artifact_id")):
                    violations.append("RELEASE_ARTIFACT_IDENTITY_MISMATCH")

        return violations

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
        if target in self.semantic_envelope_targets and not missing:
            violations.extend(self._semantic_envelope_violations(target=target, proof=proof))
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
                "semantic_envelope_required": target in self.semantic_envelope_targets,
                "transition_permitted": permitted,
                "promotion_rule": "state names and non-empty proof labels never substitute for target-specific semantic proof",
            },
            violations=tuple(sorted(set(violations))),
            metrics={"proof_coverage": (len(required) - len(missing)) / len(required) if required else 1.0},
            evidence_refs=tuple(unique_text(sequence(proof.get("evidence_refs")))),
        )
