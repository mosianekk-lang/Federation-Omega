from __future__ import annotations

"""Deterministic, additive BCO-Prime chat-forensics capability pack v1.

This module analyzes evidence already captured by authorized adapters. It has
no network, browser, filesystem, provider, clock, subprocess, or user-input
effect. Raw evidence is represented by hashes and bounded metadata in receipts.
"""

from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence

from . import bco_prime_capability_fabric_v1 as core


SCHEMA = "BCO_PRIME_CHAT_FORENSICS_V1"
RECEIPT_SCHEMA = "BCO_PRIME_CHAT_FORENSICS_RECEIPT_V1"
CAPABILITY_COUNT = 24
AUTHORITY_CEILING = "A1_INTERNAL"

DOMAIN_OPERATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("acquisition", ("bind_conversation_identity", "inventory_sources", "rank_sources", "capability_probe")),
    ("normalization", ("scope_filter", "fallback_route", "canonical_hash", "event_chain")),
    ("completion", ("timestamp_coverage", "terminal_event", "blank_turn", "trace_lineage")),
    ("failure", ("finalization_failure", "checkpoint_gap", "workload_pressure", "connector_pressure")),
    ("proof", ("error_provenance", "provider_durability", "claim_fruit", "cff_status")),
    ("recovery", ("shield_state", "recovery_plan", "audit_receipt", "harvest_summary")),
)

SOURCE_PRIORITY = {
    "native_export": 100,
    "provider_api": 90,
    "execution_trace": 85,
    "browser_dom": 80,
    "output_panel": 75,
    "console_log": 60,
    "screenshot": 40,
    "rendered_text": 35,
}


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    capability_id: str
    function_name: str
    domain: str
    operation: str
    ordinal: int


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)


