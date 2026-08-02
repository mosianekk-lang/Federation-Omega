"""Executor guard for EvidenceOps lesson KDV-L017."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


def _blocked(classification: str, gate: object = None) -> dict[str, Any]:
    issues: list[str] = []
    if isinstance(gate, Mapping) and isinstance(gate.get("issues"), list):
        issues = sorted({str(item) for item in gate["issues"]})
    return {
        "decision": "BLOCKED",
        "classification": classification,
        "gateIssues": issues,
        "referenceUpdateCalled": False,
        "lesson": "KDV-L017",
    }


def execute_kdv_l017_sequence(
    *,
    create_object: Callable[[], Mapping[str, Any]],
    build_gate_context: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    evaluate_gate: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    read_current_reference: Callable[[], str],
    expected_reference_object_id: str,
    update_reference: Callable[..., Any],
) -> dict[str, Any]:
    """Create an object and update a dependent ref only after a KDV-L017 ALLOW.

    Any missing ID, exception, malformed result, BLOCK decision, or missing
    KDV-L017 attestation fails closed before ``update_reference`` is called.
    """

    try:
        created = create_object()
    except Exception:
        return _blocked("OBJECT_CREATE_FAILED")
    if not isinstance(created, Mapping):
        return _blocked("OBJECT_CREATE_RESPONSE_INVALID")
    object_id = created.get("objectId")
    if not isinstance(object_id, str) or not object_id.strip():
        return _blocked("OBJECT_ID_REQUIRED")

    try:
        context = build_gate_context(created)
        if not isinstance(context, Mapping):
            return _blocked("KDV_L017_CONTEXT_INVALID")
        gate = evaluate_gate(context)
    except Exception:
        return _blocked("KDV_L017_GATE_FAILED")
    if not isinstance(gate, Mapping):
        return _blocked("KDV_L017_GATE_RESPONSE_INVALID")
    if gate.get("decision") != "ALLOW":
        return _blocked("REFERENCE_UPDATE_BLOCKED_BY_KDV_L017", gate)
    lessons = gate.get("lessonsApplied")
    if not isinstance(lessons, list) or "KDV-L017" not in lessons:
        return _blocked("KDV_L017_ATTESTATION_REQUIRED", gate)

    if not isinstance(expected_reference_object_id, str) or not expected_reference_object_id.strip():
        return _blocked("EXPECTED_REFERENCE_OBJECT_ID_REQUIRED", gate)
    try:
        current_reference_object_id = read_current_reference()
    except Exception:
        return _blocked("REFERENCE_READBACK_FAILED", gate)
    if current_reference_object_id != expected_reference_object_id:
        return _blocked("REFERENCE_MOVED_AFTER_STRUCTURAL_VERIFICATION", gate)

    try:
        update_result = update_reference(object_id, force=False)
    except Exception:
        return {
            "decision": "FAILED",
            "classification": "REFERENCE_UPDATE_FAILED",
            "referenceUpdateCalled": True,
            "lesson": "KDV-L017",
        }
    return {
        "decision": "COMPLETE",
        "classification": "REFERENCE_UPDATED_AFTER_KDV_L017_ALLOW",
        "referenceUpdateCalled": True,
        "updateResultPresent": update_result is not None,
        "lesson": "KDV-L017",
    }
