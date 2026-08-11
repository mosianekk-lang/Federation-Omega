from __future__ import annotations

from typing import Any

from .core import (
    FORBIDDEN_TRUE_KEYS,
    HELD_ACTIONS,
    INPUT_SCHEMA,
    all_values_for_key,
    ensure_hex_sha256,
)


class PacketValidationError(ValueError):
    """The packet is malformed or lacks a required proof boundary."""


class BoundaryViolation(PacketValidationError):
    """The packet attempts to cross an authority, case-wall or mutation boundary."""


REQUIRED_TOP_LEVEL = {
    "schema", "packet_id", "matter_id", "case_wall_id", "mission",
    "authority", "sources", "verified_facts", "claims", "chronology",
    "contradictions", "missing_records", "stakeholders", "strategies",
    "outcome_chain",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PacketValidationError(message)


def _require_string(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value


def _require_list(value: Any, field: str) -> list[Any]:
    _require(isinstance(value, list), f"{field} must be an array")
    return value


def _case_wall_check(value: Any, expected: str) -> None:
    for key in ("case_wall_id", "source_case_wall_id", "target_case_wall_id"):
        for observed in all_values_for_key(value, key):
            if observed != expected:
                raise BoundaryViolation(
                    f"case-wall mismatch at {key}: expected {expected!r}, received {observed!r}"
                )


def _matter_check(value: Any, expected: str) -> None:
    for key in ("matter_id", "source_matter_id", "target_matter_id"):
        for observed in all_values_for_key(value, key):
            if observed != expected:
                raise BoundaryViolation(
                    f"matter mismatch at {key}: expected {expected!r}, received {observed!r}"
                )


def _authority_check(packet: dict[str, Any]) -> None:
    authority = packet["authority"]
    _require(isinstance(authority, dict), "authority must be an object")
    if authority.get("tier") not in {"A0_READ", "A1_INTERNAL"}:
        raise BoundaryViolation("authority tier must remain A0_READ or A1_INTERNAL")

    for key in FORBIDDEN_TRUE_KEYS:
        for observed in all_values_for_key(packet, key):
            if observed is True:
                raise BoundaryViolation(f"{key}=true is prohibited by the read-only adapter")

    requested_actions: set[str] = set()
    for key in ("requested_actions", "actions", "operations"):
        for observed in all_values_for_key(packet, key):
            if isinstance(observed, list):
                requested_actions.update(str(item).upper() for item in observed)
            elif isinstance(observed, str):
                requested_actions.add(observed.upper())
    prohibited = sorted(requested_actions & HELD_ACTIONS)
    if prohibited:
        raise BoundaryViolation(f"held action requested: {', '.join(prohibited)}")


def _validate_sources(packet: dict[str, Any]) -> set[str]:
    source_ids: set[str] = set()
    for index, source in enumerate(_require_list(packet["sources"], "sources")):
        _require(isinstance(source, dict), f"sources[{index}] must be an object")
        source_id = _require_string(source.get("source_id"), f"sources[{index}].source_id")
        if source_id in source_ids:
            raise PacketValidationError(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)
        _require_string(source.get("case_wall_id"), f"sources[{index}].case_wall_id")
        source_hash = _require_string(source.get("sha256"), f"sources[{index}].sha256")
        _require(
            ensure_hex_sha256(source_hash),
            f"sources[{index}].sha256 must be 64 hexadecimal characters",
        )
        _require_string(source.get("classification"), f"sources[{index}].classification")
    return source_ids


def _validate_facts(packet: dict[str, Any], source_ids: set[str]) -> set[str]:
    fact_ids: set[str] = set()
    for index, fact in enumerate(_require_list(packet["verified_facts"], "verified_facts")):
        _require(isinstance(fact, dict), f"verified_facts[{index}] must be an object")
        fact_id = _require_string(fact.get("fact_id"), f"verified_facts[{index}].fact_id")
        if fact_id in fact_ids:
            raise PacketValidationError(f"duplicate fact_id: {fact_id}")
        fact_ids.add(fact_id)
        _require_string(fact.get("statement"), f"verified_facts[{index}].statement")
        if fact.get("verification_state") != "VERIFIED":
            raise PacketValidationError(f"verified_facts[{index}] is not VERIFIED")
        refs = _require_list(fact.get("source_refs"), f"verified_facts[{index}].source_refs")
        _require(bool(refs), f"verified_facts[{index}].source_refs cannot be empty")
        unknown = sorted(set(refs) - source_ids)
        if unknown:
            raise PacketValidationError(
                f"verified_facts[{index}] references unknown sources: {unknown}"
            )
    return fact_ids


def _validate_claims(packet: dict[str, Any], fact_ids: set[str]) -> None:
    claim_ids: set[str] = set()
    for index, claim in enumerate(_require_list(packet["claims"], "claims")):
        _require(isinstance(claim, dict), f"claims[{index}] must be an object")
        claim_id = _require_string(claim.get("claim_id"), f"claims[{index}].claim_id")
        if claim_id in claim_ids:
            raise PacketValidationError(f"duplicate claim_id: {claim_id}")
        claim_ids.add(claim_id)
        _require_string(claim.get("statement"), f"claims[{index}].statement")
        refs = claim.get("fact_refs", [])
        _require(isinstance(refs, list), f"claims[{index}].fact_refs must be an array")
        unknown = sorted(set(refs) - fact_ids)
        if unknown:
            raise PacketValidationError(f"claims[{index}] references unknown facts: {unknown}")
        state = claim.get("support_state", "UNVERIFIED")
        if state not in {"SUPPORTED", "PARTIALLY_SUPPORTED", "UNVERIFIED", "CONTRADICTED"}:
            raise PacketValidationError(f"invalid support_state for {claim_id}: {state}")


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(packet, dict):
        raise PacketValidationError("packet must be an object")
    missing = sorted(REQUIRED_TOP_LEVEL - set(packet))
    if missing:
        raise PacketValidationError(f"missing required top-level fields: {missing}")
    if packet.get("schema") != INPUT_SCHEMA:
        raise PacketValidationError(f"schema must equal {INPUT_SCHEMA}")

    _require_string(packet["packet_id"], "packet_id")
    matter_id = _require_string(packet["matter_id"], "matter_id")
    case_wall_id = _require_string(packet["case_wall_id"], "case_wall_id")
    _require(isinstance(packet["mission"], dict), "mission must be an object")
    _require_string(packet["mission"].get("objective"), "mission.objective")
    _require_string(packet["mission"].get("requested_outcome"), "mission.requested_outcome")

    for field in (
        "chronology", "contradictions", "missing_records", "stakeholders",
        "strategies", "outcome_chain",
    ):
        _require_list(packet[field], field)

    _case_wall_check(packet, case_wall_id)
    _matter_check(packet, matter_id)
    _authority_check(packet)
    source_ids = _validate_sources(packet)
    fact_ids = _validate_facts(packet, source_ids)
    _validate_claims(packet, fact_ids)
    return packet
