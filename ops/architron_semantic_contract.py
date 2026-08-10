"""Fail-closed semantic validator for the existing Architron /execute route.

This module does not deploy or mutate Google Cloud. It defines the minimum
provider payload that must be observed before an action-specific command may be
promoted beyond transport success.
"""

from __future__ import annotations

from typing import Any, Mapping


GENERIC_HEALTH_KEYS = {
    "runtime",
    "version",
    "cloudRunService",
    "project",
    "healthOk",
}

ACTION_REQUIRED_KEYS = {
    "GET_RUNTIME_IDENTITY": {"runtimeIdentity"},
    "GET_PROJECT_INFO": {"projectInfo"},
    "GET_CLOUD_RUN_SERVICE": {"service"},
}


class SemanticContractError(ValueError):
    """Raised when provider transport succeeds but semantic proof is missing."""


def _payload_body(response: Mapping[str, Any]) -> Mapping[str, Any]:
    body = response.get("body", response)
    if not isinstance(body, Mapping):
        raise SemanticContractError("provider body is not an object")
    return body


def validate_action_response(action: str, response: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the action body only when its semantic contract is satisfied.

    HTTP 2xx, DONE, or generic health is insufficient for the three provider
    proof actions used by the KAIO canary.
    """

    normalized = str(action or "").strip().upper()
    required = ACTION_REQUIRED_KEYS.get(normalized)
    if not required:
        raise SemanticContractError(f"unsupported semantic action: {normalized}")

    body = _payload_body(response)
    observed = set(body)

    # Explicitly reject the exact failure mode observed on 9 August 2026.
    if GENERIC_HEALTH_KEYS.issubset(observed) and not (required & observed):
        raise SemanticContractError(
            f"{normalized} collapsed to generic runtime health; action-specific proof absent"
        )

    missing = required - observed
    if missing:
        raise SemanticContractError(
            f"{normalized} missing action-specific keys: {sorted(missing)}"
        )

    return body
