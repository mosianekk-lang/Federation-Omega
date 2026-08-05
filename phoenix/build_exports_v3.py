#!/usr/bin/env python3
"""Build Phoenix exports with authority continuity and read-only recovery controls."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

V2_SPEC = importlib.util.spec_from_file_location(
    "phoenix_build_exports_v2", ROOT / "phoenix" / "build_exports_v2.py"
)
assert V2_SPEC and V2_SPEC.loader
V2 = importlib.util.module_from_spec(V2_SPEC)
sys.modules[V2_SPEC.name] = V2
V2_SPEC.loader.exec_module(V2)

PACKET_SPEC = importlib.util.spec_from_file_location(
    "phoenix_owner_sealed_packet",
    ROOT / "phoenix" / "ops-template" / "owner_sealed_packet.py",
)
assert PACKET_SPEC and PACKET_SPEC.loader
PACKET = importlib.util.module_from_spec(PACKET_SPEC)
sys.modules[PACKET_SPEC.name] = PACKET
_previous_dont_write_bytecode = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    PACKET_SPEC.loader.exec_module(PACKET)
finally:
    sys.dont_write_bytecode = _previous_dont_write_bytecode


def _include(
    source: Path,
    destination: Path,
    export_path: str,
    reason: str,
) -> V2.BASE.FileRecord:
    V2.BASE.copy_file(source, destination / export_path)
    return V2.BASE.FileRecord(
        path=export_path,
        size=source.stat().st_size,
        sha256=V2.BASE.sha256_file(source),
        classification="OPS_INCLUDED",
        reason=reason,
    )


def _publish_pst_runtime() -> dict[str, object]:
    """Publish bounded verifier runtime settings for later Phoenix steps."""

    scratch_root = os.environ.get("PST_VERIFY_ROOT", "/tmp/pst-composite-verify")
    bootstrap_dir = ROOT / "runtime_bootstrap"
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    pythonpath = str(bootstrap_dir)
    if existing_pythonpath:
        pythonpath = f"{pythonpath}{os.pathsep}{existing_pythonpath}"

    github_env = os.environ.get("GITHUB_ENV")
    published = False
    if github_env:
        env_path = Path(github_env)
        with env_path.open("a", encoding="utf-8") as handle:
            handle.write(f"PST_VERIFY_ROOT={scratch_root}\n")
            handle.write(f"PYTHONPATH={pythonpath}\n")
        published = True
    return {
        "scratch_root": scratch_root,
        "pythonpath_bootstrap": str(bootstrap_dir),
        "github_env_published": published,
        "cross_host_authorization_guard": True,
        "source_mutation_attempted": False,
    }


def stage_ops_v3_4(
    root: Path, stage: Path, policy: dict
) -> list[V2.BASE.FileRecord]:
    template = root / policy["ops"]["template_prefix"]
    if not template.is_dir():
        raise RuntimeError(f"Ops template missing: {template}")

    records: list[V2.BASE.FileRecord] = []
    for path in sorted(template.rglob("*"), key=lambda item: item.as_posix()):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if not path.is_file():
            continue
        rel = path.relative_to(template).as_posix()
        records.append(_include(path, stage, rel, "APPROVED_OPS_TEMPLATE"))

    sources = {
        "authorized cutover base coordinator": (
            root / "phoenix" / "provider_cutover_authorized_executor.py"
        ),
        "authorization-use state machine": (
            root / "phoenix" / "provider_cutover_authorization_use.py"
        ),
        "provider cutover v3.1": root / "phoenix" / "provider_cutover_v3_1.py",
        "provider cutover v3 base": root / "phoenix" / "provider_cutover_v3.py",
        "provider outcome reconciler": (
            root / "phoenix" / "provider_cutover_outcome_reconciler.py"
        ),
    }
    for label, path in sources.items():
        if not path.is_file():
            raise RuntimeError(f"{label} missing: {path}")

    records.extend(
        [
            _include(
                sources["authorized cutover base coordinator"],
                stage,
                "provider_cutover.py",
                "AUTHORIZATION_ENFORCED_PROVIDER_CUTOVER_BASE_V22",
            ),
            _include(
                sources["authorization-use state machine"],
                stage,
                "provider_cutover_authorization_use.py",
                "ONE_TIME_AUTHORIZATION_CONSUMPTION_V21",
            ),
            _include(
                sources["provider cutover v3.1"],
                stage,
                "provider_cutover_v3_1.py",
                "DUAL_AUTHORITY_PROVIDER_CUTOVER_V3_1_EXACT_LEASE",
            ),
            _include(
                sources["provider cutover v3 base"],
                stage,
                "provider_cutover_v3_base.py",
                "VERIFIED_PROVIDER_CUTOVER_V3_BASE",
            ),
            _include(
                sources["provider outcome reconciler"],
                stage,
                "provider_cutover_outcome_reconciler.py",
                "READ_ONLY_EXACT_PROVIDER_OUTCOME_RECONCILIATION_V26",
            ),
        ]
    )

    actual = {item.path for item in records}
    required = set(policy["ops"]["required_files"])
    required.update(policy["ops"].get("required_v3_files", []))
    missing = sorted(required - actual)
    if missing:
        raise RuntimeError(f"Ops export missing required files: {missing}")
    if any(V2.BASE.is_github_workflow_path(item.path) for item in records):
        raise RuntimeError("Ops export unexpectedly contains an active workflow")
    if any("__pycache__" in Path(item.path).parts or item.path.endswith(".pyc") for item in records):
        raise RuntimeError("Ops export unexpectedly contains Python runtime bytecode")
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--policy", type=Path, default=Path("phoenix/export_policy.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("phoenix-export-output")
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    policy = args.policy if args.policy.is_absolute() else root / args.policy
    output = args.output if args.output.is_absolute() else root / args.output

    pst_runtime = _publish_pst_runtime()
    V2.BASE.stage_ops = stage_ops_v3_4
    receipt = V2.BASE.build(root, output, policy)
    receipt["provider_cutover_engine"] = {
        "version": "3.5",
        "authorization_execution_gate": "V30_OWNER_PROVIDER_AUTHORITY_BINDING",
        "provider_controller_version": "3.1",
        "authority_models": ["INSTALLATION_TEMPLATE", "USER_SCOPED"],
        "authorization_decision_required": True,
        "authorization_decision_schema": (
            "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-2"
        ),
        "owner_authorization_provider_receipt_hash_binding_required": True,
        "owner_authorization_repository_creation_endpoint_binding_required": True,
        "owner_authorization_external_commercial_gate_advancement_allowed": False,
        "provider_authority_receipt_required": True,
        "provider_authority_receipt_max_age_seconds": 300,
        "provider_authority_receipt_max_future_skew_seconds": 30,
        "provider_authority_receipt_semantic_checks_required": True,
        "provider_authority_probe_get_only": True,
        "provider_authority_just_in_time_reprobe_required": True,
        "provider_authority_continuity_fields": [
            "authority_mode",
            "repository_creation_endpoint",
            "legacy_main_sha",
            "core_target_exists",
            "ops_target_exists"
        ],
        "provider_authority_mode_must_match_decision": True,
        "one_time_authorization_consumption_required": True,
        "unknown_outcome_automatic_retry": False,
        "read_only_outcome_reconciliation": True,
        "installation_template_endpoint": (
            "/repos/mosianekk-lang/Federation-Omega/generate"
        ),
        "template_generated_main_replacement": (
            "EXACT_PROVIDER_BOUND_FORCE_WITH_LEASE"
        ),
        "entrypoint": "provider_cutover_owner_authority_bound.py",
        "authority_bound_internal_entrypoint": "provider_cutover_authority_bound.py",
        "provider_authority_probe": "provider_authority_probe.py",
        "candidate_validator": "provider_cutover_candidate.py",
        "live_source_guard": "provider_cutover_guarded.py",
        "authorization_base_coordinator": "provider_cutover.py",
        "authorization_state_machine": "provider_cutover_authorization_use.py",
        "provider_controller": "provider_cutover_v3_1.py",
        "base_controller": "provider_cutover_v3_base.py",
        "outcome_reconciliation_entrypoint": (
            "provider_cutover_outcome_reconciler.py"
        ),
        "outcome_reconciliation_mutation_allowed": False,
        "provider_apply_performed": False,
        "temporary_template_state_restoration": "REQUIRED_DURING_APPLY",
        "credential_value_recorded": False,
        "owner_sealed_packet_candidate_builder": "owner_sealed_packet.py",
        "owner_sealed_packet_candidate_grants_authority": False,
        "owner_sealed_packet_candidate_proves_custody": False,
        "owner_sealed_packet_candidate_proves_confidentiality": False,
        "owner_sealed_packet_candidate_runtime_bytecode_included": False,
    }
    receipt["pst_verifier_runtime"] = pst_runtime
    receipt["source_mutation_attempted"] = False

    packet_output = output / "pst-completion" / "owner-sealed-packet-candidate.json"
    packet_summary = PACKET.build_packet_candidate(
        core_archive=output / "Federation-Omega-Core.tar.gz",
        ops_archive=output / "Federation-Omega-Ops.tar.gz",
        output=packet_output,
        metadata={
            "source_repository": receipt["source_repository"],
            "source_sha": receipt["source_sha"],
            "export_policy_version": receipt["policy_version"],
            "core": receipt["core"],
            "ops": receipt["ops"],
        },
    )
    receipt["owner_sealed_packet_candidate"] = packet_summary

    receipt.pop("receipt_sha256", None)
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    receipt["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()

    receipt_path = output / "phoenix-export-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
