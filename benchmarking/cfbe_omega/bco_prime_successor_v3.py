"""Additive BCO-Prime successor registry for flight, harvesting and adaptation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import bco_prime_adaptive_intelligence_v1 as adaptive
    from . import bco_prime_chat_forensics_v2 as v2
    from . import bco_prime_flight_recorder_v3 as flight
    from . import bco_prime_harvesting_fabric_v1 as harvest
except ImportError:  # pragma: no cover - direct script execution
    import bco_prime_adaptive_intelligence_v1 as adaptive
    import bco_prime_chat_forensics_v2 as v2
    import bco_prime_flight_recorder_v3 as flight
    import bco_prime_harvesting_fabric_v1 as harvest


SCHEMA = "BCO_PRIME_SUCCESSOR_V3"
VERSION = "3.0.0"
SUCCESSOR_OPERATIONS = (
    "BCO-PRIME-V3-MANIFEST",
    "BCO-PRIME-V3-FLIGHT-MANIFEST",
    "BCO-PRIME-V3-FLIGHT-APPEND",
    "BCO-PRIME-V3-FLIGHT-VERIFY",
    "BCO-PRIME-V3-FLIGHT-REPLAY",
    "BCO-PRIME-V3-FLIGHT-CHECKPOINT",
    "BCO-PRIME-V3-HARVEST-MANIFEST",
    "BCO-PRIME-V3-HARVEST-RADAR",
    "BCO-PRIME-V3-OPPORTUNITY-GRAPH",
    "BCO-PRIME-V3-COMPILE-CANDIDATE",
    "BCO-PRIME-V3-QUALIFY-SHADOW",
    "BCO-PRIME-V3-ADAPTIVE-MANIFEST",
    "BCO-PRIME-V3-ADAPTIVE-EVALUATE",
    "BCO-PRIME-V3-META-DEPENDENCY-CLOSURE",
)
META_DEPENDENCIES = ("MISSION_IR", "DURABLE_MISSION_RUNTIME", "PROOF_OS")


class SuccessorContractError(ValueError):
    pass


def _strict_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise SuccessorContractError(f"{field} must be a Boolean")
    return value


def _strict_int(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise SuccessorContractError(f"{field} must be an integer in range")
    return value


def _safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise SuccessorContractError("path must be non-empty and relative")
    candidate = (root.resolve() / relative).resolve()
    if candidate != root.resolve() and root.resolve() not in candidate.parents:
        raise SuccessorContractError("path traversal rejected")
    return candidate


def meta_dependency_closure(root: Path, dependencies: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for dependency_id in META_DEPENDENCIES:
        spec = dependencies.get(dependency_id, {})
        relative = spec.get("path")
        expected = spec.get("expected_sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            observations.append({"dependency_id": dependency_id, "state": "ABSENT", "reason": "PINNED_PATH_AND_SHA256_REQUIRED"})
            continue
        target = _safe_path(root, relative)
        if not target.is_file():
            observations.append({"dependency_id": dependency_id, "state": "ABSENT", "reason": "FILE_NOT_FOUND"})
            continue
        observed = v2.file_sha256(target)
        state = "VERIFIED" if observed == expected else "HASH_MISMATCH"
        observations.append({"dependency_id": dependency_id, "state": state, "expected_sha256": expected, "observed_sha256": observed})
    ready = all(item["state"] == "VERIFIED" for item in observations)
    result = {
        "schema": "BCO_PRIME_META_DEPENDENCY_CLOSURE_V1",
        "state": "READY" if ready else "BLOCKED_WITH_ROUTE",
        "dependencies": observations,
        "fullMetaRuntimeReady": ready,
        "safeSubsetReady": True,
        "closureTest": "Supply all three genuine local artifacts with exact SHA-256 pins, pass their native tests, then rerun this operation and the full meta compiler without stubs.",
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = v2.digest(result)
    return result


class SuccessorRegistry:
    def __init__(self, workspace_root: Path, base_registry: v2.UnifiedRegistry | None = None) -> None:
        self.workspace_root = workspace_root.resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.base = base_registry or v2.UnifiedRegistry()

    def health(self) -> dict[str, Any]:
        base_health = self.base.health()
        result = {
            "schema": SCHEMA,
            "version": VERSION,
            "base": base_health,
            "canonical_core_count": base_health["core_count"],
            "canonical_core_invariant_preserved": base_health["core_count"] == 100,
            "successor_operation_count": len(SUCCESSOR_OPERATIONS),
            "successor_operations": list(SUCCESSOR_OPERATIONS),
            "runtimeState": "ON_DEMAND_GOVERNED",
            "externalMutationAuthorized": False,
            "stablePromotionAuthorized": False,
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }
        result["health_sha256"] = v2.digest(result)
        return result

    def manifest(self) -> dict[str, Any]:
        result = self.health()
        result["components"] = {
            "flight": flight.manifest(),
            "harvesting": harvest.manifest(),
            "adaptive": adaptive.manifest(),
        }
        result["manifest_sha256"] = v2.digest(result)
        return result

    def execute(self, operation: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        clean = v2._normalize(v2._mapping(payload or {}, "$.payload"))
        v2._reject_external_effects(clean)
        if operation not in SUCCESSOR_OPERATIONS:
            return self.base.execute(operation, clean)
        namespace = "successor_v3"
        if operation == "BCO-PRIME-V3-MANIFEST":
            output = self.manifest()
        elif operation == "BCO-PRIME-V3-FLIGHT-MANIFEST":
            output = flight.manifest()
        elif operation.startswith("BCO-PRIME-V3-FLIGHT-"):
            recorder = flight.FlightRecorder(_safe_path(self.workspace_root, str(clean.get("recorder_root", "flight"))))
            if operation == "BCO-PRIME-V3-FLIGHT-APPEND":
                output = recorder.append(v2._mapping(clean.get("event", {}), "$.payload.event"))
            elif operation == "BCO-PRIME-V3-FLIGHT-VERIFY":
                output = recorder.verify()
            elif operation == "BCO-PRIME-V3-FLIGHT-REPLAY":
                output = recorder.replay()
            else:
                output = recorder.checkpoint(str(clean.get("checkpoint_path", "flight_checkpoint_v3.json")))
        elif operation == "BCO-PRIME-V3-HARVEST-MANIFEST":
            output = harvest.manifest()
        elif operation == "BCO-PRIME-V3-HARVEST-RADAR":
            scan_root = _safe_path(self.workspace_root, str(clean.get("scan_root", "sources")))
            radar = harvest.CapabilityRadar(
                scan_root,
                clean.get("authorized_source_ids", []),
                max_file_bytes=_strict_int(clean.get("max_file_bytes", harvest.DEFAULT_MAX_FILE_BYTES), "max_file_bytes", minimum=1, maximum=16 * 1024 * 1024),
                max_files=_strict_int(clean.get("max_files", harvest.DEFAULT_MAX_FILES), "max_files", minimum=1, maximum=100_000),
            )
            output = radar.scan(str(clean.get("source_id", "")), str(clean.get("tenant_id", "")), str(clean.get("matter_id", "")))
        elif operation == "BCO-PRIME-V3-OPPORTUNITY-GRAPH":
            output = harvest.build_opportunity_graph(clean.get("records", []))
        elif operation == "BCO-PRIME-V3-COMPILE-CANDIDATE":
            output = harvest.compile_candidate(v2._mapping(clean.get("graph", {}), "$.payload.graph"), clean.get("selected_ids", []))
        elif operation == "BCO-PRIME-V3-QUALIFY-SHADOW":
            output = harvest.qualify_shadow_candidate(
                v2._mapping(clean.get("candidate", {}), "$.payload.candidate"),
                clean.get("paired_cases", []),
                rollback_available=_strict_bool(clean.get("rollback_available", False), "rollback_available"),
                independent_verifier_pass=_strict_bool(clean.get("independent_verifier_pass", False), "independent_verifier_pass"),
            )
        elif operation == "BCO-PRIME-V3-ADAPTIVE-MANIFEST":
            output = adaptive.manifest()
        elif operation == "BCO-PRIME-V3-ADAPTIVE-EVALUATE":
            raw_candidate = v2._mapping(clean.get("candidate", {}), "$.payload.candidate")
            candidate = adaptive.PolicyCandidate(
                candidate_id=str(raw_candidate.get("candidate_id", "")),
                operation=str(raw_candidate.get("operation", "")),
                policy=str(raw_candidate.get("policy", "")),
                evidence_ids=tuple(raw_candidate.get("evidence_ids", [])),
                reversible=_strict_bool(raw_candidate.get("reversible", False), "candidate.reversible"),
                effect_class=str(raw_candidate.get("effect_class", "LOCAL_SHADOW")),
            )
            output = adaptive.paired_evaluate(
                candidate,
                clean.get("cases", []),
                rollback_available=_strict_bool(clean.get("rollback_available", False), "rollback_available"),
                independent_verifier_pass=_strict_bool(clean.get("independent_verifier_pass", False), "independent_verifier_pass"),
            )
        else:
            output = meta_dependency_closure(self.workspace_root, v2._mapping(clean.get("dependencies", {}), "$.payload.dependencies"))
        receipt = {
            "schema": "BCO_PRIME_SUCCESSOR_EXECUTION_RECEIPT_V3",
            "version": VERSION,
            "namespace": namespace,
            "operation": operation,
            "input_sha256": v2.digest(clean),
            "output": v2._normalize(output),
            "providerEffectAuthorized": False,
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }
        receipt["receipt_sha256"] = v2.digest(receipt)
        return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=SCHEMA)
    parser.add_argument("--workspace-root", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health")
    sub.add_parser("manifest")
    run = sub.add_parser("run")
    run.add_argument("operation")
    run.add_argument("--payload-json", default="{}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    registry = SuccessorRegistry(Path(args.workspace_root))
    if args.command == "health":
        output = registry.health()
    elif args.command == "manifest":
        output = registry.manifest()
    else:
        output = registry.execute(args.operation, json.loads(args.payload_json))
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["META_DEPENDENCIES", "SUCCESSOR_OPERATIONS", "SuccessorRegistry", "meta_dependency_closure"]
