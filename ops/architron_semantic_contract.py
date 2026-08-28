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

ACTION_CONTRACTS = {
    "GET_RUNTIME_IDENTITY": {
        "key": "runtimeIdentity",
        "kind": "mapping",
        "nested_any": {"principal", "serviceAccount", "identitySource"},
    },
    "GET_PROJECT_INFO": {
        "key": "projectInfo",
        "kind": "mapping",
        "nested_all": {"projectId", "projectNumber"},
    },
    "GET_CLOUD_RUN_SERVICE": {
        "key": "service",
        "kind": "mapping",
        "nested_all": {"name", "region"},
        "nested_any": {"url", "latestReadyRevision"},
    },
    "LIST_CLOUD_RUN_SERVICES": {"key": "services", "kind": "list"},
    "LIST_CLOUD_BUILD_BUILDS": {"key": "builds", "kind": "list"},
    "LIST_CLOUD_SCHEDULER_JOBS": {"key": "jobs", "kind": "list"},
    "LIST_CLOUD_SCHEDULER_JOBS_ALL_REGIONS": {"key": "jobs", "kind": "list"},
    "LIST_PUBSUB_TOPICS": {"key": "topics", "kind": "list"},
    "LIST_SERVICE_ACCOUNTS": {"key": "serviceAccounts", "kind": "list"},
    "LIST_SECRET_NAMES": {"key": "secretNames", "kind": "list"},
}


class SemanticContractError(ValueError):
    """Raised when provider transport succeeds but semantic proof is missing."""


def _payload_body(response: Mapping[str, Any]) -> Mapping[str, Any]:
    body = response.get("body", response)
    if not isinstance(body, Mapping):
        raise SemanticContractError("provider body is not an object")
    return body


def _validate_value(action: str, value: Any, contract: Mapping[str, Any]) -> None:
    kind = contract.get("kind")
    if kind == "list" and not isinstance(value, list):
        raise SemanticContractError(f"{action} action-specific value is not a list")
    if kind != "mapping":
        return
    if not isinstance(value, Mapping):
        raise SemanticContractError(f"{action} action-specific value is not an object")

    observed = set(value)
    required_all = set(contract.get("nested_all", set()))
    missing = required_all - observed
    if missing:
        raise SemanticContractError(
            f"{action} missing required provider fields: {sorted(missing)}"
        )

    required_any = set(contract.get("nested_any", set()))
    if required_any and not (required_any & observed):
        raise SemanticContractError(
            f"{action} requires at least one provider field from: {sorted(required_any)}"
        )


def validate_action_response(action: str, response: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the action body only when its semantic contract is satisfied.

    HTTP 2xx, DONE, or generic runtime health is transport proof only. Provider
    actions must return their own typed payload before they may be promoted.
    """

    normalized = str(action or "").strip().upper()
    contract = ACTION_CONTRACTS.get(normalized)
    if not contract:
        raise SemanticContractError(f"unsupported semantic action: {normalized}")

    body = _payload_body(response)
    observed = set(body)
    action_key = str(contract["key"])

    if GENERIC_HEALTH_KEYS.issubset(observed) and action_key not in observed:
        raise SemanticContractError(
            f"{normalized} collapsed to generic runtime health; action-specific proof absent"
        )

    if action_key not in body:
        raise SemanticContractError(
            f"{normalized} missing action-specific key: {action_key}"
        )

    _validate_value(normalized, body[action_key], contract)
    return body
