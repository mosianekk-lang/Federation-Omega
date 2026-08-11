from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evidenceops.fevx_adapter_v1.adapter import EvidenceOpsFEVXAdapter
from evidenceops.fevx_adapter_v1.contracts import BoundaryViolation
from evidenceops.fevx_adapter_v1.core import (
    atomic_write_json,
    atomic_write_text,
    digest,
    stable_identifier,
    utc_now,
)
from evidenceops.fevx_adapter_v1.store import DerivedStore


def restore(path: Path, dump_text: str) -> DerivedStore:
    return DerivedStore.restore_sql(path, dump_text)


def append_provider_proof(
    proof_dir: Path, proof: dict[str, Any]
) -> dict[str, Any]:
    proof_dir.mkdir(parents=True, exist_ok=True)
    head_path = proof_dir / "proof_chain_head.json"
    head = (
        json.loads(head_path.read_text(encoding="utf-8"))
        if head_path.exists()
        else {"head_hash": "GENESIS"}
    )
    record = dict(proof)
    record["previous_hash"] = head.get("head_hash", "GENESIS")
    record_hash = digest(record)
    record["record_hash"] = record_hash
    atomic_write_json(proof_dir / f"{record['proof_id']}.json", record)
    atomic_write_json(
        head_path,
        {
            "head_hash": record_hash,
            "proof_id": record["proof_id"],
            "recorded_at": record["recorded_at"],
        },
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--runtime-root", default="runtime/evidenceops_fevx_adapter"
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    runtime_root = (repo_root / args.runtime_root).resolve()
    state_dir = runtime_root / "state"
    results_dir = runtime_root / "results"
    proofs_dir = runtime_root / "proofs"
    heartbeat_dir = runtime_root / "heartbeat"
    drift_dir = runtime_root / "drift"
    snapshots_dir = runtime_root / "snapshots"
    checkpoints_dir = runtime_root / "checkpoints"
    for directory in (
        state_dir,
        results_dir,
        proofs_dir,
        heartbeat_dir,
        drift_dir,
        snapshots_dir,
        checkpoints_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    fixture_path = (
        repo_root
        / "evidenceops/fevx_adapter_v1/fixtures/synthetic_case_packet.json"
    )
    packet = json.loads(fixture_path.read_text(encoding="utf-8"))
    packet_before = copy.deepcopy(packet)
    input_hash = digest(packet_before)

    existing_dump_path = state_dir / "derived_state.sql"
    prior_dump = (
        existing_dump_path.read_text(encoding="utf-8")
        if existing_dump_path.exists()
        else ""
    )
    provider = "github_actions" if os.getenv("GITHUB_ACTIONS") == "true" else "local"
    execution_id = os.getenv("GITHUB_RUN_ID") or f"LOCAL-{utc_now()}"
    run_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "1")
    event_name = os.getenv("GITHUB_EVENT_NAME", "local")
    commit_sha = os.getenv("GITHUB_SHA", "LOCAL")
    repository = os.getenv("GITHUB_REPOSITORY", "local")
    recorded_at = utc_now()

    with tempfile.TemporaryDirectory(prefix="evidenceops-fevx-canary-") as temporary:
        temporary_path = Path(temporary)
        database = temporary_path / "derived.db"
        store = restore(database, prior_dump)
        before_dump = store.dump_sql()
        before_hash = digest(before_dump)

        adapter = EvidenceOpsFEVXAdapter(store=store, repo_root=repo_root)
        first = adapter.analyse(packet)
        recommendation_count_after_first = store.recommendation_count()
        ledger_count_after_first = store.ledger_count()
        second = adapter.analyse(packet)
        recommendation_count_after_second = store.recommendation_count()
        ledger_count_after_second = store.ledger_count()

        boundary_checks: dict[str, bool] = {}
        bad_case = copy.deepcopy(packet)
        bad_case["stakeholders"][0]["case_wall_id"] = "OTHER-CASE-WALL"
        try:
            adapter.analyse(bad_case)
            boundary_checks["nested_case_wall_rejected"] = False
        except BoundaryViolation:
            boundary_checks["nested_case_wall_rejected"] = True

        bad_external = copy.deepcopy(packet)
        bad_external["authority"]["external_effect"] = True
        try:
            adapter.analyse(bad_external)
            boundary_checks["external_effect_rejected"] = False
        except BoundaryViolation:
            boundary_checks["external_effect_rejected"] = True

        bad_action = copy.deepcopy(packet)
        bad_action["authority"]["requested_actions"].append("SEND_EMAIL")
        try:
            adapter.analyse(bad_action)
            boundary_checks["held_action_rejected"] = False
        except BoundaryViolation:
            boundary_checks["held_action_rejected"] = True

        integrity = store.verify_all()
        after_dump = store.dump_sql()
        after_hash = digest(after_dump)
        store.close()

        tamper_db = temporary_path / "tamper.db"
        tamper_store = restore(tamper_db, after_dump)
        tamper_store.connection.execute(
            "UPDATE ledger SET payload_json=? "
            "WHERE sequence=(SELECT MIN(sequence) FROM ledger)",
            ('{"tampered":true}',),
        )
        tamper_store.connection.commit()
        tamper_detected = tamper_store.verify_ledger()["status"] == "FAILED"
        tamper_store.close()

        rollback_db = temporary_path / "rollback.db"
        rollback_store = restore(rollback_db, before_dump)
        rollback_dump = rollback_store.dump_sql()
        rollback_ok = digest(rollback_dump) == before_hash
        rollback_store.close()

        reapply_store = restore(rollback_db, after_dump)
        reapply_dump = reapply_store.dump_sql()
        reapply_ok = digest(reapply_dump) == after_hash
        reapply_verify = reapply_store.verify_all()
        reapply_store.close()

    source_packet_immutable = packet == packet_before and digest(packet) == input_hash
    derived = first["derived_payload"]
    base_count = int(derived["base_cse"]["module_count"])
    frontier_count = int(derived["frontier_cse"]["module_count"])
    combined_count = int(derived["combined_module_count"])
    no_source_or_fact_tables = integrity["schema_boundary"]["status"] == "PASSED"
    adapter_source = (
        repo_root / "evidenceops/fevx_adapter_v1/adapter.py"
    ).read_text(encoding="utf-8")
    no_execution_endpoint = not any(
        token in adapter_source
        for token in ("FastAPI(", "@app.post", "requests.post", "send_email(")
    )
    idempotent = (
        second["idempotent"] is True
        and recommendation_count_after_first
        == recommendation_count_after_second
        == 1
        and ledger_count_after_first == ledger_count_after_second == 1
    )

    expected_source_manifest = [
        {
            "source_id": row["source_id"],
            "sha256": row["sha256"],
            "classification": row["classification"],
        }
        for row in packet_before["sources"]
    ]
    expected_fact_manifest = [
        {
            "fact_id": row["fact_id"],
            "source_refs": row["source_refs"],
            "verification_state": row["verification_state"],
        }
        for row in packet_before["verified_facts"]
    ]
    checks = {
        "provider_native_execution": provider == "github_actions",
        "source_packet_immutable": source_packet_immutable,
        "source_manifest_immutable": (
            derived["authority"]["source_write"] is False
            and derived["source_manifest"] == expected_source_manifest
        ),
        "verified_facts_immutable": (
            derived["authority"]["verified_fact_write"] is False
            and derived["fact_manifest"] == expected_fact_manifest
        ),
        "case_wall_intact": derived["case_wall_id"] == packet["case_wall_id"],
        "nested_case_wall_rejected": boundary_checks["nested_case_wall_rejected"],
        "external_effect_rejected": boundary_checks["external_effect_rejected"],
        "held_action_rejected": boundary_checks["held_action_rejected"],
        "output_held_and_advisory": (
            derived["release_state"] == "HELD_FOR_EVIDENCEOPS_REVIEW"
            and derived["fact_status"] == "DERIVED_NOT_FACT"
        ),
        "base_modules_10": base_count == 10,
        "frontier_modules_10": frontier_count == 10,
        "combined_modules_20": combined_count == 20,
        "idempotent_recurrence": idempotent,
        "derived_only_schema": no_source_or_fact_tables,
        "ledger_integrity": integrity["ledger"]["status"] == "PASSED",
        "record_integrity": integrity["records"]["status"] == "PASSED",
        "tamper_detected": tamper_detected,
        "rollback_test": rollback_ok,
        "reapply_test": reapply_ok and reapply_verify["status"] == "PASSED",
        "no_execution_endpoint": no_execution_endpoint,
    }
    passed = all(checks.values())

    desired_path = state_dir / "desired_state.json"
    desired = (
        json.loads(desired_path.read_text(encoding="utf-8"))
        if desired_path.exists()
        else {
            "service": "evidenceops-fevx-adapter",
            "version": "1.0.0",
            "runtime_state": "OPERATIONAL",
            "integration_state": (
                "PROVIDER_VERIFIED_SUPERVISED_READ_ONLY_ANALYTICAL_SERVICE"
            ),
            "evidenceops_adapter_level": 4,
            "cse_provider_level": 5,
            "module_count": 20,
            "external_effect": False,
            "source_write": False,
            "verified_fact_write": False,
            "cross_case_access": False,
            "level_6_eligible": False,
            "real_case_accuracy_evidence": False,
        }
    )
    actual = {
        "service": "evidenceops-fevx-adapter",
        "version": "1.0.0",
        "runtime_state": "OPERATIONAL" if passed else "DEGRADED",
        "integration_state": (
            "PROVIDER_VERIFIED_SUPERVISED_READ_ONLY_ANALYTICAL_SERVICE"
            if passed
            else "PROVIDER_CANARY_FAILED"
        ),
        "evidenceops_adapter_level": 4 if passed else 3,
        "cse_provider_level": 5,
        "module_count": combined_count,
        "external_effect": False,
        "source_write": False,
        "verified_fact_write": False,
        "cross_case_access": False,
        "level_6_eligible": False,
        "real_case_accuracy_evidence": False,
        "database_dump_sha256": after_hash,
        "input_packet_sha256": input_hash,
        "recommendation_id": first["recommendation_id"],
        "updated_at": recorded_at,
    }
    compare_keys = [
        "service", "version", "runtime_state", "integration_state",
        "evidenceops_adapter_level", "cse_provider_level", "module_count",
        "external_effect", "source_write", "verified_fact_write",
        "cross_case_access", "level_6_eligible", "real_case_accuracy_evidence",
    ]
    differences = {
        key: {"desired": desired.get(key), "actual": actual.get(key)}
        for key in compare_keys
        if desired.get(key) != actual.get(key)
    }
    drift = {
        "recorded_at": recorded_at,
        "classification": "IN_SYNC" if not differences else "DRIFT_DETECTED",
        "differences": differences,
        "desired_hash": digest({key: desired.get(key) for key in compare_keys}),
        "actual_hash": digest({key: actual.get(key) for key in compare_keys}),
    }
    passed = passed and not differences

    provider_proof_id = stable_identifier(
        "PRF-EVIDENCEOPS-FEVX",
        execution_id,
        run_attempt,
        first["proof_hash"],
        after_hash,
    )
    result = {
        "schema": "EVIDENCEOPS_FEVX_PROVIDER_RESULT_V1",
        "result_id": stable_identifier("RESULT", execution_id, run_attempt),
        "recorded_at": recorded_at,
        "status": "VERIFIED" if passed else "FAILED_VERIFICATION",
        "provider": provider,
        "provider_event": {
            "execution_id": execution_id,
            "run_attempt": run_attempt,
            "event_name": event_name,
            "commit_sha": commit_sha,
            "repository": repository,
        },
        "checks": checks,
        "check_count": len(checks),
        "checks_passed": sum(bool(value) for value in checks.values()),
        "input_packet_sha256": input_hash,
        "database_dump_sha256": after_hash,
        "recommendation_id": first["recommendation_id"],
        "adapter_proof_id": first["proof_id"],
        "adapter_proof_hash": first["proof_hash"],
        "semantic_hash": first["semantic_hash"],
        "base_module_count": base_count,
        "frontier_module_count": frontier_count,
        "combined_module_count": combined_count,
        "idempotent_recurrence": idempotent,
        "rollback_test": rollback_ok,
        "reapply_test": reapply_ok,
        "integrity": integrity,
        "drift": drift["classification"],
        "integration_state": actual["integration_state"],
        "evidenceops_adapter_level": actual["evidenceops_adapter_level"],
        "cse_provider_level": actual["cse_provider_level"],
        "level_6_eligible": False,
        "external_effect": False,
        "source_write": False,
        "verified_fact_write": False,
        "cross_case_access": False,
        "real_case_accuracy_evidence": False,
        "next_gate": "SUPERVISED_REAL_CASE_CANARY_WITH_OWNER_REVIEW",
        "truth_boundary": (
            "This provider canary proves the read-only EvidenceOps-to-FEVX "
            "integration controls using a synthetic case fixture and the actual "
            "20-module CSE runtime. It does not prove legal accuracy, a real case "
            "outcome, or authority for any external action."
        ),
    }
    provider_proof = append_provider_proof(
        proofs_dir,
        {
            "proof_id": provider_proof_id,
            "recorded_at": recorded_at,
            "status": result["status"],
            "provider": provider,
            "result_id": result["result_id"],
            "input_packet_sha256": input_hash,
            "database_dump_sha256": after_hash,
            "adapter_proof_hash": first["proof_hash"],
            "semantic_hash": first["semantic_hash"],
            "checks_sha256": digest(checks),
            "external_effect": False,
            "source_write": False,
            "verified_fact_write": False,
            "cross_case_access": False,
        },
    )
    result["provider_proof_id"] = provider_proof_id
    result["provider_proof_hash"] = provider_proof["record_hash"]

    heartbeat = {
        "heartbeat_id": "HB-EVIDENCEOPS-FEVX-ADAPTER",
        "recorded_at": recorded_at,
        "runtime_state": actual["runtime_state"],
        "verified": passed,
        "provider": provider,
        "version": "1.0.0",
        "module_count": combined_count,
        "provider_proof_id": provider_proof_id,
        "provider_proof_hash": provider_proof["record_hash"],
        "database_dump_sha256": after_hash,
        "drift": drift["classification"],
        "external_effect": False,
        "source_write": False,
        "verified_fact_write": False,
        "next_gate": result["next_gate"],
    }
    checkpoint = {
        "checkpoint_id": stable_identifier(
            "CHK-EVIDENCEOPS-FEVX", provider_proof_id, after_hash
        ),
        "recorded_at": recorded_at,
        "provider_proof_hash": provider_proof["record_hash"],
        "database_dump_sha256": after_hash,
        "recommendation_count": recommendation_count_after_second,
        "ledger_event_count": ledger_count_after_second,
        "semantic_hash": first["semantic_hash"],
    }

    atomic_write_text(existing_dump_path, after_dump)
    atomic_write_text(snapshots_dir / "before.sql", before_dump)
    atomic_write_text(snapshots_dir / "after.sql", after_dump)
    atomic_write_json(results_dir / "latest.json", result)
    atomic_write_json(heartbeat_dir / "latest.json", heartbeat)
    atomic_write_json(drift_dir / "latest.json", drift)
    atomic_write_json(state_dir / "actual_state.json", actual)
    atomic_write_json(checkpoints_dir / "latest.json", checkpoint)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
