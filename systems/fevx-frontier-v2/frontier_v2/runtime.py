from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from . import FRONTIER_SYSTEMS
from .core import digest, read_json, semantic, utc_now

BASE_SYSTEMS = ["TELOS", "KAIROS", "GALILEO", "PARALLAX", "SOCIUS", "PACTUM", "SEMIOTICA", "ARGUS", "PROMETHEUS", "PRAXIS"]


def verify_baseline(root: Path) -> dict[str, Any]:
    state = read_json(root / "runtime/fevx-cse/state/actual_state.json", {})
    result = read_json(root / "runtime/fevx-cse/results/latest.json", {})
    heartbeat = read_json(root / "runtime/fevx-cse/heartbeat/latest.json", {})
    drift = read_json(root / "runtime/fevx-cse/drift/latest.json", {})
    checks = {
        "level_4": state.get("current_verified_level") == 4,
        "ten_modules": state.get("module_count") == 10,
        "provider": state.get("provider") == "github_actions",
        "operational": state.get("runtime_state") == "OPERATIONAL",
        "verified_result": result.get("status") == "VERIFIED",
        "heartbeat": heartbeat.get("verified") is True,
        "drift": drift.get("classification") == "IN_SYNC",
        "no_external_effect": state.get("external_effect") is False and result.get("external_effect") is False,
    }
    if not all(checks.values()):
        raise RuntimeError({"baseline_checks": checks})
    return {"state": state, "result": result, "heartbeat": heartbeat, "drift": drift, "checks": checks}


def run_frontier(context: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for system in FRONTIER_SYSTEMS:
        output = system().run(context)
        results.append(output)
        context = {**context, "prior_frontier_results": results, output["system"].lower(): output}
    return results


def semantic_hash(results: list[dict[str, Any]]) -> str:
    return digest(semantic(results))


def inspect_v1_sql(root: Path) -> dict[str, Any]:
    dump_path = root / "runtime/fevx-cse/state/cse_state.sql"
    if not dump_path.exists():
        return {"available": False, "module_rows": 0}
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(dump_path.read_text(encoding="utf-8"))
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        count = 0
        if "module_results" in tables:
            count = connection.execute("SELECT COUNT(*) FROM module_results").fetchone()[0]
        return {"available": True, "module_rows": count, "sha256": digest(dump_path.read_bytes())}
    finally:
        connection.close()


def real_canaries(root: Path, release: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = verify_baseline(root)
    github = {
        "workflow_id": "REAL-GITHUB-CANONICAL-RUNTIME",
        "passed": all(baseline["checks"].values()),
        "evidence": {
            "proof_hash": baseline["result"].get("proof_hash"),
            "ledger_head": baseline["result"].get("integrity", {}).get("ledger_head_hash"),
            "drift": baseline["drift"].get("classification"),
        },
        "external_effect": False,
    }
    drive = release["drive"]
    drive_ok = (
        drive["candidate"]["size"] == 413425 and
        drive["wheel"]["size"] == 81493 and
        len(drive["candidate"].get("reader_service_accounts", [])) == 2 and
        len(drive["wheel"].get("reader_service_accounts", [])) == 2
    )
    drive_canary = {"workflow_id": "REAL-DRIVE-ARTIFACT-PROVENANCE", "passed": drive_ok, "evidence": drive, "external_effect": False}
    local = release["local_release"]
    release_ok = local["tests_passed"] == 76 and local["release_gates_passed"] == 11 and len(local["wheel_sha256"]) == 64
    release_canary = {"workflow_id": "REAL-CSE-V2-RELEASE-INTEGRITY", "passed": release_ok, "evidence": local, "external_effect": False}
    return [github, drive_canary, release_canary]


def build_result(run_id: str, provider: str, frontier: list[dict[str, Any]], canaries: list[dict[str, Any]], evolution: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    passed = len(frontier) == 10 and all(x["passed"] for x in canaries) and evolution["final_score"] == 1.0
    return {
        "run_id": run_id,
        "recorded_at": utc_now(),
        "provider": provider,
        "status": "VERIFIED" if passed else "FAILED_VERIFICATION",
        "module_count": 20,
        "base_modules": BASE_SYSTEMS,
        "frontier_modules": [x["system"] for x in frontier],
        "semantic_hash": semantic_hash(frontier),
        "current_verified_level": 5 if passed else 4,
        "maturity_state": "VERIFIED_SOVEREIGN_MISSION_ECOLOGY_SCOPED" if passed else "FRONTIER_SHADOW_FAILED",
        "level_6_eligible": False,
        "scope": [x["workflow_id"] for x in canaries if x["passed"]],
        "baseline_proof_hash": baseline["result"].get("proof_hash"),
        "evolution": evolution,
        "external_effect": False,
        "next_gate": "WORKFLOW_SPECIFIC_TRUSTED_AUTONOMY_DESIGN",
    }
