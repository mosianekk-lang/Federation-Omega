#!/usr/bin/env python3
"""Deterministic package-local MODISA 3.3 and heartbeat invariant validator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

COMPONENTS = frozenset({"frontend", "backend", "database", "queue", "worker", "scheduler", "cache", "storage", "authentication"})
FAILURES = frozenset({"INVALID_INPUT", "AUTHORIZATION_FAILURE", "TIMEOUT", "PARTIAL_WRITE", "MISSING_CONFIGURATION", "EXTERNAL_API_FAILURE"})
MATURITY = "DURABLE_FOUNDATION_IMPLEMENTED_NOT_ATTACHED"
COMPATIBILITY_COMMAND = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest "
    "tests.test_atomic_transactions tests.test_connector_foundry "
    "tests.test_connector_foundry_google_drive tests.test_ecasp "
    "tests.test_innovation_engine_registry tests.test_operation_idempotency "
    "tests.test_provenance_passport tests.test_runtime tests.test_slrk "
    "tests.test_wif_hardening"
)
ADVERSARIAL_CONTROLS = frozenset(
    {
        "HB-AUTH-001",
        "HB-CLASS-001",
        "HB-RESPAWN-001",
        "HB-PATH-001",
        "HB-PRIV-001",
        "HB-PUBLIC-001",
        "HB-CONTRACT-001",
        "HB-LINEAGE-002",
        "HB-RECEIPT-ATTR-002",
        "HB-RESPAWN-SCOPE-002",
        "HB-PRIV-OBS-002",
        "HB-INHERIT-002",
        "HB-PROOF-002",
        "HB-PRIV-CODE-003",
        "HB-REPO-PATH-003",
        "HB-RECEIPT-FRESH-003",
        "HB-RESPAWN-FRESH-003",
        "HB-POLICY-HASH-003",
        "HB-GEN-MONOTONIC-003",
        "HB-JSON-DUPKEY-003",
        "HB-IMMUTABILITY-003",
    }
)


def at(value: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def validate(value: Any, *, require_proof: bool = False) -> list[str]:
    if not isinstance(value, dict):
        return ["root must be an object"]
    errors: list[str] = []
    if value.get("contract_version") != "3.3":
        errors.append("contract_version must equal 3.3")
    mission = value.get("mission") if isinstance(value.get("mission"), dict) else {}
    mission_keys = (
        "id", "version", "goal", "user", "workflow", "data", "interface", "stack",
        "environment", "maturity", "governance", "failure", "testing", "deployment", "continuity",
    )
    for key in mission_keys:
        if not present(mission.get(key)):
            errors.append(f"mission.{key} is required")
    if mission.get("maturity") not in {"PROTOTYPE", "MVP", "PROD_FOUNDATION", "PROD_HARDENED"}:
        errors.append("mission.maturity is invalid")
    for key in ("stack", "runtime", "storage", "authentication", "deployment"):
        if not present(at(value, "assumptions", key)):
            errors.append(f"assumptions.{key} is required")
    components = at(value, "architecture", "components") or {}
    for key in sorted(COMPONENTS):
        if not present(components.get(key)):
            errors.append(f"architecture.components.{key} is unresolved")
    missing_failures = sorted(FAILURES - set(at(value, "architecture", "failure_modes") or []))
    if missing_failures:
        errors.append("failure modes missing: " + ", ".join(missing_failures))
    for key in ("correlation_ids", "health_checks", "structured_logs", "audit_logs", "metrics_alerts"):
        if not present(at(value, "architecture", "observability", key)):
            errors.append(f"architecture.observability.{key} is required")
    for key in ("unit", "integration", "e2e_or_smoke", "fixtures_mocks", "failure_first", "commands"):
        if not present(at(value, "testing", key)):
            errors.append(f"testing.{key} is required")
    if at(value, "testing", "compatibility_command") != COMPATIBILITY_COMMAND:
        errors.append("testing.compatibility_command must equal the exact 55-test command")
    if COMPATIBILITY_COMMAND not in (at(value, "testing", "commands") or []):
        errors.append("testing.commands must contain the exact 55-test command")
    for key in ("file_tree", "exact_code_files", "setup_commands", "run_commands", "test_commands", "deploy_commands", "rollback_commands", "debugging"):
        if not present(at(value, "delivery", key)):
            errors.append(f"delivery.{key} is required")
    if COMPATIBILITY_COMMAND not in (at(value, "delivery", "test_commands") or []):
        errors.append("delivery.test_commands must contain the exact 55-test command")
    formation = value.get("formation") or {}
    if formation.get("gate_decision") != "EXECUTE":
        errors.append("formation.gate_decision must equal EXECUTE")
    if formation.get("single_effectful_path") is not True:
        errors.append("formation.single_effectful_path must be true")
    for key in ("mission_id", "mission_version", "authority_class", "effectful_permit"):
        if not present(formation.get(key)):
            errors.append(f"formation.{key} is required")
    for key in ("idempotency", "checkpoints", "resume_conditions", "handoff_files", "stop_switch"):
        if not present(at(value, "continuity", key)):
            errors.append(f"continuity.{key} is required")
    states = value.get("states") or {}
    for key in ("designed", "implemented", "tested", "registered", "authorized", "ready", "deployed", "proven"):
        if not isinstance(states.get(key), bool):
            errors.append(f"states.{key} must be boolean")
    if any(states.get(key) for key in ("registered", "authorized", "ready", "deployed", "proven")):
        errors.append("live maturity states must remain false")
    if at(value, "proof", "maturity") != MATURITY:
        errors.append("proof.maturity must equal implemented-not-attached state")
    if set(at(value, "proof", "adversarial_controls") or []) != ADVERSARIAL_CONTROLS:
        errors.append("proof.adversarial_controls must cover every independent BLOCK finding")
    if set(at(value, "proof", "resolved_defects") or []) != ADVERSARIAL_CONTROLS:
        errors.append("proof.resolved_defects must enumerate every repaired independent finding")
    if at(value, "proof", "unresolved_defects") != []:
        errors.append("proof.unresolved_defects must be an explicit empty list after verified repair")
    if formation.get("effectful_permit") != "CONSUMED_AND_PERSISTED_IN_GOVERNED_FORMATION_STATE":
        errors.append("formation.effectful_permit persistence wording is inaccurate")
    limitations = set(at(value, "proof", "known_limitations") or [])
    required_limitations = {
        "no live Master Bible attachment",
        "no provider-authoritative active-chat inventory",
        "no per-chat emitters",
        "no unsolicited injection",
        "no system-wide awareness",
    }
    if not required_limitations <= limitations:
        errors.append("required truthful limitations missing")
    if require_proof:
        if states.get("tested") is not True:
            errors.append("--require-proof requires states.tested=true")
        for key in ("test_results", "semantic_verification"):
            proof = at(value, "proof", key)
            if not present(proof) or str(proof).startswith("PENDING_"):
                errors.append(f"--require-proof requires proof.{key}")
        if at(value, "proof", "unresolved_defects") not in ([], None):
            errors.append("--require-proof requires zero unresolved defects")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("--require-proof", action="store_true")
    args = parser.parse_args()
    try:
        value = json.loads(args.contract.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
        return 2
    errors = validate(value, require_proof=args.require_proof)
    print(json.dumps({"valid": not errors, "errors": errors, "maturity": MATURITY}, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
