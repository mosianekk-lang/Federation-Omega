#!/usr/bin/env python3
"""True single-state H2-F court for the Omega-One Wave-2 kernel.

The court keeps one continuously growing control/SOL/worker state, uses 10,000
globally unique missions, maintains a saturated 1:2:4 tenant backlog, and
forces 24 real SIGKILL interruptions across eight proof-finalization points.
It is local shadow evidence only: it does not invoke providers or prove a
multi-host deployment.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import signal
import sqlite3
import subprocess
import sys
import time
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from omega_one.transaction_store import SQLiteStateStore  # noqa: E402
from omega_one.work_engine import (  # noqa: E402
    MissionEnvelope,
    OmegaCompletionEngine,
    ProofBundle,
    TaskEnvelope,
    WorkerDescriptor,
    output_digest,
)


TENANTS = (("tenant-c", 4), ("tenant-c", 4), ("tenant-c", 4), ("tenant-c", 4), ("tenant-b", 2), ("tenant-b", 2), ("tenant-a", 1))
BOUNDARIES = (
    "after_proof_intent_commit",
    "transition_claimed",
    "after_proof_worker_completion",
    "after_proof_result_receipt",
    "after_proof_independent_receipt",
    "after_completion_evaluation",
    "after_proof_publication",
    "after_final_atomic_commit",
)
FAULT_ORDINALS = (700, 5000, 9300)
BACKLOG_TARGET = 700
BACKLOG_FLOOR = 50
WAL_LIMIT_BYTES = 16 * 1024 * 1024
RSS_LIMIT_KIB = 384 * 1024
RSS_TO_STATE_LIMIT = 2.0


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile(values: Iterable[float], q: float) -> float:
    rows = sorted(float(value) for value in values)
    if not rows:
        return 0.0
    position = (len(rows) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return rows[lower]
    return rows[lower] + (rows[upper] - rows[lower]) * (position - lower)


def jain(values: Iterable[float]) -> float:
    rows = tuple(float(value) for value in values)
    denominator = len(rows) * sum(value * value for value in rows)
    return 0.0 if not rows or denominator == 0 else sum(rows) ** 2 / denominator


def mission_id(index: int) -> str:
    return f"h2f-single-state-{index:05d}"


def mission_spec(index: int) -> tuple[MissionEnvelope, tuple[TaskEnvelope, ...]]:
    identifier = mission_id(index)
    tenant, weight = TENANTS[index % len(TENANTS)]
    mission = MissionEnvelope(
        identifier,
        1,
        f"H2-F unique mission {index}",
        ("one independently proven local task",),
        ("local-shadow", "no-provider", "single-state"),
    )
    task = TaskEnvelope(
        task_id="task-1",
        mission_id=identifier,
        dependencies=(),
        capability="h2f-canary",
        input_digest=canonical_digest({"mission": index, "tenant": tenant}),
        tenant_id=tenant,
        flow_weight=weight,
        idempotency_key=f"{identifier}:task-1",
    )
    return mission, (task,)


def metrics_connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=30)
    # This is a small ancillary measurement ledger, not the system under test.
    # DELETE+FULL avoids losing its final frames when the child exits while the
    # control-plane WAL deliberately remains open for crash recovery.
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute("PRAGMA synchronous=FULL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS completions(
          task_key TEXT PRIMARY KEY, latency_seconds REAL NOT NULL, recovery INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS dispatches(
          seq INTEGER PRIMARY KEY AUTOINCREMENT, task_key TEXT NOT NULL,
          tenant TEXT NOT NULL, saturated INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS startups(
          process_index INTEGER PRIMARY KEY, seconds REAL NOT NULL
        );
        """
    )
    connection.commit()
    return connection


def append_witness(path: Path, payload: dict[str, Any]) -> None:
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    with path.open("ab") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def witnessed(path: Path) -> set[tuple[int, str]]:
    if not path.exists():
        return set()
    result = set()
    with path.open("rb") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                result.add((int(row["ordinal"]), str(row["boundary"])))
    return result


