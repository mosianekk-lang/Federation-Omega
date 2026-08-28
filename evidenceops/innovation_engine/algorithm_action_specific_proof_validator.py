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
    generic_health_keys = {
        "health", "healthy", "ok", "status", "service", "service_name",
        "version", "runtime", "uptime", "timestamp", "ts", "message",
    }
    health_actions = {
        "HEALTH", "STATUS", "RUNTIME_HEALTH", "HEALTH_CHECK", "GET_HEALTH",
    }
    wrapper_actions = {
        "RUNTIME_EXECUTE", "EXECUTE", "RUN_COMMAND", "DISPATCH",
    }
    semantic_action_fields = (
        "semantic_action", "requested_capability", "requested_operation", "inner_action",
    )
    returned_semantic_fields = (
        "semantic_action", "returned_capability", "returned_operation", "inner_action",
    )

    @staticmethod
    def _first_text(source: Mapping[str, Any], fields: Sequence[str]) -> str:
        for field in fields:
            value = text(source.get(field))
            if value:
                return value
        return ""

    @classmethod
    def _looks_like_structured_health(cls, value: Any) -> bool:
        if not isinstance(value, Mapping) or not value:
            return False
        keys = {text(key).lower() for key in value.keys() if text(key)}
        if not keys:
            return False
        health_markers = {"health", "healthy", "ok", "status", "service", "service_name"}
        return bool(keys & health_markers) and keys.issubset(cls.generic_health_keys)

    @staticmethod
    def _readback_fields(value: Any) -> set[str]:
        if not isinstance(value, Mapping):
            return set()
        return {text(key).lower() for key in value.keys() if text(key)}

    def run(self, action: Mapping[str, Any], proof: Mapping[str, Any]) -> AlgorithmResult:
        violations: list[str] = []
        required_action = text(action.get("action"))
        action_id = text(action.get("action_id"))
        target_id = text(action.get("target_id"))
        returned_action = text(proof.get("action"))
        returned_target = text(proof.get("target_id"))
        raw_response = proof.get("provider_response")
        response = text(raw_response).lower()
        readback = proof.get("target_readback")
        semantic_match = proof.get("semantic_match") is True
        executed = proof.get("executed") is True
        semantic_action = self._first_text(action, self.semantic_action_fields)
        returned_semantic = self._first_text(proof, self.returned_semantic_fields)
        required_readback_fields = tuple(
            field.lower() for field in unique_text(sequence(action.get("required_readback_fields")))
        )
        readback_fields = self._readback_fields(readback)
        missing_readback_fields = tuple(
            field for field in required_readback_fields if field not in readback_fields
        )

        for field, value in (
            ("ACTION_ID", action_id), ("REQUESTED_ACTION", required_action),
            ("TARGET_ID", target_id), ("PROVIDER_RESPONSE", raw_response),
            ("TARGET_READBACK", readback), ("CHECKED_AT", proof.get("checked_at")),
        ):
            if value in (None, "", [], {}):
                violations.append(f"MISSING_{field}")

        if returned_action != required_action:
            violations.append("ACTION_SEMANTICS_MISMATCH")
        if returned_target != target_id:
            violations.append("TARGET_IDENTITY_MISMATCH")

        required_action_upper = required_action.upper()
        if any(term == response or response.startswith(term + " ") for term in self.generic_terms):
            violations.append("GENERIC_HEALTH_OR_QUEUE_RESPONSE_NOT_ACTION_PROOF")
        if required_action_upper not in self.health_actions and (
            self._looks_like_structured_health(raw_response)
            or self._looks_like_structured_health(readback)
        ):
            violations.append("GENERIC_HEALTH_OBJECT_NOT_ACTION_PROOF")

        if required_action_upper in self.wrapper_actions:
            if not semantic_action:
                violations.append("WRAPPER_ACTION_MISSING_SEMANTIC_INTENT")
            elif returned_semantic != semantic_action:
                violations.append("INNER_ACTION_SEMANTICS_MISMATCH")
        elif semantic_action and returned_semantic != semantic_action:
            violations.append("INNER_ACTION_SEMANTICS_MISMATCH")

        if missing_readback_fields:
            violations.append("MISSING_REQUIRED_READBACK_FIELDS")
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
                "semantic_action": semantic_action,
                "returned_semantic_action": returned_semantic,
                "target_id": target_id,
                "returned_target_id": returned_target,
                "required_readback_fields": required_readback_fields,
                "missing_readback_fields": missing_readback_fields,
                "executed": executed,
                "semantic_match": semantic_match,
                "promotion_permitted": passed,
            },
            violations=tuple(sorted(set(violations))),
            metrics={"proof_complete": 1.0 if passed else 0.0},
            evidence_refs=tuple(unique_text(sequence(proof.get("evidence_refs")))),
        )
