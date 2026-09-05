"""Strict additive registry for BCO-Prime successor v3.1."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import bco_prime_baseline_registry_v3_1 as baseline
    from . import bco_prime_cycle_v3_1 as cycle
    from . import bco_prime_drift_harvest_v3_1 as drift
    from . import bco_prime_successor_v3 as v3
except ImportError:  # pragma: no cover
    import bco_prime_baseline_registry_v3_1 as baseline
    import bco_prime_cycle_v3_1 as cycle
    import bco_prime_drift_harvest_v3_1 as drift
    import bco_prime_successor_v3 as v3


SCHEMA = "BCO_PRIME_SUCCESSOR_V3_1"
VERSION = "3.1.0"
SUCCESSOR_OPERATIONS_V3_1 = (
    "BCO-PRIME-V3-1-MANIFEST",
    "BCO-PRIME-V3-1-BASELINE-VERIFY",
    "BCO-PRIME-V3-1-DRIFT-CHECK",
    "BCO-PRIME-V3-1-INCREMENTAL-SCAN",
    "BCO-PRIME-V3-1-HARVEST-DIFF",
    "BCO-PRIME-V3-1-SHADOW-REPAIR-PLAN",
    "BCO-PRIME-V3-1-REGRESSION-SCOREBOARD",
    "BCO-PRIME-V3-1-CYCLE-RUN",
    "BCO-PRIME-V3-1-CONTROL-POINTER-ROLLBACK",
)
_FORBIDDEN_EFFECT_KEYS = {
    "externaleffect",
    "providereffect",
    "providereffectauthorized",
    "authorityexpansion",
    "network",
    "deploy",
    "registerlive",
    "stablepromotionauthorized",
    "sourceMutationAuthorized".lower(),
    "exec",
    "eval",
    "subprocess",
}


class SuccessorV31ContractError(ValueError):
    pass


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _strict_normalize(value: Any, path: str = "$") -> Any:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if value != value or value in (float("inf"), float("-inf")):
            raise SuccessorV31ContractError(f"non-finite number at {path}")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise SuccessorV31ContractError(f"non-string key at {path}")
            item = value[key]
            if _normalized_key(key) in {_normalized_key(name) for name in _FORBIDDEN_EFFECT_KEYS} and item not in (None, False, 0, "", [], {}):
                raise SuccessorV31ContractError(f"external or executable effect rejected at {path}.{key}")
            result[key] = _strict_normalize(item, f"{path}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [_strict_normalize(item, f"{path}[]") for item in value]
    raise SuccessorV31ContractError(f"unsupported input at {path}: {type(value).__name__}")


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SuccessorV31ContractError(f"{field} must be an object")
    return value


def _strict_int(value: Any, field: str, *, minimum: int = 0, maximum: int = 10_000_000) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise SuccessorV31ContractError(f"{field} must be an integer in range")
    return value


def _strict_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise SuccessorV31ContractError(f"{field} must be a Boolean")
    return value


def _safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise SuccessorV31ContractError("path must be a non-empty relative path")
    candidate = (root.resolve() / relative).resolve()
    if candidate != root.resolve() and root.resolve() not in candidate.parents:
        raise SuccessorV31ContractError("path traversal rejected")
    return candidate


def _load_json(root: Path, relative: str) -> Mapping[str, Any]:
    target = _safe_path(root, relative)
    if not target.is_file() or target.is_symlink():
        raise SuccessorV31ContractError("JSON input file is unavailable")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SuccessorV31ContractError("JSON input file is invalid") from exc
    return _mapping(value, relative)


class SuccessorRegistryV31:
    def __init__(self, workspace_root: Path, base_registry: v3.SuccessorRegistry | None = None) -> None:
        self.workspace_root = workspace_root.resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.base = base_registry or v3.SuccessorRegistry(self.workspace_root / "v3-base")

    def health(self) -> dict[str, Any]:
        old = self.base.health()
        result = {
            "schema": SCHEMA,
            "version": VERSION,
            "base": old,
            "canonical_core_count": old["canonical_core_count"],
            "canonical_core_invariant_preserved": old["canonical_core_invariant_preserved"],
            "v3_operation_count": old["successor_operation_count"],
            "v3_1_operation_count": len(SUCCESSOR_OPERATIONS_V3_1),
            "v3_1_operations": list(SUCCESSOR_OPERATIONS_V3_1),
            "runtimeState": "ON_DEMAND_GOVERNED",
            "baselineSigningTrustRootRequired": True,
            "baselineAutoAdvanceAuthorized": False,
            "quarantineAutoClearAuthorized": False,
            "sourceMutationAuthorized": False,
            "externalMutationAuthorized": False,
            "stablePromotionAuthorized": False,
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }
        result["health_sha256"] = drift.digest(result)
        return result

    def manifest(self) -> dict[str, Any]:
        result = self.health()
        result["components"] = {
            "baseline_registry": {"schema": baseline.SCHEMA, "version": baseline.VERSION, "signature_algorithm": baseline.SIGNATURE_ALGORITHM},
            "drift_harvest": {"schema": drift.SCHEMA, "version": drift.VERSION},
            "cycle": {"schema": cycle.SCHEMA, "version": cycle.VERSION},
        }
        result["manifest_sha256"] = drift.digest(result)
        return result

    def execute(self, operation: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        clean = _strict_normalize(dict(payload or {}))
        if operation not in SUCCESSOR_OPERATIONS_V3_1:
            return self.base.execute(operation, clean)
        if operation == "BCO-PRIME-V3-1-MANIFEST":
            output = self.manifest()
        elif operation == "BCO-PRIME-V3-1-BASELINE-VERIFY":
            envelope = _load_json(self.workspace_root, str(clean.get("baseline_path", "")))
            output = baseline.verify_signed_baseline(
                envelope,
                expected_public_key_fingerprint=str(clean.get("expected_public_key_fingerprint") or "") or None,
                minimum_generation=_strict_int(clean.get("minimum_generation", 1), "minimum_generation", minimum=1),
                expected_parent_baseline_sha256=str(clean.get("expected_parent_baseline_sha256")) if clean.get("expected_parent_baseline_sha256") is not None else None,
            )
        elif operation == "BCO-PRIME-V3-1-DRIFT-CHECK":
            envelope = _load_json(self.workspace_root, str(clean.get("baseline_path", "")))
            output = drift.detect_drift(
                envelope,
                root=_safe_path(self.workspace_root, str(clean.get("monitored_root", ""))),
                expected_public_key_fingerprint=str(clean.get("expected_public_key_fingerprint") or "") or None,
                minimum_generation=_strict_int(clean.get("minimum_generation", 1), "minimum_generation", minimum=1),
                policies=_mapping(clean.get("policies", {}), "policies"),
                capabilities=list(clean.get("capabilities", [])),
                test_results=_mapping(clean.get("test_results", {}), "test_results"),
                result_assertions=_mapping(clean.get("result_assertions", {}), "result_assertions"),
                coverage_complete=_strict_bool(clean.get("coverage_complete"), "coverage_complete"),
            )
        elif operation == "BCO-PRIME-V3-1-INCREMENTAL-SCAN":
            scanner = drift.IncrementalCapabilityScanner(
                _safe_path(self.workspace_root, str(clean.get("scan_root", ""))),
                source_id=str(clean.get("source_id") or ""),
                tenant_id=str(clean.get("tenant_id") or ""),
                matter_id=str(clean.get("matter_id") or ""),
                baseline_sha256=str(clean.get("baseline_sha256") or ""),
                max_files=_strict_int(clean.get("max_files", 1000), "max_files", minimum=1, maximum=100_000),
                max_file_bytes=_strict_int(clean.get("max_file_bytes", 1024 * 1024), "max_file_bytes", minimum=1, maximum=16 * 1024 * 1024),
                max_total_bytes=_strict_int(clean.get("max_total_bytes", 32 * 1024 * 1024), "max_total_bytes", minimum=1, maximum=128 * 1024 * 1024),
                max_depth=_strict_int(clean.get("max_depth", 16), "max_depth", minimum=1, maximum=64),
                dependency_licenses=_mapping(clean.get("dependency_licenses", {}), "dependency_licenses"),
            )
            output = scanner.scan(cancelled=_strict_bool(clean.get("cancelled", False), "cancelled"))
        elif operation == "BCO-PRIME-V3-1-HARVEST-DIFF":
            output = drift.diff_capability_scans(
                _mapping(clean.get("previous", {}), "previous"),
                _mapping(clean.get("current", {}), "current"),
            )
        elif operation == "BCO-PRIME-V3-1-SHADOW-REPAIR-PLAN":
            output = drift.shadow_repair_plan(_mapping(clean.get("drift_report", {}), "drift_report"), str(clean.get("baseline_sha256") or ""))
        elif operation == "BCO-PRIME-V3-1-REGRESSION-SCOREBOARD":
            output = drift.regression_scoreboard(
                _mapping(clean.get("drift_report", {}), "drift_report"),
                previous_state=str(clean.get("previous_state")) if clean.get("previous_state") is not None else None,
            )
        elif operation == "BCO-PRIME-V3-1-CYCLE-RUN":
            envelope = _load_json(self.workspace_root, str(clean.get("baseline_path", "")))
            runner = cycle.GovernedCycleRunner(_safe_path(self.workspace_root, str(clean.get("cycle_root", "cycles"))))
            output = runner.run(
                cycle_id=str(clean.get("cycle_id") or ""),
                mission_id=str(clean.get("mission_id") or ""),
                mission_version=_strict_int(clean.get("mission_version"), "mission_version", minimum=1),
                cancel_token=_mapping(clean.get("cancel_token", {}), "cancel_token"),
                baseline_envelope=envelope,
                monitored_root=_safe_path(self.workspace_root, str(clean.get("monitored_root", ""))),
                expected_public_key_fingerprint=str(clean.get("expected_public_key_fingerprint") or "") or None,
                minimum_generation=_strict_int(clean.get("minimum_generation", 1), "minimum_generation", minimum=1),
                policies=_mapping(clean.get("policies", {}), "policies"),
                capabilities=list(clean.get("capabilities", [])),
                test_results=_mapping(clean.get("test_results", {}), "test_results"),
                result_assertions=_mapping(clean.get("result_assertions", {}), "result_assertions"),
                coverage_complete=_strict_bool(clean.get("coverage_complete"), "coverage_complete"),
                previous_scoreboard_state=str(clean.get("previous_scoreboard_state")) if clean.get("previous_scoreboard_state") is not None else None,
                current_scan=_mapping(clean.get("current_scan"), "current_scan") if clean.get("current_scan") is not None else None,
                previous_scan=_mapping(clean.get("previous_scan"), "previous_scan") if clean.get("previous_scan") is not None else None,
            )
        else:
            output = cycle.rollback_control_pointer(
                _safe_path(self.workspace_root, str(clean.get("control_root", "cycles"))),
                expected_current_baseline_sha256=str(clean.get("expected_current_baseline_sha256") or ""),
                target_baseline_path=str(clean.get("target_baseline_path") or ""),
                target_baseline_sha256=str(clean.get("target_baseline_sha256") or ""),
            )
        receipt = {
            "schema": "BCO_PRIME_SUCCESSOR_EXECUTION_RECEIPT_V3_1",
            "version": VERSION,
            "namespace": "successor_v3_1",
            "operation": operation,
            "input_sha256": drift.digest(clean),
            "output": _strict_normalize(output),
            "providerEffectAuthorized": False,
            "stablePromotionAuthorized": False,
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }
        receipt["receipt_sha256"] = drift.digest(receipt)
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
    registry = SuccessorRegistryV31(Path(args.workspace_root))
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


__all__ = ["SUCCESSOR_OPERATIONS_V3_1", "SuccessorRegistryV31", "SuccessorV31ContractError"]
