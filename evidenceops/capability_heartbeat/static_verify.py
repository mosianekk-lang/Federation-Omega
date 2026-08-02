#!/usr/bin/env python3
"""Fail-closed static verification for network/effect/scheduler boundaries."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT / "foundation"
INTEGRATION_FILES = (
    ROOT / "authority.py",
    ROOT / "engine.py",
    ROOT / "bible_federation.py",
    ROOT / "system.py",
    ROOT.parents[1] / "scheduler" / "run_scheduler.py",
)
WORKFLOW = ROOT.parents[1] / ".github" / "workflows" / "evidenceops-capability-heartbeat-ci.yml"
COMPATIBILITY_COMMAND = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest "
    "tests.test_atomic_transactions tests.test_connector_foundry "
    "tests.test_connector_foundry_google_drive tests.test_ecasp "
    "tests.test_innovation_engine_registry tests.test_operation_idempotency "
    "tests.test_provenance_passport tests.test_runtime tests.test_slrk "
    "tests.test_wif_hardening"
)

BANNED_IMPORT_ROOTS = frozenset(
    {
        "aiohttp", "asyncio", "boto3", "ftplib", "google", "http", "multiprocessing",
        "openai", "os", "requests", "sched", "smtplib", "socket", "subprocess",
        "threading", "urllib", "webbrowser",
    }
)
BANNED_CALLS = frozenset({"eval", "exec", "open", "__import__", "input"})
BANNED_METHODS = frozenset(
    {
        "chmod", "link_to", "mkdir", "rename", "replace", "rmdir", "symlink_to",
        "touch", "unlink", "write_bytes", "write_text",
    }
)
BANNED_TEXT = (
    "workflow_dispatch:",
    "schedule:",
    "cron:",
    "permissions: write-all",
    "contents: write",
    "pull-requests: write",
    "curl ",
    "wget ",
)


def verify_python() -> list[str]:
    errors: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(ROOT)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        except (OSError, SyntaxError) as exc:
            errors.append(f"PARSE_FAILURE:{relative}:{exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
                for root in roots:
                    if root in BANNED_IMPORT_ROOTS:
                        errors.append(f"BANNED_IMPORT:{relative}:{node.lineno}:{root}")
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    root = node.module.split(".")[0]
                    if root in BANNED_IMPORT_ROOTS:
                        errors.append(f"BANNED_IMPORT:{relative}:{node.lineno}:{root}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
                    errors.append(f"BANNED_CALL:{relative}:{node.lineno}:{node.func.id}")
                if isinstance(node.func, ast.Attribute) and node.func.attr in BANNED_METHODS:
                    errors.append(f"BANNED_EFFECT_METHOD:{relative}:{node.lineno}:{node.func.attr}")
            elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom)):
                errors.append(f"BACKGROUND_OR_STREAMING_SYNTAX:{relative}:{getattr(node, 'lineno', 0)}")
    return errors


def verify_workflow() -> list[str]:
    if not WORKFLOW.is_file():
        return ["CI_WORKFLOW_MISSING"]
    text = WORKFLOW.read_text(encoding="utf-8")
    lowered = text.lower()
    errors = [f"BANNED_WORKFLOW_TEXT:{item.strip()}" for item in BANNED_TEXT if item in lowered]
    required = (
        "evidenceops/capability_heartbeat/**",
        ".github/workflows/evidenceops-capability-heartbeat-ci.yml",
        "permissions:\n  contents: read",
        "python-version: \"3.12\"",
        COMPATIBILITY_COMMAND,
    )
    errors.extend(f"WORKFLOW_REQUIREMENT_MISSING:{item}" for item in required if item not in text)
    return errors


def verify_contract_truth() -> list[str]:
    value = json.loads((ROOT / "BUILD_CONTRACT.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    states = value.get("states") or {}
    if any(states.get(key) for key in ("registered", "authorized", "ready", "deployed", "proven")):
        errors.append("FALSE_LIVE_STATE_CLAIM")
    if (value.get("proof") or {}).get("maturity") != "DURABLE_FOUNDATION_IMPLEMENTED_NOT_ATTACHED":
        errors.append("MATURITY_DRIFT")
    if value.get("mission", {}).get("user") != "OWNER-A1B2C3D4 and governed metadata-only EvidenceOps consumers":
        errors.append("PUBLIC_OWNER_LABEL_NOT_MINIMIZED")
    if value.get("formation", {}).get("effectful_permit") != "CONSUMED_AND_PERSISTED_IN_GOVERNED_FORMATION_STATE":
        errors.append("FORMATION_PERMIT_PERSISTENCE_DRIFT")
    return errors


def verify_integrity_controls() -> list[str]:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(PACKAGE.rglob("*.py"))
    )
    tests = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((ROOT / "foundation_tests").glob("test_*.py"))
    )
    source_markers = (
        "SIGNER_REGISTRY_BINDING_MISMATCH",
        "ENVELOPE_CLASSIFICATION_WEAKER_THAN_NODE",
        "RESPAWN_MANIFEST_FUTURE_DATED",
        "parent_transaction_id",
        "HOP_PATH_LENGTH_MISMATCH",
        "VISITED_PARENT_CHAIN_MISMATCH",
        "validate_explicit_metadata",
        "COMPLETE_ENVELOPE_LINEAGE_REQUIRED",
        "LINEAGE_PARENT_ENVELOPE_MISMATCH",
        "LINEAGE_SEMANTIC_PAYLOAD_MUTATION",
        "RECEIPT_ACCEPTED_ENVELOPE_SCOPE_MISMATCH",
        "RECEIPT_FUTURE_DATED",
        "UNSUPPORTED_OBSERVATION_SOURCE",
        "SIGNING_VERSION_INHERITANCE_MISMATCH",
        "root_record.adapter_version == policy.adapter_version",
        "FIELD_CODE_NAMESPACE_MISMATCH",
        "CREDENTIAL_VALUE_SHAPE_PROHIBITED",
        "contained_git_reference",
        "RECEIPT_DESTINATION_REGISTRATION_NOT_FRESH",
        "registry_records_fresh",
        "MASTER_BIBLE_POLICY_HASH_MISMATCH",
        "CONTROL_GENERATION_ROLLBACK",
        "DUPLICATE_JSON_KEY",
        "REGISTRY_RECORDS_SEQUENCE_REQUIRED",
    )
    test_markers = (
        "test_attacker_signer_reusing_registered_key_id_is_rejected",
        "test_forged_destination_receipt_is_rejected",
        "test_legitimate_rotation_generation_passes",
        "test_destination_classification_fence_is_independent",
        "test_respawn_cross_binds_policy_registry_root_and_generation",
        "test_unregistered_signing_node_is_rejected",
        "test_generic_ledger_field_cannot_hide_legal_or_personal_prose",
        "test_forwarded_envelope_requires_complete_signed_lineage",
        "test_malformed_lineage_sequence_payload_and_completeness_are_rejected",
        "test_receipt_scope_is_cross_bound_to_accepted_envelope",
        "test_receipt_acceptance_time_is_bounded_and_fresh",
        "test_respawn_cross_binds_complete_policy_root_scope",
        "test_observation_rejects_unknown_source_fields_and_raw_prose",
        "test_child_signing_version_must_equal_parent",
        "test_root_signing_version_must_be_supported",
        "test_field_bound_code_privacy_rejects_credentials_personal_and_legal_probes",
        "test_valid_code_namespace_compatibility_table",
        "test_local_git_reference_rejects_traversal_empty_dot_and_symlink_segments",
        "test_receipt_verification_requires_fresh_destination_registration",
        "test_respawn_requires_every_registry_record_fresh_at_now",
        "test_master_bible_policy_hash_is_deterministically_recomputed",
        "test_control_generation_rollback_is_rejected_by_append_verify_and_readback",
        "test_strict_json_decoder_rejects_duplicate_keys",
        "test_adapter_json_boundaries_reject_duplicate_keys",
        "test_frozen_tuple_contracts_snapshot_external_lists",
        "test_third_review_control_manifest_is_required",
    )
    errors = [f"INTEGRITY_CONTROL_MISSING:{item}" for item in source_markers if item not in source]
    errors.extend(f"ADVERSARIAL_TEST_MISSING:{item}" for item in test_markers if item not in tests)
    integration = "\n".join(path.read_text(encoding="utf-8") for path in INTEGRATION_FILES)
    integration_tests = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((ROOT / "tests").glob("test_*.py"))
    )
    integration_markers = (
        "class VerifiedV4Authority",
        "COMPLETE_REGISTERED_SIGNER_SET_REQUIRED",
        "VERIFIED_V4_AUTHORITY_REQUIRED",
        "CATALOGUE_ONLY_CANNOT_AUTHORIZE_INGRESS",
        "complete typed signed lineage is required",
        "TURN_OPERATION_IDEMPOTENCY_CONFLICT",
        'ACCEPTED_INGRESS_STATES = {"TURN_TRANSACTION_VERIFIED_LOCAL"}',
        '"scheduler_authority": False',
        '"recommendation_authority": False',
    )
    integration_test_markers = (
        "test_verified_v4_is_the_only_recommendation_authority",
        "test_catalogue_without_authority_cannot_recommend",
        "test_forged_signature_fails_closed",
        "test_future_envelope_fails_closed",
        "test_raw_turn_content_and_static_fixture_are_rejected",
        "test_operation_id_replay_with_changed_full_payload_fails",
        "test_false_live_attachment_policy_is_rejected",
        "test_surface_and_scheduler_paths_are_inventory_only",
    )
    errors.extend(
        f"INTEGRATION_CONTROL_MISSING:{item}" for item in integration_markers if item not in integration
    )
    errors.extend(
        f"INTEGRATION_TEST_MISSING:{item}" for item in integration_test_markers if item not in integration_tests
    )
    manifest = json.loads((ROOT / "DOCUMENTATION_MANIFEST.json").read_text(encoding="utf-8"))
    if any(str(item.get("source", "")).startswith("/") for item in manifest.get("documents", [])):
        errors.append("ABSOLUTE_DOCUMENTATION_SOURCE_PATH")
    public_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(ROOT.rglob("*"))
        if path.is_file() and path.suffix in {".py", ".md", ".json", ".toml"}
    )
    if ("/" + "root/") in public_text:
        errors.append("ABSOLUTE_PRIVATE_ROOT_PATH")
    return errors


def main() -> int:
    errors = sorted(set(
        verify_python()
        + verify_workflow()
        + verify_contract_truth()
        + verify_integrity_controls()
    ))
    print(json.dumps({
        "valid": not errors,
        "errors": errors,
        "production_python_files": len(tuple(PACKAGE.rglob("*.py"))),
        "network_free": not errors,
        "external_effect_free": not errors,
        "scheduler_free": not errors,
        "maturity": "DURABLE_FOUNDATION_IMPLEMENTED_NOT_ATTACHED",
    }, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