def raw_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("rb") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def child_main(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    control_path = state_dir / "control-state.sqlite3"
    if control_path.exists():
        recovery_store = SQLiteStateStore(control_path)
        future = "2999-01-01T00:00:00Z"
        recovery_store.recover_stale_outbox(max_age_seconds=0, as_of=future)
        recovery_store.recover_stale_transitions(max_age_seconds=0, as_of=future)

    start = time.perf_counter()
    active = {"ordinal": 0, "started": 0.0, "task_key": ""}
    seen_faults = witnessed(Path(args.witness_file))
    schedule = {
        ordinal + offset: boundary
        for ordinal in FAULT_ORDINALS
        for offset, boundary in enumerate(BOUNDARIES)
    }
    metrics = metrics_connect(Path(args.metrics_db))

    def record_completion(task_key: str, latency: float, recovery: bool) -> None:
        metrics.execute(
            "INSERT OR REPLACE INTO completions(task_key,latency_seconds,recovery) VALUES(?,?,?)",
            (task_key, max(0.0, float(latency)), int(recovery)),
        )
        metrics.commit()

    def maybe_kill(boundary: str) -> None:
        ordinal = int(active["ordinal"])
        if not ordinal or schedule.get(ordinal) != boundary or (ordinal, boundary) in seen_faults:
            return
        if boundary == "after_final_atomic_commit" and active["task_key"]:
            record_completion(active["task_key"], time.perf_counter() - float(active["started"]), False)
        append_witness(
            Path(args.witness_file),
            {"ordinal": ordinal, "boundary": boundary, "pid": os.getpid(), "at_ns": time.monotonic_ns()},
        )
        os.kill(os.getpid(), signal.SIGKILL)
        raise RuntimeError("SIGKILL_DID_NOT_TERMINATE")

    def injected(point: str) -> None:
        if point in BOUNDARIES:
            maybe_kill(point)

    engine = OmegaCompletionEngine(state_dir, verify_source=False, fault_injector=injected)
    startup_seconds = time.perf_counter() - start
    metrics.execute(
        "INSERT OR REPLACE INTO startups(process_index,seconds) VALUES(?,?)",
        (int(args.process_index), startup_seconds),
    )
    metrics.commit()

    # A recovered pending transition may have completed before fault wrappers
    # were installed; record its bounded startup recovery latency if needed.
    for task_key in engine.state["certificates"]:
        metrics.execute(
            "INSERT OR IGNORE INTO completions(task_key,latency_seconds,recovery) VALUES(?,?,1)",
            (task_key, startup_seconds),
        )
    metrics.commit()

    if "h2f-worker" not in engine.state["workers"]:
        engine.register_worker(
            WorkerDescriptor(
                worker_id="h2f-worker",
                capabilities=("h2f-canary",),
                capacity=1,
                predicted_latency_ms=1.0,
            )
        )
    engine.recover_expired_leases(as_of="2999-01-01T00:00:00Z")

    original_claim = engine.store.claim_transition

    def claim_transition(*claim_args: Any, **claim_kwargs: Any):
        item = original_claim(*claim_args, **claim_kwargs)
        if item is not None:
            maybe_kill("transition_claimed")
        return item

    engine.store.claim_transition = claim_transition  # type: ignore[method-assign]

    original_evaluate = engine._evaluate_sol_completion_once

    def evaluate_then_fault(workstream_id: str, publication_id: str):
        result = original_evaluate(workstream_id, publication_id)
        maybe_kill("after_completion_evaluation")
        return result

    engine._evaluate_sol_completion_once = evaluate_then_fault  # type: ignore[method-assign]

    original_delta = engine.store.commit_delta

    def commit_delta_then_fault(**kwargs: Any):
        result = original_delta(**kwargs)
        if kwargs.get("applied_transition") is not None:
            maybe_kill("after_final_atomic_commit")
        return result

    engine.store.commit_delta = commit_delta_then_fault  # type: ignore[method-assign]

    total = int(args.missions)
    while len(engine.state["certificates"]) < total:
        ready = len(engine._ready_task_keys)
        admitted = len(engine.state["missions"])
        while admitted < total and ready < BACKLOG_TARGET:
            mission, tasks = mission_spec(admitted)
            engine.submit_mission(mission, tasks)
            admitted += 1
            ready += 1

        ready_counts = Counter(
            engine.state["tasks"][key]["spec"]["tenant_id"] for key in engine._ready_task_keys
        )
        saturated = all(ready_counts[tenant] >= BACKLOG_FLOOR for tenant, _ in TENANTS)
        lease = engine.schedule_next(lease_seconds=300)
        if lease is None:
            raise RuntimeError("H2F_STALLED_WITHOUT_LEASE")
        tenant = engine.state["tasks"][lease.task_key]["spec"]["tenant_id"]
        metrics.execute(
            "INSERT INTO dispatches(task_key,tenant,saturated) VALUES(?,?,?)",
            (lease.task_key, tenant, int(saturated)),
        )
        metrics.commit()

        ordinal = len(engine.state["certificates"]) + 1
        active.update(ordinal=ordinal, started=time.perf_counter(), task_key=lease.task_key)
        output = {"task_key": lease.task_key, "ordinal": ordinal, "local_shadow": True}
        proof = ProofBundle(
            verifier_id="h2f-independent-verifier",
            output_digest=output_digest(output),
            schema_valid=True,
            semantic_valid=True,
            policy_valid=True,
            readback_valid=True,
            evidence_refs=(f"h2f:{lease.task_key}",),
        )
        engine.submit_candidate(lease, output, proof)
        record_completion(lease.task_key, time.perf_counter() - float(active["started"]), False)
        active.update(ordinal=0, started=0.0, task_key="")

    metrics.close()
    return 0


def rss_kib(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith(("VmRSS:", "VmHWM:")):
                yield_value = int(line.split()[1])
                if line.startswith("VmHWM:"):
                    return yield_value
        return 0
    except (FileNotFoundError, ProcessLookupError, ValueError):
        return 0


def final_report(args: argparse.Namespace, wall_seconds: float, peak_rss: int, peak_wal: int, cpu_seconds: float, process_count: int) -> dict[str, Any]:
    state_dir = Path(args.state_dir)
    engine = OmegaCompletionEngine(state_dir, verify_source=False)
    metrics = sqlite3.connect(args.metrics_db)
    completion_rows = list(metrics.execute("SELECT task_key,latency_seconds,recovery FROM completions"))
    dispatch_rows = list(metrics.execute("SELECT tenant,saturated FROM dispatches ORDER BY seq"))
    startup_rows = [float(row[0]) for row in metrics.execute("SELECT seconds FROM startups ORDER BY process_index")]
    known_completion_keys = {str(row[0]) for row in completion_rows}
    missing_completion_keys = sorted(set(engine.state["certificates"]) - known_completion_keys)
    conservative_recovery_latency = max(startup_rows, default=0.0)
    for task_key in missing_completion_keys:
        metrics.execute(
            "INSERT OR IGNORE INTO completions(task_key,latency_seconds,recovery) VALUES(?,?,1)",
            (task_key, conservative_recovery_latency),
        )
    if missing_completion_keys:
        metrics.commit()
        completion_rows = list(metrics.execute("SELECT task_key,latency_seconds,recovery FROM completions"))
    metrics.close()

    sol_events = raw_events(state_dir / "sol" / "events.jsonl")
    worker_events = raw_events(state_dir / "worker" / "worker-events.jsonl")
    sol_types = Counter(row["event_type"] for row in sol_events)
    receipt_types = Counter(
        row["payload"]["receipt_type"] for row in sol_events if row["event_type"] == "RECEIPT_RECORDED"
    )
    worker_types = Counter(row["event_type"] for row in worker_events)
    control_types = Counter(row["type"] for row in engine.state["events"])
    total = int(args.missions)
    exact_cardinality = {
        "result_receipts": receipt_types["RESULT"],
        "independent_proof_receipts": receipt_types["INDEPENDENT_PROOF"],
        "completion_evaluations": sol_types["COMPLETION_EVALUATED"],
        "reliability_updates": sol_types["RELIABILITY_UPDATED"],
        "worker_completions": worker_types["JOB_COMPLETED"],
        "task_proven_events": control_types["TASK_PROVEN"],
        "certificates": len(engine.state["certificates"]),
    }
    cardinality_pass = all(value == total for value in exact_cardinality.values())

    saturated_tenants = [tenant for tenant, saturated in dispatch_rows if saturated]
    window_scores = []
    for start in range(0, max(0, len(saturated_tenants) - 699), 70):
        window = saturated_tenants[start : start + 700]
        if len(window) < 700:
            continue
        counts = Counter(window)
        window_scores.append(jain((counts["tenant-a"] / 1, counts["tenant-b"] / 2, counts["tenant-c"] / 4)))
    gaps: dict[str, int] = {}
    for tenant in ("tenant-a", "tenant-b", "tenant-c"):
        positions = [index for index, value in enumerate(saturated_tenants) if value == tenant]
        gaps[tenant] = max((right - left - 1 for left, right in zip(positions, positions[1:])), default=0)

    witnesses = witnessed(Path(args.witness_file))
    expected_faults = {
        (ordinal + offset, boundary)
        for ordinal in FAULT_ORDINALS
        for offset, boundary in enumerate(BOUNDARIES)
    }
    status = engine.store.status()
    active_leases = sum(1 for row in engine.state["leases"].values() if row.get("active"))
    running_workers = sum(int(row["running"]) for row in engine.state["workers"].values())
    state_bytes = sum(path.stat().st_size for path in state_dir.rglob("*") if path.is_file())
    rss_to_state_ratio = (peak_rss * 1024) / state_bytes if state_bytes else float("inf")
    latencies = [float(row[1]) for row in completion_rows]
    source_files = (
        "omega_one/work_engine.py",
        "omega_one/transaction_store.py",
        "sol_61_runtime/runtime.py",
        "sol_61_runtime/worker.py",
        "benchmarks/run_h2f_single_state.py",
    )
    source_hashes = {name: sha256_file(PROJECT_ROOT / name) for name in source_files}

    gates = {
        "ten_thousand_unique_missions": len(engine.state["missions"]) == total == len(set(engine.state["missions"])),
        "ten_thousand_proven_tasks": len(engine.state["tasks"]) == total and len(engine.state["certificates"]) == total,
        "exact_raw_event_cardinality": cardinality_pass,
        "twenty_four_witnessed_sigkills": witnesses == expected_faults,
        "sqlite_and_journal_integrity": engine.verify_integrity() and engine.sol.verify_event_chain() and engine.worker_plane.verify_event_chain(),
        "zero_pending_work": status["pending_outbox"] == 0 and status["pending_transition_outbox"] == 0 and active_leases == 0 and running_workers == 0 and not engine.worker_plane.state.dead_letters,
        "saturated_dispatches": len(saturated_tenants) >= 9000,
        "rolling_weighted_fairness": bool(window_scores) and min(window_scores) >= 0.995 and max(gaps.values(), default=0) <= 28,
        "bounded_rss": 0 < peak_rss <= RSS_LIMIT_KIB and rss_to_state_ratio <= RSS_TO_STATE_LIMIT,
        "valid_bounded_wal": 0 < peak_wal <= WAL_LIMIT_BYTES,
        "complete_latency_metrics": len(completion_rows) == total and all(value >= 0 for value in latencies),
    }
    report = {
        "schema": "OMEGA_ONE_H2F_SINGLE_STATE_V1",
        "verdict": "H2F_LOCAL_SHADOW_SINGLE_STATE_PASSED" if all(gates.values()) else "H2F_LOCAL_SHADOW_SINGLE_STATE_FAILED",
        "truth_boundary": {
            "single_continuously_growing_state": True,
            "globally_unique_mission_ids": True,
            "local_processes_only": True,
            "logical_concurrency": True,
            "provider_execution": False,
            "multi_host": False,
            "deployment": False,
            "cfbe_gold": False,
        },
        "workload": {"missions": total, "tasks": total, "backlog_target": BACKLOG_TARGET, "tenant_weights": {"tenant-a": 1, "tenant-b": 2, "tenant-c": 4}},
        "faults": {"expected": len(expected_faults), "witnessed": len(witnesses), "boundaries": list(BOUNDARIES), "processes": process_count},
        "metrics": {
            "wall_seconds": wall_seconds,
            "throughput_missions_per_second": total / wall_seconds,
            "cpu_seconds": cpu_seconds,
            "peak_rss_kib": peak_rss,
            "rss_limit_kib": RSS_LIMIT_KIB,
            "rss_to_state_ratio": rss_to_state_ratio,
            "rss_to_state_limit": RSS_TO_STATE_LIMIT,
            "peak_wal_bytes": peak_wal,
            "state_bytes": state_bytes,
            "completion_latency_p50_seconds": percentile(latencies, 0.50),
            "completion_latency_p95_seconds": percentile(latencies, 0.95),
            "completion_latency_p99_seconds": percentile(latencies, 0.99),
            "startup_recovery_p99_seconds": percentile(startup_rows, 0.99),
            "reconciled_recovery_latency_rows": len(missing_completion_keys),
            "saturated_dispatches": len(saturated_tenants),
            "minimum_rolling_jain": min(window_scores) if window_scores else 0.0,
            "maximum_saturated_dispatch_gap": gaps,
        },
        "exact_cardinality": exact_cardinality,
        "residual_state": {"active_leases": active_leases, "running_workers": running_workers, "dead_letters": len(engine.worker_plane.state.dead_letters), "pending_outbox": status["pending_outbox"], "pending_transitions": status["pending_transition_outbox"]},
        "gates": gates,
        "source_manifest": {"python": sys.version, "platform": platform.platform(), "source_sha256": source_hashes},
    }
    report["canonical_sha256"] = canonical_digest(report)
    return report


def controller_main(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    Path(args.witness_file).parent.mkdir(parents=True, exist_ok=True)
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    peak_rss = 0
    peak_wal = 0
    process_count = 0
    deadline = started + float(args.timeout_seconds)
    while True:
        process_count += 1
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--child",
            "--state-dir", str(state_dir),
            "--metrics-db", str(args.metrics_db),
            "--witness-file", str(args.witness_file),
            "--missions", str(args.missions),
            "--process-index", str(process_count),
        ]
        process = subprocess.Popen(command, cwd=PROJECT_ROOT, start_new_session=True)
        while process.poll() is None:
            peak_rss = max(peak_rss, rss_kib(process.pid))
            for wal_path in state_dir.rglob("*-wal"):
                try:
                    peak_wal = max(peak_wal, wal_path.stat().st_size)
                except FileNotFoundError:
                    continue
            if time.perf_counter() > deadline:
                os.killpg(process.pid, signal.SIGKILL)
                raise TimeoutError("H2F_GLOBAL_TIMEOUT")
            time.sleep(0.005)
        if process.returncode == 0:
            break
        if process.returncode != -signal.SIGKILL:
            raise RuntimeError(f"H2F_CHILD_FAILED:{process.returncode}")
        if process_count > len(BOUNDARIES) * len(FAULT_ORDINALS) + 2:
            raise RuntimeError("H2F_EXCESS_RESTARTS")

    wall = time.perf_counter() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    child_peak = int(after.ru_maxrss)
    if sys.platform == "darwin":
        child_peak //= 1024
    peak_rss = max(peak_rss, child_peak)
    cpu = (after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime)
    report = final_report(args, wall, peak_rss, peak_wal, cpu, process_count)
    output = Path(args.output)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verdict"].endswith("PASSED") else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--metrics-db", required=True)
    parser.add_argument("--witness-file", required=True)
    parser.add_argument("--missions", type=int, default=10_000)
    parser.add_argument("--process-index", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument("--output", default="OMEGA_ONE_H2F_SINGLE_STATE_10000.json")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    raise SystemExit(child_main(arguments) if arguments.child else controller_main(arguments))
