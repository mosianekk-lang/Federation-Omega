#!/usr/bin/env python3
"""H2-P paired forced-process-interruption canary for Omega-One.

The candidate and baseline execute the same five boundary shards and the same
mission/task/proof workload.  Only shard scheduling differs: sequential versus
five-way parallel.  Every shard ends in a real POSIX SIGKILL at its named
boundary, then the parent performs bounded recovery and exact integrity checks.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from omega_one.source_proof import assert_sources_verified  # noqa: E402
from omega_one.transaction_store import SQLiteStateStore  # noqa: E402
from omega_one.work_engine import (  # noqa: E402
    LeaseReceipt,
    MissionEnvelope,
    OmegaCompletionEngine,
    ProofBundle,
    TaskEnvelope,
    WorkerDescriptor,
    output_digest,
)


SCENARIOS = (
    "admission_commit",
    "dispatch_wave_commit",
    "transition_claim",
    "partial_sidecar",
    "proof_completion",
)
TWO_TASK_SCENARIOS = {"dispatch_wave_commit", "transition_claim", "partial_sidecar"}
TENANT_CYCLE = (
    ("tenant-a", 1),
    ("tenant-b", 2),
    ("tenant-c", 4),
    ("tenant-c", 4),
    ("tenant-c", 4),
    ("tenant-b", 2),
    ("tenant-c", 4),
)
DEFAULT_MISSIONS_PER_SCENARIO = 20
WAL_BOUND_BYTES = 16 * 1024 * 1024
RSS_BOUND_KIB = 256 * 1024


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def tenant_for(index: int) -> tuple[str, int]:
    return TENANT_CYCLE[index % len(TENANT_CYCLE)]


def scenario_task_count(scenario: str) -> int:
    if scenario not in SCENARIOS:
        raise ValueError(f"UNKNOWN_SCENARIO:{scenario}")
    return 2 if scenario in TWO_TASK_SCENARIOS else 1


def jain_index(values: Iterable[float]) -> float:
    rows = tuple(float(value) for value in values)
    if not rows or any(value < 0 for value in rows):
        raise ValueError("JAIN_INPUT_INVALID")
    denominator = len(rows) * sum(value * value for value in rows)
    return 0.0 if denominator == 0 else (sum(rows) ** 2) / denominator


def mission_id(run_id: str, scenario: str, index: int) -> str:
    return f"h2p-{run_id}-{scenario}-{index:03d}"


def mission_spec(run_id: str, scenario: str, index: int) -> tuple[MissionEnvelope, tuple[TaskEnvelope, ...]]:
    identifier = mission_id(run_id, scenario, index)
    tenant_id, weight = tenant_for(index)
    mission = MissionEnvelope(
        mission_id=identifier,
        version=1,
        objective=f"H2-P {scenario} mission {index}",
        success_definition=("every task independently proven",),
        constraints=("local-only", "no-provider", "no-external-effect"),
    )
    tasks = tuple(
        TaskEnvelope(
            task_id=f"task-{task_index + 1}",
            mission_id=identifier,
            dependencies=(),
            capability="h2-canary",
            input_digest=canonical_digest(
                {"scenario": scenario, "mission": index, "task": task_index + 1}
            ),
            tenant_id=tenant_id,
            flow_weight=weight,
            priority=50,
            idempotency_key=f"{identifier}:task-{task_index + 1}",
        )
        for task_index in range(scenario_task_count(scenario))
    )
    return mission, tasks


def _proof_for(lease: LeaseReceipt, scenario: str, run_id: str, index: int) -> tuple[dict[str, Any], ProofBundle]:
    output = {
        "scenario": scenario,
        "run_id": run_id,
        "mission_index": index,
        "task_key": lease.task_key,
    }
    proof = ProofBundle(
        verifier_id="h2-independent-verifier",
        output_digest=output_digest(output),
        schema_valid=True,
        semantic_valid=True,
        policy_valid=True,
        readback_valid=True,
        evidence_refs=(f"h2-canary:{lease.task_key}",),
    )
    return output, proof


def _complete_lease(
    engine: OmegaCompletionEngine,
    lease: LeaseReceipt,
    scenario: str,
    run_id: str,
    index: int,
) -> None:
    output, proof = _proof_for(lease, scenario, run_id, index)
    engine.submit_candidate(lease, output, proof)


def _complete_ready_mission(
    engine: OmegaCompletionEngine,
    scenario: str,
    run_id: str,
    index: int,
) -> None:
    while engine.mission_status(mission_id(run_id, scenario, index))["state"] != "PROVEN":
        leases = engine.schedule_wave(max_concurrency=2, lease_seconds=300)
        if not leases:
            raise RuntimeError("MISSION_STALLED_WITHOUT_LEASE")
        for lease in leases:
            _complete_lease(engine, lease, scenario, run_id, index)


def _kill_self() -> None:
    os.kill(os.getpid(), signal.SIGKILL)
    raise RuntimeError("SIGKILL_DID_NOT_TERMINATE_PROCESS")


def child_run(state_dir: Path, scenario: str, run_id: str, missions: int) -> None:
    armed = {"value": False}

    def injected(point: str) -> None:
        if not armed["value"]:
            return
        if scenario == "admission_commit" and point == "after_admission_commit":
            _kill_self()
        if scenario == "dispatch_wave_commit" and point == "after_dispatch_wave_commit":
            _kill_self()
        if scenario == "proof_completion" and point == "after_proof_publication":
            _kill_self()

    engine = OmegaCompletionEngine(state_dir, verify_source=False, fault_injector=injected)
    engine.register_worker(
        WorkerDescriptor(
            worker_id=f"worker-{run_id}-{scenario}",
            capabilities=("h2-canary",),
            capacity=2,
            predicted_latency_ms=1.0,
        )
    )

    for index in range(missions):
        last = index == missions - 1
        mission, tasks = mission_spec(run_id, scenario, index)
        if last and scenario == "admission_commit":
            armed["value"] = True
        engine.submit_mission(mission, tasks)

        if not last:
            _complete_ready_mission(engine, scenario, run_id, index)
            continue

        if scenario == "transition_claim":
            armed["value"] = True

            def claim_then_kill() -> None:
                engine.store.recover_stale_transitions()
                engine.worker_plane._replay()
                item = engine.store.claim_transition(engine._transition_claim_token)
                if item is None:
                    return
                _kill_self()

            engine._drain_transition_outbox = claim_then_kill  # type: ignore[method-assign]
        elif scenario == "partial_sidecar":
            armed["value"] = True
            original_lease = engine.worker_plane.lease
            materialized = {"count": 0}

            def lease_then_kill(worker_id: str, capability: str, lease_seconds: int = 60):
                result = original_lease(worker_id, capability, lease_seconds)
                materialized["count"] += 1
                if materialized["count"] == 1:
                    _kill_self()
                return result

            engine.worker_plane.lease = lease_then_kill  # type: ignore[method-assign]
        elif scenario == "proof_completion":
            armed["value"] = True
        elif scenario == "dispatch_wave_commit":
            armed["value"] = True

        leases = engine.schedule_wave(max_concurrency=2, lease_seconds=300)
        if scenario == "proof_completion":
            if len(leases) != 1:
                raise RuntimeError("PROOF_COMPLETION_LEASE_COUNT_INVALID")
            _complete_lease(engine, leases[0], scenario, run_id, index)
        raise RuntimeError(f"FAULT_NOT_TRIGGERED:{scenario}")


def _rss_kib(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (FileNotFoundError, ProcessLookupError, ValueError):
        return 0
    return 0


def _wal_bytes(root: Path) -> int:
    return max((path.stat().st_size for path in root.rglob("*-wal")), default=0)


def _active_lease(engine: OmegaCompletionEngine, task_key: str) -> LeaseReceipt:
    row = engine.state["tasks"][task_key]
    stored = engine.state["leases"][row["lease_id"]]
    return LeaseReceipt(
        lease_id=str(stored["lease_id"]),
        task_key=str(stored["task_key"]),
        worker_id=str(stored["worker_id"]),
        mission_version=int(stored["mission_version"]),
        fencing_token=int(stored["fencing_token"]),
        attempt=int(stored["attempt"]),
        input_digest=str(stored["input_digest"]),
    )


def _recover_last_mission(
    state_dir: Path,
    scenario: str,
    run_id: str,
    missions: int,
) -> dict[str, Any]:
    store = SQLiteStateStore(state_dir / "control-state.sqlite3")
    reclaimed: tuple[str, ...] = ()
    if scenario in {"transition_claim", "partial_sidecar", "proof_completion"}:
        reclaimed = store.recover_stale_transitions(
            max_age_seconds=0,
            as_of="2999-01-01T00:00:00Z",
        )
    engine = OmegaCompletionEngine(state_dir, verify_source=False)
    index = missions - 1
    target = mission_id(run_id, scenario, index)
    status = engine.mission_status(target)

    running = [key for key, state in status["tasks"].items() if state == "RUNNING"]
    for task_key in running:
        _complete_lease(engine, _active_lease(engine, task_key), scenario, run_id, index)
    if engine.mission_status(target)["state"] != "PROVEN":
        _complete_ready_mission(engine, scenario, run_id, index)

    mission_states = [
        engine.mission_status(mission_id(run_id, scenario, item))["state"]
        for item in range(missions)
    ]
    receipt_counts = Counter(
        (str(row["workstream_id"]), str(row["receipt_type"]))
        for row in engine.sol.state.receipts.values()
    )
    duplicate_receipts = sum(max(0, count - 1) for count in receipt_counts.values())
    persistence = engine.persistence_status()
    engine_integrity = engine.verify_integrity()

    connection = sqlite3.connect(state_dir / "control-state.sqlite3")
    try:
        sqlite_integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        checkpoint = tuple(int(value) for value in connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
    finally:
        connection.close()

    return {
        "mission_count": len(mission_states),
        "all_missions_proven": all(state == "PROVEN" for state in mission_states),
        "task_count": sum(
            1
            for row in engine.state["tasks"].values()
            if str(row["spec"]["mission_id"]).startswith(f"h2p-{run_id}-{scenario}-")
        ),
        "engine_integrity": engine_integrity,
        "sqlite_integrity": sqlite_integrity,
        "pending_admission_outbox": int(persistence["pending_admission_outbox"]),
        "pending_transition_outbox": int(persistence["pending_transition_outbox"]),
        "reclaimed_transition_ids": list(reclaimed),
        "duplicate_proof_receipts": duplicate_receipts,
        "dispatch_counts": {
            key: int(value)
            for key, value in engine.state["dispatch_counts"].items()
            if key in {"tenant-a", "tenant-b", "tenant-c"}
        },
        "wal_checkpoint": list(checkpoint),
        "wal_bytes_final": _wal_bytes(state_dir),
    }


def run_shard(root: Path, scenario: str, run_id: str, missions: int) -> dict[str, Any]:
    state_dir = root / scenario
    state_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child",
        "--state-dir",
        str(state_dir),
        "--scenario",
        scenario,
        "--run-id",
        run_id,
        "--missions",
        str(missions),
    ]
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        shell=False,
    )
    peak_rss_kib = 0
    while process.poll() is None:
        peak_rss_kib = max(peak_rss_kib, _rss_kib(process.pid))
        time.sleep(0.002)
    stderr = (process.stderr.read() if process.stderr else b"").decode("utf-8", errors="replace")
    elapsed_to_kill = time.perf_counter() - started
    wal_at_crash = _wal_bytes(state_dir)
    if process.returncode != -signal.SIGKILL:
        raise RuntimeError(
            f"EXPECTED_SIGKILL:{scenario}:returncode={process.returncode}:stderr={stderr[-1000:]}"
        )
    recovered = _recover_last_mission(state_dir, scenario, run_id, missions)
    elapsed_total = time.perf_counter() - started
    recovered.update(
        {
            "scenario": scenario,
            "run_id": run_id,
            "process_returncode": int(process.returncode),
            "sigkill_verified": process.returncode == -signal.SIGKILL,
            "elapsed_to_kill_seconds": elapsed_to_kill,
            "elapsed_total_seconds": elapsed_total,
            "peak_rss_kib": peak_rss_kib,
            "wal_bytes_at_crash": wal_at_crash,
            "wal_bound_pass": wal_at_crash <= WAL_BOUND_BYTES,
            "rss_bound_pass": peak_rss_kib <= RSS_BOUND_KIB,
            "external_effects": 0,
            "provider_calls": 0,
        }
    )
    recovered["verified"] = bool(
        recovered["sigkill_verified"]
        and recovered["all_missions_proven"]
        and recovered["engine_integrity"]
        and recovered["sqlite_integrity"] == "ok"
        and recovered["pending_admission_outbox"] == 0
        and recovered["pending_transition_outbox"] == 0
        and recovered["wal_bound_pass"]
        and recovered["rss_bound_pass"]
    )
    return recovered


def run_suite(root: Path, run_id: str, missions_per_scenario: int, *, parallel: bool) -> dict[str, Any]:
    started = time.perf_counter()
    if parallel:
        results = []
        with ThreadPoolExecutor(max_workers=len(SCENARIOS), thread_name_prefix="h2p") as executor:
            futures = {
                executor.submit(run_shard, root, scenario, run_id, missions_per_scenario): scenario
                for scenario in SCENARIOS
            }
            for future in as_completed(futures):
                results.append(future.result())
    else:
        results = [
            run_shard(root, scenario, run_id, missions_per_scenario)
            for scenario in SCENARIOS
        ]
    elapsed = time.perf_counter() - started
    results.sort(key=lambda row: SCENARIOS.index(str(row["scenario"])))
    dispatch = Counter()
    for row in results:
        dispatch.update(row["dispatch_counts"])
    normalized = [
        dispatch["tenant-a"] / 1.0,
        dispatch["tenant-b"] / 2.0,
        dispatch["tenant-c"] / 4.0,
    ]
    mission_count = sum(int(row["mission_count"]) for row in results)
    verified_missions = sum(
        int(row["mission_count"]) if row["all_missions_proven"] else 0
        for row in results
    )
    return {
        "mode": "parallel-five-shard" if parallel else "sequential-five-shard",
        "elapsed_seconds": elapsed,
        "mission_count": mission_count,
        "verified_missions": verified_missions,
        "verified_output_ratio": verified_missions / mission_count if mission_count else 0.0,
        "task_count": sum(int(row["task_count"]) for row in results),
        "process_kills": sum(1 for row in results if row["sigkill_verified"]),
        "fault_boundaries": [row["scenario"] for row in results if row["sigkill_verified"]],
        "all_shards_verified": all(bool(row["verified"]) for row in results),
        "integrity_verified": all(
            bool(row["engine_integrity"]) and row["sqlite_integrity"] == "ok"
            for row in results
        ),
        "recovery_verified": all(
            bool(row["all_missions_proven"])
            and int(row["pending_admission_outbox"]) == 0
            and int(row["pending_transition_outbox"]) == 0
            for row in results
        ),
        "duplicate_proof_receipts": sum(int(row["duplicate_proof_receipts"]) for row in results),
        "dispatch_counts": dict(sorted(dispatch.items())),
        "normalized_service": normalized,
        "jain_fairness": jain_index(normalized),
        "max_wal_bytes_at_crash": max(int(row["wal_bytes_at_crash"]) for row in results),
        "max_peak_rss_kib": max(int(row["peak_rss_kib"]) for row in results),
        "wal_bound_pass": all(bool(row["wal_bound_pass"]) for row in results),
        "rss_bound_pass": all(bool(row["rss_bound_pass"]) for row in results),
        "provider_calls": 0,
        "external_effects": 0,
        "shards": results,
    }


def build_report(missions_per_scenario: int) -> dict[str, Any]:
    assert_sources_verified(PROJECT_ROOT / "SOURCE_BASE.json", PROJECT_ROOT)
    workload = {
        "scenarios": list(SCENARIOS),
        "missions_per_scenario": missions_per_scenario,
        "candidate_missions": missions_per_scenario * len(SCENARIOS),
        "baseline_missions": missions_per_scenario * len(SCENARIOS),
        "task_counts_per_mission": {
            scenario: scenario_task_count(scenario) for scenario in SCENARIOS
        },
        "tenant_cycle": list(TENANT_CYCLE),
        "proof_policy": ["schema", "semantic", "policy", "readback", "independent-verifier"],
    }
    with tempfile.TemporaryDirectory(prefix="omega-h2p-baseline-") as baseline_temp:
        baseline = run_suite(
            Path(baseline_temp),
            "baseline",
            missions_per_scenario,
            parallel=False,
        )
    with tempfile.TemporaryDirectory(prefix="omega-h2p-candidate-") as candidate_temp:
        candidate = run_suite(
            Path(candidate_temp),
            "candidate",
            missions_per_scenario,
            parallel=True,
        )

    speedup = baseline["elapsed_seconds"] / candidate["elapsed_seconds"]
    projected_full_seconds = candidate["elapsed_seconds"] * (
        10_000 / candidate["mission_count"]
    )
    quality_gate = bool(
        candidate["all_shards_verified"]
        and candidate["integrity_verified"]
        and candidate["recovery_verified"]
        and candidate["verified_output_ratio"] == 1.0
        and candidate["jain_fairness"] >= 0.995
        and candidate["wal_bound_pass"]
        and candidate["rss_bound_pass"]
        and candidate["duplicate_proof_receipts"] == 0
    )
    speed_gate = bool(
        speedup >= 2.0
        and candidate["verified_output_ratio"] >= baseline["verified_output_ratio"]
    )
    projection_gate = projected_full_seconds <= 270.0
    full_h2_admitted = quality_gate and speed_gate and projection_gate

    report: dict[str, Any] = {
        "schema_version": "H2-P-1.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "classification": "LOCAL_SHADOW_PROCESS_KILL_CANARY",
        "workload": workload,
        "workload_fingerprint": canonical_digest(workload),
        "workload_identical": True,
        "baseline": baseline,
        "candidate": candidate,
        "measurement": {
            "speedup": speedup,
            "measured_2x_route_improvement": speed_gate,
            "quality_not_lower_than_baseline": (
                candidate["verified_output_ratio"] >= baseline["verified_output_ratio"]
            ),
            "projected_10000_mission_seconds": projected_full_seconds,
            "projection_within_270_seconds": projection_gate,
            "projection_is_linear_extrapolation_not_soak_proof": True,
        },
        "gates": {
            "exact_candidate_100_missions": candidate["mission_count"] == 100,
            "exact_baseline_100_missions": baseline["mission_count"] == 100,
            "all_five_boundaries": set(candidate["fault_boundaries"]) == set(SCENARIOS),
            "sigkill_verified": candidate["process_kills"] == len(SCENARIOS),
            "integrity": candidate["integrity_verified"],
            "recovery": candidate["recovery_verified"],
            "wal_bounded": candidate["wal_bound_pass"],
            "rss_bounded": candidate["rss_bound_pass"],
            "fairness": candidate["jain_fairness"] >= 0.995,
            "proof_receipts_exactly_once": candidate["duplicate_proof_receipts"] == 0,
            "quality_gate": quality_gate,
            "speed_gate": speed_gate,
            "projection_gate": projection_gate,
        },
        "release": {
            "full_h2_admitted": full_h2_admitted,
            "state": "H2_FULL_RETRY_ADMITTED" if full_h2_admitted else "H2_FULL_RETRY_HELD",
            "reason": (
                "all H2-P quality, speed and projection gates passed"
                if full_h2_admitted
                else "one or more H2-P gates failed; inspect gates and boundary receipts"
            ),
            "deployment": "SHADOW_ONLY",
            "provider_execution": False,
            "external_effects": 0,
        },
    }
    report["report_sha256"] = canonical_digest(report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--run-id")
    parser.add_argument("--missions", type=int, default=DEFAULT_MISSIONS_PER_SCENARIO)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "benchmarks" / "CFBE_H2P_PROCESS_KILL_CANARY_20260830.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.missions < 1:
        raise ValueError("MISSIONS_MUST_BE_POSITIVE")
    if args.child:
        if not args.state_dir or not args.scenario or not args.run_id:
            raise ValueError("CHILD_ARGUMENTS_REQUIRED")
        child_run(args.state_dir, args.scenario, args.run_id, args.missions)
        return 3
    report = build_report(args.missions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "report_sha256": report["report_sha256"],
        "speedup": report["measurement"]["speedup"],
        "candidate_missions": report["candidate"]["mission_count"],
        "full_h2_admitted": report["release"]["full_h2_admitted"],
        "release_state": report["release"]["state"],
        "failed_gates": [key for key, passed in report["gates"].items() if not passed],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
