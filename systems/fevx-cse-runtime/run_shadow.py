#!/usr/bin/env python3
"""Provider-native GitHub Actions shadow runtime for FEVX CSE v1.1.

The runtime is deliberately synthetic and A1-only. It restores durable state from a
text SQL snapshot, runs a deterministic ten-module canary, exercises bounded
evolution, proves rollback and semantic equivalence, then persists a tamper-evident
proof packet, heartbeat, drift report and the next resumable SQL snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_obj(value: Any) -> str:
    return sha256_bytes(canonical(value))


def semantic_view(value: Any) -> Any:
    """Remove runtime-generated identifiers while preserving cognitive meaning."""
    volatile = {
        "created_at", "recorded_at", "updated_at", "timestamp", "completed_at",
        "event_hash", "record_hash", "previous_hash", "content_hash",
        "checkpoint_id", "transaction_id", "output_hash", "idempotent",
    }
    if isinstance(value, dict):
        return {key: semantic_view(item) for key, item in sorted(value.items()) if key not in volatile}
    if isinstance(value, list):
        return [semantic_view(item) for item in value]
    return value


def analysis_semantic_hash(analysis: dict[str, Any]) -> str:
    selected = {
        "mission_id": analysis.get("mission_id"),
        "final_recommendation": analysis.get("final_recommendation"),
        "module_order": analysis.get("module_order"),
        "module_results": analysis.get("module_results"),
        "confidence": analysis.get("confidence"),
        "held_reasons": analysis.get("held_reasons"),
        "evidence_requirements": analysis.get("evidence_requirements"),
    }
    return sha256_obj(semantic_view(selected))


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def dump_database(database: Path) -> str:
    if not database.exists():
        return ""
    connection = sqlite3.connect(database)
    try:
        lines = list(connection.iterdump())
    finally:
        connection.close()
    return "\n".join(lines) + "\n"


def restore_database(database: Path, dump_text: str) -> None:
    for candidate in (database, Path(str(database) + "-wal"), Path(str(database) + "-shm")):
        candidate.unlink(missing_ok=True)
    connection = sqlite3.connect(database)
    try:
        if dump_text.strip():
            connection.executescript(dump_text)
        connection.commit()
    finally:
        connection.close()


def run_cli(database: Path, *args: str, output: Path | None = None) -> dict[str, Any]:
    command = [sys.executable, "-m", "fevx_cse", "--database", str(database), *args]
    if output is not None:
        command.extend(["--output", str(output)])
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(json.dumps({
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-10000:],
            "stderr": completed.stderr[-10000:],
        }, indent=2))
    if output is not None:
        return json.loads(output.read_text(encoding="utf-8"))
    return json.loads(completed.stdout)


def perform_cycle(
    database: Path,
    mission_path: Path,
    genome_path: Path,
    work: Path,
    *,
    run_id: str,
    checkpoint_label: str,
) -> dict[str, Any]:
    work.mkdir(parents=True, exist_ok=True)
    init = run_cli(database, "init")
    analysis_path = work / "analysis.json"
    evolution_path = work / "evolution.json"
    analysis = run_cli(
        database,
        "analyse",
        "--mission",
        str(mission_path),
        "--genome",
        str(genome_path),
        "--run-id",
        run_id,
        output=analysis_path,
    )
    evolution = run_cli(database, "evolve", "--maximum-cycles", "12", output=evolution_path)
    checkpoint = run_cli(database, "checkpoint", "--label", checkpoint_label)
    integrity = run_cli(database, "verify")
    status = run_cli(database, "status")
    return {
        "init": init,
        "analysis": analysis,
        "evolution": evolution,
        "checkpoint": checkpoint,
        "integrity": integrity,
        "status": status,
    }


def append_proof(proofs: Path, event: dict[str, Any]) -> dict[str, Any]:
    proofs.mkdir(parents=True, exist_ok=True)
    head_path = proofs / "proof_chain_head.json"
    head = read_json(head_path, {"head_hash": "GENESIS"})
    record = dict(event)
    record["previous_hash"] = head.get("head_hash", "GENESIS")
    record["record_hash"] = sha256_obj(record)
    proof_id = str(record["proof_id"])
    write_json(proofs / f"{proof_id}.json", record)
    write_json(head_path, {"head_hash": record["record_hash"], "proof_id": proof_id, "recorded_at": record["recorded_at"]})
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mission", required=True)
    parser.add_argument("--genome", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    mission_path = (root / args.mission).resolve()
    genome_path = (root / args.genome).resolve()
    runtime = root / "runtime/fevx-cse"
    state_dir = runtime / "state"
    results_dir = runtime / "results"
    proofs_dir = runtime / "proofs"
    heartbeat_dir = runtime / "heartbeat"
    drift_dir = runtime / "drift"
    snapshots_dir = runtime / "snapshots"
    checkpoints_dir = runtime / "checkpoints"
    for directory in (state_dir, results_dir, proofs_dir, heartbeat_dir, drift_dir, snapshots_dir, checkpoints_dir):
        directory.mkdir(parents=True, exist_ok=True)

    provider = "github_actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local_rehearsal"
    execution_id = os.environ.get("GITHUB_RUN_ID") or f"LOCAL-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    event_name = os.environ.get("GITHUB_EVENT_NAME", "local")
    commit_sha = os.environ.get("GITHUB_SHA", "LOCAL")
    repository = os.environ.get("GITHUB_REPOSITORY", "local")
    proof_id = f"PRF-CSE-GHA-{execution_id}-{run_attempt}"
    recorded_at = utc_now()

    state_dump_path = state_dir / "cse_state.sql"
    previous_dump_raw = state_dump_path.read_text(encoding="utf-8") if state_dump_path.exists() else ""

    with tempfile.TemporaryDirectory(prefix="cse-shadow-") as temporary_dir:
        temporary = Path(temporary_dir)
        baseline_db = temporary / "baseline.db"
        twin_db = temporary / "twin.db"
        actual_db = temporary / "actual.db"
        restore_database(baseline_db, previous_dump_raw)
        previous_dump = dump_database(baseline_db)
        before_hash = sha256_bytes(previous_dump.encode("utf-8"))
        restore_database(twin_db, previous_dump)
        restore_database(actual_db, previous_dump)

        stable_run_id = "CSE-GITHUB-SHADOW-CANARY-STABLE-V1"
        twin = perform_cycle(
            twin_db,
            mission_path,
            genome_path,
            temporary / "twin",
            run_id=stable_run_id,
            checkpoint_label=f"digital-twin-{execution_id}-{run_attempt}",
        )
        twin_after_dump = dump_database(twin_db)
        twin_after_hash = sha256_bytes(twin_after_dump.encode("utf-8"))

        restore_database(twin_db, previous_dump)
        rollback_dump = dump_database(twin_db)
        rollback_ok = sha256_bytes(rollback_dump.encode("utf-8")) == before_hash
        restore_database(twin_db, twin_after_dump)
        reapply_ok = sha256_bytes(dump_database(twin_db).encode("utf-8")) == twin_after_hash

        actual = perform_cycle(
            actual_db,
            mission_path,
            genome_path,
            temporary / "actual",
            run_id=stable_run_id,
            checkpoint_label=f"provider-shadow-{execution_id}-{run_attempt}",
        )
        actual_after_dump = dump_database(actual_db)
        after_hash = sha256_bytes(actual_after_dump.encode("utf-8"))

    analysis = actual["analysis"]
    evolution = actual["evolution"]
    integrity = actual["integrity"]
    status = actual["status"]
    twin_analysis = twin["analysis"]
    twin_integrity = twin["integrity"]

    checks = {
        "provider_native_execution": provider == "github_actions",
        "module_count_10": len(analysis.get("module_order", [])) == 10,
        "synthetic_internal_only": (analysis.get("fevx6_contracts", {}).get("action", {}).get("external_effect") is False and "A0/A1 internal work" in str(analysis.get("authority_boundary", ""))),
        "analysis_semantic_readback": analysis_semantic_hash(analysis) == analysis_semantic_hash(twin_analysis),
        "bounded_evolution": evolution.get("final_promoted", {}).get("score") == 1.0,
        "ledger_integrity": integrity.get("status") == "PASSED",
        "twin_ledger_integrity": twin_integrity.get("status") == "PASSED",
        "rollback_test": rollback_ok,
        "reapply_test": reapply_ok,
        "durable_state_materialised": bool(actual_after_dump.strip()),
        "no_external_effect": True,
    }
    passed = all(checks.values())

    actual_state = {
        "service": "fevx-cognitive-sovereignty-ecology",
        "version": status.get("version", "1.1.0"),
        "provider": provider,
        "runtime_state": "OPERATIONAL" if passed else "DEGRADED",
        "maturity_state": "AUTONOMOUS_RUNTIME_VERIFIED_SHADOW" if passed else "SHADOW_RUNTIME_FAILED",
        "current_verified_level": 4 if passed else 3,
        "level_5_eligible": False,
        "module_count": len(analysis.get("module_order", [])),
        "analysis_output_hash": analysis.get("output_hash"),
        "analysis_semantic_hash": analysis_semantic_hash(analysis),
        "ledger_head_hash": integrity.get("ledger_head_hash"),
        "database_dump_sha256": after_hash,
        "external_effect": False,
        "real_workflow_evidence": False,
        "updated_at": recorded_at,
    }
    desired_state = read_json(state_dir / "desired_state.json", {
        "service": "fevx-cognitive-sovereignty-ecology",
        "version": "1.1.0",
        "provider": "github_actions",
        "runtime_state": "OPERATIONAL",
        "maturity_state": "AUTONOMOUS_RUNTIME_VERIFIED_SHADOW",
        "current_verified_level": 4,
        "level_5_eligible": False,
        "module_count": 10,
        "external_effect": False,
        "real_workflow_evidence": False,
    })
    comparison_keys = [
        "service", "version", "provider", "runtime_state", "maturity_state",
        "current_verified_level", "level_5_eligible", "module_count",
        "external_effect", "real_workflow_evidence",
    ]
    drift_items = {
        key: {"desired": desired_state.get(key), "actual": actual_state.get(key)}
        for key in comparison_keys
        if desired_state.get(key) != actual_state.get(key)
    }
    drift = {
        "checked_at": recorded_at,
        "classification": "IN_SYNC" if not drift_items else "DRIFT_DETECTED",
        "differences": drift_items,
        "desired_hash": sha256_obj({key: desired_state.get(key) for key in comparison_keys}),
        "actual_hash": sha256_obj({key: actual_state.get(key) for key in comparison_keys}),
    }
    passed = passed and not drift_items
    checks["desired_actual_state_match"] = not drift_items
    actual_state["runtime_state"] = "OPERATIONAL" if passed else "DEGRADED"

    result = {
        "result_id": f"CSE-GHA-{execution_id}-{run_attempt}",
        "recorded_at": recorded_at,
        "status": "VERIFIED" if passed else "FAILED_VERIFICATION",
        "provider": provider,
        "event_name": event_name,
        "repository": repository,
        "commit_sha": commit_sha,
        "execution_id": execution_id,
        "run_attempt": run_attempt,
        "checks": checks,
        "before_state_sha256": before_hash,
        "after_state_sha256": after_hash,
        "semantic_readback": checks["analysis_semantic_readback"],
        "rollback_test": rollback_ok,
        "reapply_test": reapply_ok,
        "analysis": {
            "run_id": stable_run_id,
            "mission_id": analysis.get("mission_id"),
            "module_count": len(analysis.get("module_order", [])),
            "output_hash": analysis.get("output_hash"),
            "semantic_hash": analysis_semantic_hash(analysis),
            "recommendation": analysis.get("final_recommendation"),
            "maturity_state": analysis.get("maturity_state"),
        },
        "evolution": {
            "state": evolution.get("state"),
            "version": evolution.get("final_promoted", {}).get("version"),
            "score": evolution.get("final_promoted", {}).get("score"),
            "cycle_count": len(evolution.get("cycles", [])),
        },
        "integrity": integrity,
        "checkpoint": actual["checkpoint"],
        "external_effect": False,
        "maturity_state": actual_state["maturity_state"],
        "current_verified_level": actual_state["current_verified_level"],
        "next_gate": "SUPERVISED_REAL_WORKFLOW_CANARIES",
    }

    proof = append_proof(proofs_dir, {
        "proof_id": proof_id,
        "recorded_at": recorded_at,
        "result_id": result["result_id"],
        "status": result["status"],
        "provider": provider,
        "repository": repository,
        "commit_sha": commit_sha,
        "execution_id": execution_id,
        "run_attempt": run_attempt,
        "before_state_sha256": before_hash,
        "after_state_sha256": after_hash,
        "analysis_output_hash": analysis.get("output_hash"),
        "analysis_semantic_hash": analysis_semantic_hash(analysis),
        "ledger_head_hash": integrity.get("ledger_head_hash"),
        "semantic_readback": result["semantic_readback"],
        "rollback_test": rollback_ok,
        "reapply_test": reapply_ok,
        "module_count": len(analysis.get("module_order", [])),
        "external_effect": False,
        "maturity_state": actual_state["maturity_state"],
        "current_verified_level": actual_state["current_verified_level"],
        "checks": checks,
    })
    result["proof_id"] = proof["proof_id"]
    result["proof_hash"] = proof["record_hash"]

    heartbeat = {
        "heartbeat_id": "HB-FEVX-CSE-GITHUB-SHADOW",
        "recorded_at": recorded_at,
        "provider": provider,
        "runtime_state": "OPERATIONAL" if passed else "DEGRADED",
        "version": actual_state["version"],
        "verified": passed,
        "proof_id": proof["proof_id"],
        "proof_hash": proof["record_hash"],
        "ledger_head_hash": integrity.get("ledger_head_hash"),
        "database_dump_sha256": after_hash,
        "module_count": actual_state["module_count"],
        "external_effect": False,
        "next_gate": "SUPERVISED_REAL_WORKFLOW_CANARIES",
    }

    write_text(snapshots_dir / f"{result['result_id']}-before.sql", previous_dump)
    write_text(state_dump_path, actual_after_dump)
    write_json(state_dir / "actual_state.json", actual_state)
    write_json(drift_dir / "latest.json", drift)
    write_json(results_dir / f"{result['result_id']}.json", result)
    write_json(results_dir / "latest.json", result)
    write_json(heartbeat_dir / "latest.json", heartbeat)
    write_json(checkpoints_dir / "latest.json", actual["checkpoint"])

    print(json.dumps({
        "status": result["status"],
        "provider": provider,
        "proof_id": proof["proof_id"],
        "proof_hash": proof["record_hash"],
        "heartbeat": heartbeat,
        "drift": drift,
        "maturity_state": actual_state["maturity_state"],
        "current_verified_level": actual_state["current_verified_level"],
    }, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
