#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
import shutil
import tempfile
from pathlib import Path
from frontier_v2.core import digest, read_json, semantic, utc_now, write_json
from frontier_v2.evolution import evolve
from frontier_v2.runtime import build_result, inspect_v1_sql, real_canaries, run_frontier, verify_baseline
from frontier_v2.store import dump_database, restore_database, save_run, verify_chain
def proof_record(result, head, before_hash, after_hash, rollback, reapply):
    return {
        "proof_id": f"PRF-FRONTIER-{result['run_id']}",
        "recorded_at": result["recorded_at"],
        "status": result["status"],
        "provider": result["provider"],
        "module_count": result["module_count"],
        "semantic_hash": result["semantic_hash"],
        "before_state_sha256": before_hash,
        "after_state_sha256": after_hash,
        "ledger_head_hash": head,
        "rollback_test": rollback,
        "reapply_test": reapply,
        "workflow_scope": result["scope"],
        "current_verified_level": result["current_verified_level"],
        "external_effect": False,
    }
def append_proof(directory: Path, proof: dict) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    head_path = directory / "proof_chain_head.json"
    previous = read_json(head_path, {"head_hash": "GENESIS"})
    record = {**proof, "previous_hash": previous["head_hash"]}
    record["record_hash"] = digest(record)
    write_json(directory / f"{record['proof_id']}.json", record)
    write_json(head_path, {"proof_id": record["proof_id"], "head_hash": record["record_hash"], "recorded_at": record["recorded_at"]})
    return record
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--context", default="systems/fevx-frontier-v2/context.json")
    parser.add_argument("--release", default="systems/fevx-frontier-v2/release_evidence.json")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    runtime = root / "runtime/fevx-frontier"
    for name in ("state", "results", "proofs", "heartbeat", "drift", "checkpoints", "snapshots"):
        (runtime / name).mkdir(parents=True, exist_ok=True)
    context = read_json(root / args.context)
    release = read_json(root / args.release)
    provider = "github_actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local_rehearsal"
    execution_id = os.environ.get("GITHUB_RUN_ID") or f"LOCAL-{utc_now().replace(':','').replace('-','')}"
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    run_id = f"CSE-V2-{execution_id}-{attempt}"
    baseline = verify_baseline(root)
    prior_sql_path = runtime / "state/frontier_state.sql"
    prior_sql = prior_sql_path.read_text(encoding="utf-8") if prior_sql_path.exists() else ""
    with tempfile.TemporaryDirectory(prefix="fevx-frontier-") as temp:
        temp = Path(temp)
        before_db, twin_db, actual_db = temp / "before.db", temp / "twin.db", temp / "actual.db"
        restore_database(before_db, prior_sql)
        canonical_before = dump_database(before_db)
        before_hash = digest(canonical_before.encode())
        restore_database(twin_db, canonical_before)
        restore_database(actual_db, canonical_before)
        twin_frontier = run_frontier(dict(context))
        actual_frontier = run_frontier(dict(context))
        semantic_readback = digest(semantic(twin_frontier)) == digest(semantic(actual_frontier))
        evolution = evolve(actual_db)
        canaries = real_canaries(root, release)
        result = build_result(run_id, provider, actual_frontier, canaries, evolution, baseline)
        result["semantic_readback"] = semantic_readback
        result["v1_sql_inspection"] = inspect_v1_sql(root)
        if not semantic_readback:
            result["status"] = "FAILED_VERIFICATION"
            result["current_verified_level"] = 4
        head = save_run(actual_db, result, actual_frontier, canaries)
        after_sql = dump_database(actual_db)
        after_hash = digest(after_sql.encode())
        restore_database(twin_db, canonical_before)
        rollback_ok = digest(dump_database(twin_db).encode()) == before_hash
        restore_database(twin_db, after_sql)
        reapply_ok = digest(dump_database(twin_db).encode()) == after_hash
        integrity = verify_chain(actual_db)
    passed = result["status"] == "VERIFIED" and rollback_ok and reapply_ok and integrity["status"] == "PASSED"
    if not passed:
        result["status"] = "FAILED_VERIFICATION"
        result["current_verified_level"] = 4
        result["maturity_state"] = "FRONTIER_SHADOW_FAILED"
    prior_sql_path.write_text(after_sql, encoding="utf-8")
    proof = append_proof(runtime / "proofs", proof_record(result, head, before_hash, after_hash, rollback_ok, reapply_ok))
    result.update({
        "proof_id": proof["proof_id"], "proof_hash": proof["record_hash"],
        "ledger_head_hash": head, "database_dump_sha256": after_hash,
        "rollback_test": rollback_ok, "reapply_test": reapply_ok,
        "integrity": integrity, "real_workflows": canaries,
    })
    write_json(runtime / "results/latest.json", result)
    actual_state = {
        "service": "fevx-cognitive-sovereignty-ecology",
        "version": "2.0.0",
        "provider": provider,
        "runtime_state": "OPERATIONAL" if passed else "DEGRADED",
        "maturity_state": result["maturity_state"],
        "current_verified_level": result["current_verified_level"],
        "level_6_eligible": False,
        "module_count": 20,
        "verified_workflow_count": sum(x["passed"] for x in canaries),
        "workflow_scope": result["scope"],
        "database_dump_sha256": after_hash,
        "ledger_head_hash": head,
        "proof_hash": proof["record_hash"],
        "external_effect": False,
        "updated_at": result["recorded_at"],
    }
    desired = read_json(runtime / "state/desired_state.json", actual_state)
    keys = ["service", "version", "provider", "runtime_state", "maturity_state", "current_verified_level", "level_6_eligible", "module_count", "verified_workflow_count", "external_effect"]
    differences = {k: {"desired": desired.get(k), "actual": actual_state.get(k)} for k in keys if desired.get(k) != actual_state.get(k)}
    drift = {"recorded_at": result["recorded_at"], "classification": "IN_SYNC" if not differences else "DRIFT_DETECTED", "differences": differences, "desired_hash": digest({k: desired.get(k) for k in keys}), "actual_hash": digest({k: actual_state.get(k) for k in keys})}
    if differences:
        actual_state["runtime_state"] = "DEGRADED"
    write_json(runtime / "state/actual_state.json", actual_state)
    write_json(runtime / "drift/latest.json", drift)
    write_json(runtime / "heartbeat/latest.json", {
        "heartbeat_id": "HB-FEVX-CSE-V2-FRONTIER", "recorded_at": result["recorded_at"],
        "provider": provider, "runtime_state": actual_state["runtime_state"], "verified": passed and not differences,
        "module_count": 20, "verified_workflow_count": actual_state["verified_workflow_count"],
        "proof_id": proof["proof_id"], "proof_hash": proof["record_hash"], "ledger_head_hash": head,
        "database_dump_sha256": after_hash, "next_gate": result["next_gate"], "external_effect": False,
    })
    write_json(runtime / "checkpoints/latest.json", {"recorded_at": result["recorded_at"], "run_id": run_id, "proof_hash": proof["record_hash"], "database_dump_sha256": after_hash, "module_count": 20, "workflow_count": actual_state["verified_workflow_count"]})
    write_json(runtime / "snapshots/rollback.json", {"before_state_sha256": before_hash, "after_state_sha256": after_hash, "rollback_test": rollback_ok, "reapply_test": reapply_ok})
    print(result["status"], result["current_verified_level"], proof["record_hash"])
    return 0 if passed and not differences else 1
if __name__ == "__main__":
    raise SystemExit(main())
