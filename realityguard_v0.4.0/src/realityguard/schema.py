"""Strict, dependency-free input parsing and validation."""

from __future__ import annotations

from typing import Any

from .model import Claim, Evidence, EvidenceGrade, LifecycleState


class InputError(ValueError):
    pass


def _enum(enum_type: type, raw: Any, field: str):
    if not isinstance(raw, str):
        raise InputError(f"{field} must be a string")
    try:
        return enum_type[raw.strip().upper()]
    except KeyError as exc:
        options = ", ".join(item.name for item in enum_type)
        raise InputError(f"{field} must be one of: {options}") from exc


def _strings(raw: Any, field: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(v, str) for v in raw):
        raise InputError(f"{field} must be an array of strings")
    return tuple(dict.fromkeys(v.strip() for v in raw if v.strip()))


def parse_request(payload: Any) -> tuple[Claim, list[Evidence], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise InputError("input must be a JSON object")
    raw_claim = payload.get("claim")
    if not isinstance(raw_claim, dict):
        raise InputError("claim must be an object")
    text = raw_claim.get("text")
    if not isinstance(text, str) or not text.strip():
        raise InputError("claim.text must be a non-empty string")
    claim = Claim(
        text=text.strip(),
        claimed_state=_enum(LifecycleState, raw_claim.get("claimed_state", "DESCRIBED"), "claim.claimed_state"),
        subject=str(raw_claim.get("subject", "unspecified")).strip() or "unspecified",
        scope=_strings(raw_claim.get("scope"), "claim.scope"),
        completion_asserted=bool(raw_claim.get("completion_asserted", False)),
        ownership_asserted=bool(raw_claim.get("ownership_asserted", False)),
        capability_asserted=bool(raw_claim.get("capability_asserted", False)),
    )
    raw_evidence = payload.get("evidence", [])
    if not isinstance(raw_evidence, list):
        raise InputError("evidence must be an array")
    evidence: list[Evidence] = []
    for index, item in enumerate(raw_evidence):
        if not isinstance(item, dict):
            raise InputError(f"evidence[{index}] must be an object")
        evidence.append(Evidence(
            kind=str(item.get("kind", "UNSPECIFIED")).strip().upper(),
            supports_state=_enum(LifecycleState, item.get("supports_state", "DESCRIBED"), f"evidence[{index}].supports_state"),
            grade=_enum(EvidenceGrade, item.get("grade", "SELF_REPORTED"), f"evidence[{index}].grade"),
            reference=str(item.get("reference", "")).strip(),
            scope=_strings(item.get("scope"), f"evidence[{index}].scope"),
            passed=bool(item.get("passed", True)),
            current=bool(item.get("current", True)),
            semantic=bool(item.get("semantic", False)),
            independent=bool(item.get("independent", False)),
        ))
    context = payload.get("context", {})
    if not isinstance(context, dict):
        raise InputError("context must be an object")
    return claim, evidence, context
