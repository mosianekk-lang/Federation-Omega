#!/usr/bin/env python3
"""Local MODISA Code-Forge v3.3 build-contract validator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


COMPONENTS = {
    "frontend", "backend", "database", "queue", "worker", "scheduler",
    "cache", "storage", "authentication",
}
FAILURES = {
    "INVALID_INPUT", "AUTHORIZATION_FAILURE", "TIMEOUT", "PARTIAL_WRITE",
    "MISSING_CONFIGURATION", "EXTERNAL_API_FAILURE",
}


def _at(data, *path):
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _present(value):
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def validate(data, require_proof=False):
    errors = []
    if data.get("contract_version") != "3.3":
        errors.append("contract_version must equal 3.3")
    mission = data.get("mission") if isinstance(data.get("mission"), dict) else {}
    for key in (
        "id", "version", "goal", "user", "workflow", "data", "interface",
        "stack", "environment", "maturity", "governance", "failure", "testing",
        "deployment", "continuity",
    ):
        if not _present(mission.get(key)):
            errors.append(f"mission.{key} is required")
    if mission.get("maturity") not in {"PROTOTYPE", "MVP", "PROD_FOUNDATION", "PROD_HARDENED"}:
        errors.append("mission.maturity is invalid")
    if not _present(data.get("classification")):
        errors.append("classification is required")
    for key in ("stack", "runtime", "storage", "authentication", "deployment"):
        if not _present((data.get("assumptions") or {}).get(key)):
            errors.append(f"assumptions.{key} is required")
    components = _at(data, "architecture", "components") or {}
    for key in sorted(COMPONENTS):
        if not _present(components.get(key)):
            errors.append(f"architecture.components.{key} is unresolved")
    modes = _at(data, "architecture", "failure_modes")
    if not isinstance(modes, list):
        errors.append("architecture.failure_modes must be an array")
    else:
        missing = sorted(FAILURES - set(modes))
        if missing:
            errors.append("failure modes missing: " + ", ".join(missing))
    for key in ("correlation_ids", "health_checks", "structured_logs", "audit_logs", "metrics_alerts"):
        if not _present(_at(data, "architecture", "observability", key)):
            errors.append(f"architecture.observability.{key} is required")
    for key in ("unit", "integration", "e2e_or_smoke", "fixtures_mocks", "failure_first", "commands"):
        if not _present(_at(data, "testing", key)):
            errors.append(f"testing.{key} is required")
    for key in (
        "file_tree", "exact_code_files", "setup_commands", "run_commands",
        "test_commands", "deploy_commands", "rollback_commands", "debugging",
    ):
        if not _present(_at(data, "delivery", key)):
            errors.append(f"delivery.{key} is required")
    formation = data.get("formation") or {}
    if formation.get("gate_decision") != "EXECUTE":
        errors.append("formation.gate_decision must equal EXECUTE")
    if formation.get("single_effectful_path") is not True:
        errors.append("formation.single_effectful_path must be true")
    for key in ("mission_id", "mission_version", "authority_class", "effectful_permit"):
        if not _present(formation.get(key)):
            errors.append(f"formation.{key} is required")
    for key in ("idempotency", "checkpoints", "resume_conditions", "handoff_files", "stop_switch"):
        if not _present(_at(data, "continuity", key)):
            errors.append(f"continuity.{key} is required")
    states = data.get("states") or {}
    for key in ("designed", "implemented", "tested", "registered", "authorized", "ready", "deployed", "proven"):
        if not isinstance(states.get(key), bool):
            errors.append(f"states.{key} must be boolean")
    if states.get("tested") and not _present(_at(data, "proof", "test_results")):
        errors.append("tested=true requires proof.test_results")
    if states.get("deployed") and not _present(_at(data, "proof", "deployment_readback")):
        errors.append("deployed=true requires proof.deployment_readback")
    if states.get("proven"):
        if not _present(_at(data, "proof", "semantic_verification")):
            errors.append("proven=true requires proof.semantic_verification")
        if _at(data, "proof", "unresolved_defects") not in ([], None):
            errors.append("proven=true requires zero unresolved defects")
    if require_proof:
        for key in ("test_results", "semantic_verification"):
            if not _present(_at(data, "proof", key)):
                errors.append(f"--require-proof requires proof.{key}")
        if _at(data, "proof", "unresolved_defects") not in ([], None):
            errors.append("--require-proof requires zero unresolved defects")
    return sorted(set(errors))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("--require-proof", action="store_true")
    args = parser.parse_args()
    try:
        payload = json.loads(args.contract.read_text(encoding="utf-8"))
        errors = validate(payload, args.require_proof) if isinstance(payload, dict) else ["root must be an object"]
    except (OSError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