def _hash(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else [value]
    return [" ".join(str(item).split()) for item in values if str(item).strip()]


def _items(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key, [])
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _boundary_guard(payload: Mapping[str, Any]) -> None:
    if payload.get("manual_user_tasks") not in (None, 0, [], ()):
        raise ValueError("CHAT_FORENSICS_BOUNDARY:MANUAL_USER_TASK_PROHIBITED")
    for key in ("external_effect", "provider_effect_authorized", "authority_expansion"):
        if payload.get(key) is True:
            raise ValueError(f"CHAT_FORENSICS_BOUNDARY:{key.upper()}_PROHIBITED")


def _acquisition(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "bind_conversation_identity":
        expected_id = str(p.get("expected_id", "")).strip()
        observed_id = str(p.get("observed_id", "")).strip()
        expected_title = str(p.get("expected_title", "")).strip()
        observed_title = str(p.get("observed_title", "")).strip()
        if not expected_id or expected_id != observed_id:
            raise ValueError("CONVERSATION_ID_MISMATCH")
        if expected_title and expected_title != observed_title:
            raise ValueError("CONVERSATION_TITLE_MISMATCH")
        return {"bound": True, "conversation_id_sha256": _hash(expected_id), "title_sha256": _hash(expected_title)}
    sources = _items(p, "sources")
    if operation == "inventory_sources":
        inventory = [
            {
                "source_id": str(item.get("source_id", "")),
                "kind": str(item.get("kind", "unknown")),
                "accessible": bool(item.get("accessible")),
                "captured": bool(item.get("captured")),
                "hash_present": bool(item.get("sha256")),
            }
            for item in sources
        ]
        return {"sources": sorted(inventory, key=lambda x: x["source_id"]), "source_count": len(inventory)}
    if operation == "rank_sources":
        ranked = sorted(
            (
                {
                    "source_id": str(item.get("source_id", "")),
                    "kind": str(item.get("kind", "unknown")),
                    "priority": SOURCE_PRIORITY.get(str(item.get("kind", "unknown")), 0),
                    "captured": bool(item.get("captured")),
                }
                for item in sources
            ),
            key=lambda x: (-x["priority"], x["source_id"]),
        )
        return {"ranked_sources": ranked, "best_available": next((x["source_id"] for x in ranked if x["captured"]), None)}
    probes = _items(p, "probes")
    unavailable = sorted(str(item.get("capability")) for item in probes if not item.get("supported"))
    return {
        "supported": sorted(str(item.get("capability")) for item in probes if item.get("supported")),
        "unavailable": unavailable,
        "fallback_required": bool(unavailable),
    }


def _normalization(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "scope_filter":
        target = str(p.get("conversation_id", ""))
        evidence = _items(p, "evidence")
        accepted = sorted(str(item.get("evidence_id")) for item in evidence if str(item.get("conversation_id", "")) == target)
        rejected = sorted(str(item.get("evidence_id")) for item in evidence if str(item.get("conversation_id", "")) != target)
        return {"accepted_ids": accepted, "rejected_ids": rejected, "scope_clean": not rejected}
    if operation == "fallback_route":
        available = set(_strings(p.get("available_kinds")))
        if "native_export" in available:
            route = "NATIVE_EXPORT"
        elif {"browser_dom", "execution_trace"} <= available:
            route = "BROWSER_DOM_TRACE"
        elif "rendered_text" in available:
            route = "RENDERED_TEXT_PARTIAL"
        else:
            route = "AUDIT_BLOCKED"
        return {"route": route, "native_export": "native_export" in available, "fallback_used": route != "NATIVE_EXPORT"}
    if operation == "canonical_hash":
        return {"canonical_sha256": _hash(p.get("value")), "algorithm": "sha256-canonical-json"}
    events = _items(p, "events")
    previous = "0" * 64
    chained: list[dict[str, Any]] = []
    for index, event in enumerate(events, 1):
        content_sha = str(event.get("content_sha256") or _hash(event.get("content", "")))
        draft = {"event_id": str(event.get("event_id") or f"EV-{index:06d}"), "content_sha256": content_sha, "previous_event_hash": previous}
        event_hash = _hash(draft)
        chained.append({**draft, "event_hash": event_hash})
        previous = event_hash
    return {"events": chained, "event_count": len(chained), "chain_head": previous, "tamper_evident": True}


def _completion(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "timestamp_coverage":
        total = max(0, int(p.get("message_count", 0) or 0))
        native = max(0, min(total, int(p.get("native_timestamp_count", 0) or 0)))
        return {"coverage": round(native / total, 9) if total else 0.0, "native_timestamps": native, "message_count": total}
    if operation == "terminal_event":
        user = bool(p.get("user_final_message_present"))
        assistant = bool(p.get("assistant_terminal_content_present"))
        if user and assistant:
            state = "COMPLETE_VISIBLE"
        elif user and not assistant:
            state = "BLANK_ASSISTANT_TERMINAL"
        else:
            state = "INSUFFICIENT"
        return {"terminal_state": state, "user_final_message_present": user, "assistant_terminal_content_present": assistant}
    if operation == "blank_turn":
        detected = bool(p.get("user_final_message_present")) and not bool(p.get("assistant_terminal_content_present"))
        return {"blank_terminal_turn": detected, "evidence_bounded": True}
    steps = _items(p, "steps")
    normalized = [
        {"step_id": str(step.get("step_id", "")), "kind": str(step.get("kind", "unknown")), "status": str(step.get("status", "UNKNOWN"))}
        for step in steps
    ]
    return {"steps": normalized, "step_count": len(normalized), "last_step": normalized[-1] if normalized else None}


def _failure(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "finalization_failure":
        detected = bool(p.get("final_tool_action_present")) and not bool(p.get("final_response_commit_observed"))
        server_cause = str(p.get("verified_server_cause") or "").strip()
        return {
            "detected": detected,
            "failure_class": "FINAL_OUTPUT_COMMIT_FAILURE" if detected else "NOT_DETECTED",
            "exact_backend_cause": server_cause if server_cause else "UNVERIFIED",
            "causal_ceiling": "OBSERVED_TERMINAL_SEQUENCE" if detected else "INSUFFICIENT",
        }
    if operation == "checkpoint_gap":
        required = set(_strings(p.get("required_checkpoints")))
        present = set(_strings(p.get("present_checkpoints")))
        missing = sorted(required - present)
        return {"missing_checkpoints": missing, "gap_detected": bool(missing), "checkpoint_complete": bool(required) and not missing}
    if operation == "workload_pressure":
        durations = [max(0, int(value)) for value in p.get("work_durations_seconds", []) if isinstance(value, (int, float))]
        threshold = max(1, int(p.get("pressure_threshold_seconds", 900) or 900))
        peak = max(durations, default=0)
        return {"peak_seconds": peak, "threshold_seconds": threshold, "pressure_observed": peak >= threshold, "causal_status": "POSSIBLE_CONTRIBUTOR_NOT_PROVEN"}
    sources = set(_strings(p.get("connector_sources")))
    errors = _items(p, "connector_errors")
    return {
        "connector_count": len(sources),
        "connector_error_count": len(errors),
        "pressure": "HIGH" if len(sources) >= 4 else "MODERATE" if len(sources) >= 2 else "LOW",
        "causal_status": "NOT_PROVEN",
    }


def _proof(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "error_provenance":
        errors = _items(p, "errors")
        rows = []
        for item in errors:
            stage = str(item.get("stage", "unknown"))
            terminal = bool(item.get("terminal_window")) and bool(item.get("server_confirmed"))
            rows.append({"error_id": str(item.get("error_id", "")), "stage": stage, "terminal_cause_supported": terminal})
        return {"errors": rows, "terminal_cause_supported": any(row["terminal_cause_supported"] for row in rows)}
    if operation == "provider_durability":
        matches = sorted(_strings(p.get("durable_artifact_matches")))
        pinned = bool(str(p.get("provider_ref", "")).strip())
        proven = pinned and bool(matches)
        return {"state": "PROVEN" if proven else "UNPROVEN", "artifact_match_count": len(matches), "provider_ref_bound": pinned}
    if operation == "claim_fruit":
        claimed = set(_strings(p.get("claimed_outputs")))
        proven = set(_strings(p.get("proven_outputs")))
        missing = sorted(claimed - proven)
        return {"missing_outputs": missing, "fruit_complete": bool(claimed) and not missing, "proven_outputs": sorted(claimed & proven)}
    raw = str(p.get("engine_state", "UNAVAILABLE"))
    native = bool(p.get("native_export")) and bool(p.get("native_message_ids")) and bool(p.get("native_timestamps"))
    captured = max(0, int(p.get("captured_source_count", 0) or 0))
    state = "COMPLETE_VERIFIED" if raw == "COMPLETE_VERIFIED" and native else "PARTIAL_CHECKPOINTED" if captured else "AUDIT_BLOCKED"
    return {"engine_state": raw, "audit_state": state, "native_telemetry_complete": native, "completion_claim_allowed": state == "COMPLETE_VERIFIED"}


def _recovery(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "shield_state":
        native = bool(p.get("native_export"))
        terminal = bool(p.get("terminal_sequence_captured"))
        durability = bool(p.get("provider_durability_proven"))
        state = 6 if native and terminal and durability else 4 if terminal else 2 if p.get("captured_source_count") else 0
        return {"shield_state": state, "maximum_state": 6, "promotion_blocked": state < 6}
    if operation == "recovery_plan":
        gaps = set(_strings(p.get("gaps")))
        actions = ["persist_local_checkpoint_before_finalization", "emit_finalization_receipt", "read_back_provider_durability"]
        if "native_export" in gaps:
            actions.insert(0, "capture_native_export_when_available")
        return {"actions": actions, "automatic_only": True, "manual_user_tasks": []}
    if operation == "audit_receipt":
        return {"audit_sha256": _hash(p.get("findings", {})), "evidence_sha256": _hash(p.get("evidence_refs", [])), "deterministic": True}
    sources = _items(p, "sources")
    accessible = [item for item in sources if item.get("accessible")]
    captured = [item for item in accessible if item.get("captured")]
    blocked = [item for item in sources if not item.get("accessible")]
    return {
        "source_count": len(sources),
        "accessible_count": len(accessible),
        "captured_count": len(captured),
        "blocked_count": len(blocked),
        "harvest_sha256": _hash(sorted(str(item.get("sha256", "")) for item in captured)),
    }


_EVALUATORS: Mapping[str, Callable[[str, Mapping[str, Any]], Mapping[str, Any]]] = {
    "acquisition": _acquisition,
    "normalization": _normalization,
    "completion": _completion,
    "failure": _failure,
    "proof": _proof,
    "recovery": _recovery,
}


def _build_specs() -> tuple[CapabilitySpec, ...]:
    specs: list[CapabilitySpec] = []
    ordinal = 0
    for domain, operations in DOMAIN_OPERATIONS:
        for operation in operations:
            ordinal += 1
            specs.append(CapabilitySpec(f"BCO-PRIME-CFF-CAP-{ordinal:03d}", f"cff_cap_{ordinal:03d}_{operation}", domain, operation, ordinal))
    if ordinal != CAPABILITY_COUNT:
        raise RuntimeError("BCO_PRIME_CHAT_FORENSICS_COUNT_INVALID")
    return tuple(specs)


CAPABILITY_SPECS = _build_specs()
_SPEC_BY_ID = {item.capability_id: item for item in CAPABILITY_SPECS}


def execute_capability(capability_id: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if capability_id not in _SPEC_BY_ID:
        raise KeyError(f"UNKNOWN_BCO_PRIME_CHAT_FORENSICS_CAPABILITY:{capability_id}")
    payload = {} if payload is None else payload
    if not isinstance(payload, Mapping):
        raise TypeError("CHAT_FORENSICS_PAYLOAD_MAPPING_REQUIRED")
    _boundary_guard(payload)
    spec = _SPEC_BY_ID[capability_id]
    output = dict(_EVALUATORS[spec.domain](spec.operation, payload))
    draft: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "capability_schema": SCHEMA,
        "capability_id": spec.capability_id,
        "function_name": spec.function_name,
        "domain": spec.domain,
        "operation": spec.operation,
        "status": "SUCCESS",
        "input_sha256": _hash(payload),
        "output": output,
        "authority_ceiling": AUTHORITY_CEILING,
        "authority_expansion": False,
        "external_effect": False,
        "provider_effect_authorized": False,
        "stable_self_promotion_authorized": False,
        "manual_user_tasks": [],
        "owner_action_required": False,
        "rollback": "NO_EFFECT_REPLAY_SAFE",
        "truth_boundary": "deterministic analysis of supplied evidence; no hidden telemetry or provider effect",
    }
    return {**draft, "receipt_sha256": _hash(draft)}


def _make_capability(spec: CapabilitySpec) -> Callable[[Mapping[str, Any] | None], dict[str, Any]]:
    def capability(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return execute_capability(spec.capability_id, payload)
    capability.__name__ = spec.function_name
    capability.__qualname__ = spec.function_name
    return capability


FUNCTION_REGISTRY: dict[str, Callable[[Mapping[str, Any] | None], dict[str, Any]]] = {}
for _spec in CAPABILITY_SPECS:
    _function = _make_capability(_spec)
    globals()[_spec.function_name] = _function
    FUNCTION_REGISTRY[_spec.capability_id] = _function


def capability_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability_count": len(CAPABILITY_SPECS),
        "extends": core.SCHEMA,
        "canonical_core_capability_count_unchanged": core.CAPABILITY_COUNT,
        "domains": {domain: len(operations) for domain, operations in DOMAIN_OPERATIONS},
        "capabilities": [asdict(item) for item in CAPABILITY_SPECS],
        "manual_user_tasks": [],
        "owner_action_required": False,
        "external_effect": False,
        "provider_effect_authorized": False,
        "authority_expansion": False,
    }


def audit_incident(bundle: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, Mapping):
        raise TypeError("INCIDENT_BUNDLE_MAPPING_REQUIRED")
    _boundary_guard(bundle)
    conversation = bundle.get("conversation", {}) if isinstance(bundle.get("conversation"), Mapping) else {}
    observations = bundle.get("observations", {}) if isinstance(bundle.get("observations"), Mapping) else {}
    provider = bundle.get("provider", {}) if isinstance(bundle.get("provider"), Mapping) else {}
    cff = bundle.get("cff", {}) if isinstance(bundle.get("cff"), Mapping) else {}
    sources = _items(bundle, "sources")
    receipts = [
        execute_capability("BCO-PRIME-CFF-CAP-001", {
            "expected_id": conversation.get("expected_id"), "observed_id": conversation.get("observed_id"),
            "expected_title": conversation.get("expected_title"), "observed_title": conversation.get("observed_title"),
        }),
        execute_capability("BCO-PRIME-CFF-CAP-002", {"sources": sources}),
        execute_capability("BCO-PRIME-CFF-CAP-003", {"sources": sources}),
        execute_capability("BCO-PRIME-CFF-CAP-006", {"available_kinds": [item.get("kind") for item in sources if item.get("captured")]}),
        execute_capability("BCO-PRIME-CFF-CAP-012", {"steps": observations.get("trace_steps", [])}),
        execute_capability("BCO-PRIME-CFF-CAP-013", {
            "final_tool_action_present": observations.get("final_tool_action_present"),
            "final_response_commit_observed": observations.get("final_response_commit_observed"),
            "verified_server_cause": observations.get("verified_server_cause"),
        }),
        execute_capability("BCO-PRIME-CFF-CAP-015", {"work_durations_seconds": observations.get("work_durations_seconds", [])}),
        execute_capability("BCO-PRIME-CFF-CAP-017", {"errors": observations.get("errors", [])}),
        execute_capability("BCO-PRIME-CFF-CAP-018", {
            "provider_ref": provider.get("provider_ref"), "durable_artifact_matches": provider.get("durable_artifact_matches", []),
        }),
        execute_capability("BCO-PRIME-CFF-CAP-019", {
            "claimed_outputs": observations.get("claimed_outputs", []), "proven_outputs": observations.get("proven_outputs", []),
        }),
        execute_capability("BCO-PRIME-CFF-CAP-020", {
            "engine_state": cff.get("engine_state"), "native_export": cff.get("native_export"),
            "native_message_ids": cff.get("native_message_ids"), "native_timestamps": cff.get("native_timestamps"),
            "captured_source_count": sum(1 for item in sources if item.get("captured")),
        }),
        execute_capability("BCO-PRIME-CFF-CAP-024", {"sources": sources}),
    ]
    by_operation = {receipt["operation"]: receipt for receipt in receipts}
    provider_state = by_operation["provider_durability"]["output"]["state"]
    cff_state = by_operation["cff_status"]["output"]["audit_state"]
    shield = execute_capability("BCO-PRIME-CFF-CAP-021", {
        "native_export": cff.get("native_export"),
        "terminal_sequence_captured": by_operation["finalization_failure"]["output"]["detected"],
        "provider_durability_proven": provider_state == "PROVEN",
        "captured_source_count": sum(1 for item in sources if item.get("captured")),
    })
    recovery = execute_capability("BCO-PRIME-CFF-CAP-022", {
        "gaps": ["native_export"] if not cff.get("native_export") else [],
    })
    core_receipts = [
        core.execute_capability("BCO-PRIME-CAP-017", {
            "source_id": conversation.get("expected_id"), "source_sha256": bundle.get("evidence_root_sha256") or _hash(sources),
        }),
        core.execute_capability("BCO-PRIME-CAP-019", {
            "required_proof": ["native_export", "terminal_response", "provider_durability"],
            "present_proof": bundle.get("present_proof", []),
        }),
        core.execute_capability("BCO-PRIME-CAP-004", {
            "desired_outputs": observations.get("claimed_outputs", []), "produced_outputs": observations.get("proven_outputs", []),
        }),
    ]
    finding = by_operation["finalization_failure"]["output"]
    draft: dict[str, Any] = {
        "schema": "BCO_PRIME_CHAT_FORENSICS_AUDIT_V1",
        "conversation_binding": receipts[0]["output"],
        "audit_state": cff_state,
        "primary_finding": finding["failure_class"],
        "primary_finding_confidence": "HIGH" if finding["detected"] else "INSUFFICIENT",
        "exact_backend_cause": finding["exact_backend_cause"],
        "provider_durability": provider_state,
        "shield": shield["output"],
        "recovery": recovery["output"],
        "extension_receipt_hashes": [receipt["receipt_sha256"] for receipt in receipts] + [shield["receipt_sha256"], recovery["receipt_sha256"]],
        "core_receipt_hashes": [receipt["receipt_sha256"] for receipt in core_receipts],
        "manual_user_tasks": [],
        "owner_action_required": False,
        "external_effect": False,
        "authority_expansion": False,
    }
    return {**draft, "audit_receipt_sha256": _hash(draft)}


def main() -> int:
    parser = ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    run = sub.add_parser("run")
    run.add_argument("capability_id")
    run.add_argument("--payload-json", default="{}")
    audit = sub.add_parser("audit")
    audit.add_argument("--payload-json", required=True)
    args = parser.parse_args()
    if args.command == "list":
        print(json.dumps(capability_manifest(), sort_keys=True))
    elif args.command == "run":
        print(json.dumps(execute_capability(args.capability_id, json.loads(args.payload_json)), sort_keys=True))
    else:
        print(json.dumps(audit_incident(json.loads(args.payload_json)), sort_keys=True))
    return 0


__all__ = ["CAPABILITY_COUNT", "CAPABILITY_SPECS", "FUNCTION_REGISTRY", "capability_manifest", "execute_capability", "audit_incident"] + [item.function_name for item in CAPABILITY_SPECS]


if __name__ == "__main__":
    raise SystemExit(main())
