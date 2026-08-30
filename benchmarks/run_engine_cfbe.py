#!/usr/bin/env python3
"""Measured CFBE benchmark for the real Omega completion-engine control path.

The worker body is a deterministic local latency stub.  Engine scheduling,
leasing, proof commits, persistence, DAG release, fencing, cancellation and
recovery are exercised through the real ``OmegaCompletionEngine`` APIs.  No
provider, network, credential, GPU, or external side effect is used.
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import statistics
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from omega_one.cfbe import (  # noqa: E402
    CFBEEvaluator,
    DeterministicFaultSimulator,
    FailureInjection,
    FaultKind,
    ReleaseEvidence,
    SimulationTask,
    SimulatorPolicy,
)
from omega_one.interop import EffectClass  # noqa: E402
from omega_one.source_proof import verify_sources  # noqa: E402
from omega_one.transaction_store import SQLiteStateStore  # noqa: E402
from omega_one.work_engine import (  # noqa: E402
    MissionEnvelope,
    OmegaCompletionEngine,
    ProofBundle,
    TaskEnvelope,
    TaskState,
    WorkerDescriptor,
    output_digest,
)


REPORT_SCHEMA = "urn:omega-one:cfbe-actual-engine-benchmark:v2"
CAPABILITY = "reason"
WORKER_ID = "bench-worker"
VERIFIER_ID = "bench-independent-verifier"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def percentile(samples: Sequence[float], fraction: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def summarized(samples: Sequence[float]) -> dict[str, float | int]:
    if not samples:
        return {"count": 0, "min": 0.0, "median": 0.0, "mean": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "count": len(samples),
        "min": min(samples),
        "median": statistics.median(samples),
        "mean": statistics.fmean(samples),
        "p95": percentile(samples, 0.95),
        "max": max(samples),
    }


def directory_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def make_worker(parallelism: int) -> WorkerDescriptor:
    return WorkerDescriptor(
        worker_id=WORKER_ID,
        capabilities=(CAPABILITY,),
        authority_grants=("A0", "A1", "A2"),
        privacy_ceiling="P2",
        data_zones=("internal",),
        capacity=parallelism,
        predicted_latency_ms=5.0,
    )


def make_proof(output: Any) -> ProofBundle:
    return ProofBundle(
        verifier_id=VERIFIER_ID,
        output_digest=output_digest(output),
        schema_valid=True,
        semantic_valid=True,
        policy_valid=True,
        readback_valid=True,
        evidence_refs=("urn:omega-one:benchmark:deterministic-readback",),
    )


def task_id_from_key(task_key: str) -> str:
    return task_key.rsplit(":", 1)[-1]


def execute_stub(task_id: str, delay_seconds: float) -> dict[str, Any]:
    time.sleep(delay_seconds)
    return {"task_id": task_id, "fruit": f"verified-{task_id}"}


def task_set(
    mission_id: str,
    task_ids: Sequence[str],
    dependency_map: dict[str, tuple[str, ...]] | None = None,
    *,
    tenant: Callable[[str], str] | None = None,
    weight: Callable[[str], int] | None = None,
) -> tuple[TaskEnvelope, ...]:
    dependencies = dependency_map or {}
    return tuple(
        TaskEnvelope(
            task_id=item,
            mission_id=mission_id,
            dependencies=dependencies.get(item, ()),
            capability=CAPABILITY,
            input_digest=sha256({"mission": mission_id, "task": item}),
            tenant_id=tenant(item) if tenant else "benchmark",
            flow_weight=weight(item) if weight else 1,
            authority="A0",
            privacy="P1",
        )
        for item in task_ids
    )


def run_workload(
    *,
    label: str,
    tasks: tuple[TaskEnvelope, ...],
    delays: dict[str, float],
    parallelism: int,
) -> dict[str, Any]:
    mission_id = tasks[0].mission_id
    mission = MissionEnvelope(
        mission_id=mission_id,
        version=1,
        objective=f"Prove benchmark workload {label}",
        success_definition=("all task fruit independently proven",),
    )
    workload_contract = {
        "label": label,
        "task_count": len(tasks),
        "tasks": [
            {
                "task_id": item.task_id,
                "dependencies": list(item.dependencies),
                "delay_seconds": delays[item.task_id],
                "tenant_id": item.tenant_id,
                "flow_weight": item.flow_weight,
            }
            for item in tasks
        ],
        "proof_threshold": "schema+semantic+policy+readback+evidence_ref",
    }
    with tempfile.TemporaryDirectory(prefix="omega-cfbe-run-") as directory:
        state_root = Path(directory) / "state"
        engine = OmegaCompletionEngine(state_root)
        engine.register_worker(make_worker(parallelism))
        schedule_ms: list[float] = []
        commit_ms: list[float] = []
        completed = 0
        cpu_start = time.process_time()
        wall_start = time.perf_counter()
        engine.submit_mission(mission, tasks)
        with ThreadPoolExecutor(max_workers=parallelism, thread_name_prefix="omega-cfbe") as pool:
            active: dict[Any, Any] = {}
            while completed < len(tasks):
                while len(active) < parallelism:
                    start = time.perf_counter()
                    leases = engine.schedule_wave(max_concurrency=parallelism - len(active))
                    elapsed_ms = (time.perf_counter() - start) * 1000.0
                    if not leases:
                        schedule_ms.append(elapsed_ms)
                        break
                    schedule_ms.extend([elapsed_ms / len(leases)] * len(leases))
                    for lease in leases:
                        item = task_id_from_key(lease.task_key)
                        future = pool.submit(execute_stub, item, delays[item])
                        active[future] = lease
                if not active:
                    raise RuntimeError(f"BENCHMARK_STALLED:{label}:{completed}/{len(tasks)}")
                done, _ = wait(tuple(active), return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda item: active[item].task_key):
                    lease = active.pop(future)
                    output = future.result()
                    start = time.perf_counter()
                    engine.submit_candidate(lease, output, make_proof(output))
                    commit_ms.append((time.perf_counter() - start) * 1000.0)
                    completed += 1
        wall_seconds = time.perf_counter() - wall_start
        cpu_seconds = time.process_time() - cpu_start
        status = engine.mission_status(mission_id)
        integrity = engine.verify_integrity()
        restarted = OmegaCompletionEngine(state_root)
        restart_valid = restarted.verify_integrity() and restarted.mission_status(mission_id)["state"] == "PROVEN"
        verified = sum(value == TaskState.PROVEN.value for value in status["tasks"].values())
        persistence = engine.persistence_status()
        return {
            "label": label,
            "parallelism": parallelism,
            "task_count": len(tasks),
            "workload_sha256": sha256(workload_contract),
            "wall_seconds": wall_seconds,
            "cpu_seconds": cpu_seconds,
            "verified_tasks": verified,
            "verified_output_ratio": verified / len(tasks),
            "verified_throughput_tasks_per_second": verified / wall_seconds,
            "schedule_latency_ms": summarized(schedule_ms),
            "proof_commit_latency_ms": summarized(commit_ms),
            "integrity_valid": integrity,
            "restart_readback_valid": restart_valid,
            "event_count": len(engine.state["events"]),
            "control_state_bytes": engine.control_file.stat().st_size,
            "total_state_bytes": directory_bytes(state_root),
            "persistence": {
                "backend": persistence["backend"],
                "schema_version": persistence["schema_version"],
                "journal_mode": persistence["journal_mode"],
                "revision": persistence["revision"],
                "pending_outbox": persistence["pending_outbox"],
                "integrity_valid": persistence["integrity_valid"],
            },
            "worker_stub_seconds": sum(delays.values()),
            "external_provider_calls": 0,
            "external_effects": 0,
        }


def aggregate_repetitions(label: str, parallelism: int, runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    throughput = [float(item["verified_throughput_tasks_per_second"]) for item in runs]
    wall = [float(item["wall_seconds"]) for item in runs]
    mean = statistics.fmean(throughput)
    return {
        "label": label,
        "parallelism": parallelism,
        "repetitions": len(runs),
        "task_count": runs[0]["task_count"],
        "workload_sha256": runs[0]["workload_sha256"],
        "wall_seconds": summarized(wall),
        "throughput_tasks_per_second": summarized(throughput),
        "throughput_cv": statistics.pstdev(throughput) / mean if mean else 0.0,
        "schedule_p95_ms_median": statistics.median(item["schedule_latency_ms"]["p95"] for item in runs),
        "commit_p95_ms_median": statistics.median(item["proof_commit_latency_ms"]["p95"] for item in runs),
        "verified_output_ratio_min": min(float(item["verified_output_ratio"]) for item in runs),
        "integrity_all": all(bool(item["integrity_valid"]) for item in runs),
        "restart_readback_all": all(bool(item["restart_readback_valid"]) for item in runs),
        "state_bytes_median": statistics.median(int(item["total_state_bytes"]) for item in runs),
        "raw_runs": list(runs),
    }


def paired_result(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if baseline["workload_sha256"] != candidate["workload_sha256"]:
        raise ValueError("NON_COMPARABLE_WORKLOADS")
    base_rate = float(baseline["throughput_tasks_per_second"]["median"])
    candidate_rate = float(candidate["throughput_tasks_per_second"]["median"])
    factor = candidate_rate / base_rate
    return {
        "label": baseline["label"],
        "task_count": baseline["task_count"],
        "workload_sha256": baseline["workload_sha256"],
        "baseline_parallelism": baseline["parallelism"],
        "candidate_parallelism": candidate["parallelism"],
        "baseline_median_throughput": base_rate,
        "candidate_median_throughput": candidate_rate,
        "measured_speedup": factor,
        "parallel_efficiency": factor / float(candidate["parallelism"]),
        "verified_output_ratio_delta": (
            float(candidate["verified_output_ratio_min"]) - float(baseline["verified_output_ratio_min"])
        ),
        "quality_preserved": (
            candidate["verified_output_ratio_min"] >= baseline["verified_output_ratio_min"]
            and candidate["integrity_all"]
            and candidate["restart_readback_all"]
        ),
    }


def independent_workload(load: int, run_number: int, parallelism: int) -> dict[str, Any]:
    mission_id = f"LOAD-{load}-R{run_number}-P{parallelism}"
    ids = tuple(f"task-{index:04d}" for index in range(load))
    delays = {item: (0.003, 0.006, 0.009, 0.012, 0.015)[index % 5] for index, item in enumerate(ids)}
    return run_workload(
        label=f"independent-{load}",
        tasks=task_set(mission_id, ids),
        delays=delays,
        parallelism=parallelism,
    )


def structured_workload(kind: str, run_number: int, parallelism: int) -> dict[str, Any]:
    mission_id = f"{kind.upper()}-R{run_number}-P{parallelism}"
    if kind == "heavy-tail":
        ids = tuple(f"task-{index:03d}" for index in range(60))
        pattern = (0.001, 0.002, 0.004, 0.008, 0.016, 0.032)
        dependencies: dict[str, tuple[str, ...]] = {}
        delays = {item: pattern[index % len(pattern)] for index, item in enumerate(ids)}
    elif kind == "wide-dag":
        parents = tuple(f"parent-{index:02d}" for index in range(30))
        ids = parents + ("join",)
        dependencies = {"join": parents}
        delays = {item: 0.006 for item in ids}
    elif kind == "deep-dag":
        ids = tuple(f"step-{index:02d}" for index in range(20))
        dependencies = {ids[index]: (ids[index - 1],) for index in range(1, len(ids))}
        delays = {item: 0.006 for item in ids}
    elif kind == "long-latency-stub":
        ids = tuple(f"media-{index:02d}" for index in range(18))
        pattern = (0.080, 0.100, 0.120)
        dependencies = {}
        delays = {item: pattern[index % len(pattern)] for index, item in enumerate(ids)}
    else:
        raise ValueError(f"UNKNOWN_WORKLOAD:{kind}")
    return run_workload(
        label=kind,
        tasks=task_set(mission_id, ids, dependencies),
        delays=delays,
        parallelism=parallelism,
    )


def jain_index(values: Iterable[float]) -> float:
    items = tuple(float(value) for value in values)
    denominator = len(items) * sum(value * value for value in items)
    return (sum(items) ** 2) / denominator if denominator else 0.0


def fairness_benchmark() -> dict[str, Any]:
    weights = {"alpha": 1, "beta": 2, "gamma": 4}
    task_ids = tuple(f"{tenant}-{index:02d}" for tenant in weights for index in range(24))
    mission_id = "FAIRNESS"
    tasks = task_set(
        mission_id,
        task_ids,
        tenant=lambda item: item.split("-", 1)[0],
        weight=lambda item: weights[item.split("-", 1)[0]],
    )
    counts = {tenant: 0 for tenant in weights}
    sequence: list[str] = []
    prefix_observations: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="omega-cfbe-fairness-") as directory:
        engine = OmegaCompletionEngine(Path(directory) / "state")
        engine.register_worker(make_worker(1))
        engine.submit_mission(
            MissionEnvelope(mission_id, 1, "Measure weighted fairness", ("42 dispatches observed",)),
            tasks,
        )
        for dispatch_index in range(42):
            lease = engine.schedule_next()
            if lease is None:
                raise RuntimeError("FAIRNESS_SCHEDULER_STALLED")
            tenant = engine.state["tasks"][lease.task_key]["spec"]["tenant_id"]
            counts[tenant] += 1
            sequence.append(tenant)
            output = {"dispatch": dispatch_index, "tenant": tenant}
            engine.submit_candidate(lease, output, make_proof(output))
            if (dispatch_index + 1) % 7 == 0:
                normalized = {name: counts[name] / value for name, value in weights.items()}
                prefix_observations.append(
                    {
                        "dispatches": dispatch_index + 1,
                        "counts": dict(counts),
                        "normalized_service": normalized,
                        "jain_index": jain_index(normalized.values()),
                    }
                )
        engine.cancel_mission(mission_id)
        normalized = {name: counts[name] / value for name, value in weights.items()}
        return {
            "dispatches_observed": len(sequence),
            "weights": weights,
            "dispatch_counts": counts,
            "target_counts_for_42": {"alpha": 6, "beta": 12, "gamma": 24},
            "normalized_service": normalized,
            "jain_index": jain_index(normalized.values()),
            "maximum_normalized_service_spread": max(normalized.values()) - min(normalized.values()),
            "prefix_observations": prefix_observations,
            "integrity_valid": engine.verify_integrity(),
            "external_effects": 0,
        }


def persistence_write_amplification_benchmark() -> dict[str, Any]:
    """Compare incremental payloads with a conservative whole-state rewrite lower bound."""
    mission_id = "PERSISTENCE-WRITE-AMPLIFICATION"
    ids = tuple(f"task-{index:03d}" for index in range(60))
    with tempfile.TemporaryDirectory(prefix="omega-cfbe-persistence-") as directory:
        engine = OmegaCompletionEngine(Path(directory) / "state")
        full_snapshot_bytes = 0
        incremental_changed_bytes = 0
        incremental_rows_touched = 0
        observations = 0

        def observe_commit() -> None:
            nonlocal full_snapshot_bytes, incremental_changed_bytes, incremental_rows_touched, observations
            receipt = engine.store.last_commit
            if receipt is None:
                raise RuntimeError("PERSISTENCE_COMMIT_RECEIPT_MISSING")
            full_snapshot_bytes += len(canonical_json(engine.state).encode("utf-8"))
            incremental_changed_bytes += receipt.logical_changed_bytes
            incremental_rows_touched += receipt.rows_upserted + receipt.rows_deleted + receipt.events_appended
            observations += 1

        engine.register_worker(make_worker(1))
        observe_commit()
        tasks = task_set(mission_id, ids)
        engine.submit_mission(
            MissionEnvelope(mission_id, 1, "Measure incremental persistence", ("all tasks proven",)),
            tasks,
        )
        observe_commit()
        for index in range(len(tasks)):
            lease = engine.schedule_next()
            if lease is None:
                raise RuntimeError(f"PERSISTENCE_BENCHMARK_STALLED:{index}")
            observe_commit()
            output = {"task": task_id_from_key(lease.task_key), "sequence": index}
            engine.submit_candidate(lease, output, make_proof(output))
            observe_commit()
        status = engine.persistence_status()
        reduction_factor = full_snapshot_bytes / incremental_changed_bytes
        return {
            "workload": "60 independent tasks; register, admission, lease and proof commits",
            "commit_observations": observations,
            "whole_state_logical_bytes_lower_bound": full_snapshot_bytes,
            "incremental_changed_payload_bytes": incremental_changed_bytes,
            "logical_write_reduction_factor": reduction_factor,
            "logical_write_reduction_percent": (1.0 - incremental_changed_bytes / full_snapshot_bytes) * 100.0,
            "incremental_rows_touched": incremental_rows_touched,
            "backend": status["backend"],
            "journal_mode": status["journal_mode"],
            "revision": status["revision"],
            "pending_outbox": status["pending_outbox"],
            "integrity_valid": engine.verify_integrity(),
            "mission_state": engine.mission_status(mission_id)["state"],
            "external_effects": 0,
            "measurement_boundary": "logical serialized payload; not physical filesystem write bytes or an elapsed-time speed claim",
        }


def observed_check(name: str, safety_critical: bool, function: Callable[[], tuple[bool, Any]]) -> dict[str, Any]:
    try:
        passed, observation = function()
        return {"name": name, "passed": bool(passed), "safety_critical": safety_critical, "observation": observation}
    except Exception as error:  # benchmark must report failures rather than conceal them
        return {
            "name": name,
            "passed": False,
            "safety_critical": safety_critical,
            "observation": {"unexpected_exception": type(error).__name__, "message": str(error)},
        }


def invariant_benchmarks() -> list[dict[str, Any]]:
    def proof_rejection() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            engine = OmegaCompletionEngine(Path(directory) / "state")
            engine.register_worker(make_worker(1))
            mission_id = "BAD-PROOF"
            task = task_set(mission_id, ("A",))[0]
            engine.submit_mission(MissionEnvelope(mission_id, 1, "Reject bad proof", ("bad proof rejected",)), (task,))
            lease = engine.schedule_next()
            output = {"fruit": "unproven"}
            bad = replace(make_proof(output), semantic_valid=False)
            error = None
            try:
                engine.submit_candidate(lease, output, bad)
            except ValueError as caught:
                error = str(caught)
            state = engine.mission_status(mission_id)["tasks"][lease.task_key]
            return error == "INDEPENDENT_PROOF_FAILED" and state == TaskState.RUNNING.value, {"error": error, "state": state}

    def self_verification() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            engine = OmegaCompletionEngine(Path(directory) / "state")
            engine.register_worker(make_worker(1))
            mission_id = "SELF-PROOF"
            task = task_set(mission_id, ("A",))[0]
            engine.submit_mission(MissionEnvelope(mission_id, 1, "Reject self proof", ("self proof rejected",)), (task,))
            lease = engine.schedule_next()
            output = {"fruit": "self-attested"}
            error = None
            try:
                engine.submit_candidate(lease, output, replace(make_proof(output), verifier_id=WORKER_ID))
            except ValueError as caught:
                error = str(caught)
            return error == "SELF_VERIFICATION_PROHIBITED", {"error": error}

    def cancellation() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            engine = OmegaCompletionEngine(Path(directory) / "state")
            engine.register_worker(make_worker(1))
            mission_id = "CANCEL"
            task = task_set(mission_id, ("A",))[0]
            engine.submit_mission(MissionEnvelope(mission_id, 1, "Cancel", ("cancelled",)), (task,))
            lease = engine.schedule_next()
            engine.cancel_mission(mission_id)
            error = None
            output = {"fruit": "late"}
            try:
                engine.submit_candidate(lease, output, make_proof(output))
            except ValueError as caught:
                error = str(caught)
            running = engine.state["workers"][WORKER_ID]["running"]
            return bool(error and "STALE" in error) and running == 0, {"error": error, "worker_running": running}

    def supersession() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            engine = OmegaCompletionEngine(Path(directory) / "state")
            engine.register_worker(make_worker(1))
            mission_id = "SUPERSEDE"
            first = task_set(mission_id, ("A",))[0]
            engine.submit_mission(MissionEnvelope(mission_id, 1, "V1", ("v1",)), (first,))
            lease = engine.schedule_next()
            second = task_set(mission_id, ("A",))[0]
            engine.submit_mission(MissionEnvelope(mission_id, 2, "V2", ("v2",)), (second,))
            error = None
            output = {"fruit": "stale-v1"}
            try:
                engine.submit_candidate(lease, output, make_proof(output))
            except ValueError as caught:
                error = str(caught)
            return bool(error and "STALE" in error), {"error": error}

    def retry_bound() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            engine = OmegaCompletionEngine(Path(directory) / "state")
            engine.register_worker(make_worker(1))
            mission_id = "RETRY"
            task = replace(task_set(mission_id, ("A",))[0], max_attempts=2)
            engine.submit_mission(MissionEnvelope(mission_id, 1, "Retry", ("bounded retry",)), (task,))
            first = engine.schedule_next()
            state_one = engine.fail_task(first, "TRANSIENT", "first")
            second = engine.schedule_next()
            state_two = engine.fail_task(second, "TRANSIENT", "second")
            return state_one == TaskState.RETRY_WAIT.value and state_two == TaskState.DEAD_LETTER.value, {
                "first": state_one,
                "second": state_two,
            }

    def authority_and_privacy() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            engine = OmegaCompletionEngine(Path(directory) / "state")
            engine.register_worker(
                WorkerDescriptor(
                    worker_id=WORKER_ID,
                    capabilities=(CAPABILITY,),
                    authority_grants=("A0",),
                    privacy_ceiling="P1",
                    capacity=2,
                )
            )
            mission_id = "POLICY"
            tasks = (
                replace(task_set(mission_id, ("AUTH",))[0], authority="A2"),
                replace(task_set(mission_id, ("PRIVATE",))[0], privacy="P2"),
            )
            engine.submit_mission(MissionEnvelope(mission_id, 1, "Policy", ("mismatch not routed",)), tasks)
            lease = engine.schedule_next()
            return lease is None, {"lease": None if lease is None else lease.task_key}

    def restart_recovery() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            engine = OmegaCompletionEngine(state)
            engine.register_worker(make_worker(1))
            mission_id = "RESTART"
            task = task_set(mission_id, ("A",))[0]
            engine.submit_mission(MissionEnvelope(mission_id, 1, "Restart", ("fruit durable",)), (task,))
            lease = engine.schedule_next()
            output = {"fruit": "durable"}
            engine.submit_candidate(lease, output, make_proof(output))
            restarted = OmegaCompletionEngine(state)
            status = restarted.mission_status(mission_id)
            valid = restarted.verify_integrity()
            return status["state"] == "PROVEN" and valid, {"state": status["state"], "integrity": valid}

    def tamper_detection() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            engine = OmegaCompletionEngine(Path(directory) / "state")
            engine.register_worker(make_worker(1))
            before = engine.verify_integrity()
            engine.state["events"][0]["body"]["worker_id"] = "tampered"
            after = engine.verify_integrity()
            return before and not after, {"before": before, "after_tamper": after}

    def graph_validation() -> tuple[bool, Any]:
        errors: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            engine = OmegaCompletionEngine(Path(directory) / "state")
            mission_id = "GRAPH"
            cyclic = task_set(mission_id, ("A", "B"), {"A": ("B",), "B": ("A",)})
            try:
                engine.submit_mission(MissionEnvelope(mission_id, 1, "Graph", ("valid DAG",)), cyclic)
            except ValueError as error:
                errors.append(str(error))
        return errors == ["CYCLIC_DAG"], {"errors": errors}

    def effect_idempotency() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            engine = OmegaCompletionEngine(Path(directory) / "state")
            engine.register_worker(make_worker(1))
            mission_id = "IDEMPOTENT"
            task = replace(
                task_set(mission_id, ("A",))[0],
                authority="A2",
                effect_class=EffectClass.WRITE,
                idempotency_key="idem-A",
            )
            engine.submit_mission(MissionEnvelope(mission_id, 1, "Idempotent", ("one logical effect",)), (task,))
            lease = engine.schedule_next()
            payload = {"operation": "local-simulation"}
            permit = engine.issue_effect_permit(lease, output_digest(payload), owner_authorized=True)
            first = engine.record_simulated_effect(lease, permit["permit_id"], payload)
            second = engine.record_simulated_effect(lease, permit["permit_id"], payload)
            return first == second and not first["external_effect"], {
                "same_receipt": first == second,
                "external_effect": first["external_effect"],
            }

    def conflicting_idempotency_cleanup() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            engine = OmegaCompletionEngine(Path(directory) / "state")
            engine.register_worker(make_worker(1))
            mission_id = "IDEM-CONFLICT"
            base = task_set(mission_id, ("A", "B"))
            tasks = tuple(
                replace(item, authority="A2", effect_class=EffectClass.WRITE, idempotency_key="shared-key")
                for item in base
            )
            error = None
            try:
                engine.submit_mission(MissionEnvelope(mission_id, 1, "Conflict", ("conflict contained",)), tasks)
            except ValueError as caught:
                error = str(caught)
            admitted_tasks = sorted(engine.state["tasks"])
            admitted_jobs = sorted(engine.worker_plane.state.jobs)
            passed = (
                error == "DUPLICATE_IDEMPOTENCY_KEY"
                and not admitted_tasks
                and not admitted_jobs
                and not engine.worker_plane.state.idempotency
                and mission_id not in engine.state["missions"]
                and engine.verify_integrity()
            )
            return passed, {
                "error": error,
                "engine_task_count": len(admitted_tasks),
                "worker_job_count": len(admitted_jobs),
                "idempotency_index": dict(engine.worker_plane.state.idempotency),
                "mission_admitted": mission_id in engine.state["missions"],
                "integrity_valid": engine.verify_integrity(),
                "external_effects": 0,
            }

    def transactional_backend() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            engine = OmegaCompletionEngine(Path(directory) / "state")
            engine.register_worker(make_worker(1))
            status = engine.persistence_status()
            passed = (
                status["backend"] == "SQLITE_WAL_INCREMENTAL"
                and status["journal_mode"] == "WAL"
                and status["schema_version"] == 2
                and status["pending_outbox"] == 0
                and status["integrity_valid"]
                and not status["legacy_snapshot_present"]
            )
            return passed, status

    def legacy_migration() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            state.mkdir(parents=True)
            legacy = OmegaCompletionEngine._blank()
            row = {"type": "LEGACY", "body": {"count": 3}, "at": "2026-08-30T00:00:00Z", "previous": "GENESIS"}
            row["hash"] = output_digest(row)
            legacy["events"].append(row)
            legacy["dispatch_counts"]["alpha"] = 3
            source = state / "control-state.json"
            source.write_text(json.dumps(legacy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            engine = OmegaCompletionEngine(state)
            after = hashlib.sha256(source.read_bytes()).hexdigest()
            status = engine.persistence_status()
            passed = (
                before == after
                and engine.state["dispatch_counts"] == {"alpha": 3}
                and len(status["migrations"]) == 1
                and engine.verify_integrity()
            )
            return passed, {
                "source_hash_before": before,
                "source_hash_after": after,
                "migrations": len(status["migrations"]),
                "dispatch_counts": engine.state["dispatch_counts"],
                "integrity_valid": engine.verify_integrity(),
            }

    def crash_recovery_outbox() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"

            def crash(point: str) -> None:
                if point == "after_admission_commit":
                    raise RuntimeError("INJECTED_PROCESS_CRASH")

            engine = OmegaCompletionEngine(state, fault_injector=crash)
            engine.register_worker(make_worker(1))
            mission_id = "CRASH-RECOVERY"
            error = None
            try:
                engine.submit_mission(
                    MissionEnvelope(mission_id, 1, "Recover committed admission", ("job materialized",)),
                    task_set(mission_id, ("A",)),
                )
            except RuntimeError as caught:
                error = str(caught)
            pending_before = engine.persistence_status()["pending_outbox"]
            jobs_before = len(engine.worker_plane.state.jobs)
            recovered = OmegaCompletionEngine(state)
            pending_after = recovered.persistence_status()["pending_outbox"]
            jobs_after = len(recovered.worker_plane.state.jobs)
            passed = (
                error == "INJECTED_PROCESS_CRASH"
                and pending_before == 1
                and jobs_before == 0
                and pending_after == 0
                and jobs_after == 1
                and recovered.verify_integrity()
            )
            return passed, {
                "error": error,
                "pending_before_restart": pending_before,
                "jobs_before_restart": jobs_before,
                "pending_after_restart": pending_after,
                "jobs_after_restart": jobs_after,
                "integrity_valid": recovered.verify_integrity(),
            }

    def cross_instance_contention() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            first = OmegaCompletionEngine(state)
            first.register_worker(make_worker(1))
            second = OmegaCompletionEngine(state)
            barrier = threading.Barrier(2)
            outcomes: list[str] = []
            outcomes_lock = threading.Lock()

            def submit(engine: OmegaCompletionEngine, mission_id: str, task_id: str) -> None:
                candidate = replace(
                    task_set(mission_id, (task_id,))[0],
                    authority="A2",
                    effect_class=EffectClass.WRITE,
                    idempotency_key="shared-contention-key",
                )
                barrier.wait()
                try:
                    engine.submit_mission(
                        MissionEnvelope(mission_id, 1, "Contend", ("one admission",)),
                        (candidate,),
                    )
                    outcome = "ADMITTED"
                except ValueError as caught:
                    outcome = str(caught)
                with outcomes_lock:
                    outcomes.append(outcome)

            threads = [
                threading.Thread(target=submit, args=(first, "CONTEND-A", "A")),
                threading.Thread(target=submit, args=(second, "CONTEND-B", "B")),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            readback = OmegaCompletionEngine(state)
            passed = (
                outcomes.count("ADMITTED") == 1
                and outcomes.count("IDEMPOTENCY_KEY_CONFLICT") == 1
                and len(readback.state["tasks"]) == 1
                and len(readback.worker_plane.state.jobs) == 1
                and readback.persistence_status()["pending_outbox"] == 0
                and readback.verify_integrity()
            )
            return passed, {
                "outcomes": sorted(outcomes),
                "mission_count": len(readback.state["missions"]),
                "task_count": len(readback.state["tasks"]),
                "worker_job_count": len(readback.worker_plane.state.jobs),
                "pending_outbox": readback.persistence_status()["pending_outbox"],
                "integrity_valid": readback.verify_integrity(),
            }

    def online_backup() -> tuple[bool, Any]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = OmegaCompletionEngine(root / "state")
            engine.register_worker(make_worker(1))
            receipt = engine.backup_state(root / "backup.sqlite3")
            restored = SQLiteStateStore(receipt["path"])
            restored_state, revision = restored.load(OmegaCompletionEngine._blank())
            passed = (
                receipt["integrity_valid"]
                and restored.verify_integrity()
                and revision == engine.persistence_status()["revision"]
                and sha256(restored_state["workers"]) == sha256(engine.state["workers"])
            )
            return passed, {
                "backup_bytes": receipt["bytes"],
                "revision": revision,
                "integrity_valid": restored.verify_integrity(),
                "worker_rows": len(restored_state["workers"]),
            }

    checks = (
        ("independent-proof-rejection", True, proof_rejection),
        ("self-verification-rejection", True, self_verification),
        ("post-cancellation-result-rejection", True, cancellation),
        ("stale-version-result-rejection", True, supersession),
        ("bounded-retry-dead-letter", False, retry_bound),
        ("authority-and-privacy-hard-match", True, authority_and_privacy),
        ("durable-restart-readback", True, restart_recovery),
        ("hash-chain-tamper-detection", True, tamper_detection),
        ("cyclic-graph-rejection", True, graph_validation),
        ("effect-idempotent-replay", True, effect_idempotency),
        ("duplicate-idempotency-admission-atomic", True, conflicting_idempotency_cleanup),
        ("sqlite-wal-incremental-backend", True, transactional_backend),
        ("legacy-json-migration-source-preserving", True, legacy_migration),
        ("committed-admission-crash-recovery", True, crash_recovery_outbox),
        ("cross-instance-idempotency-contention", True, cross_instance_contention),
        ("online-backup-semantic-restore", True, online_backup),
    )
    return [observed_check(name, critical, function) for name, critical, function in checks]


def deterministic_simulator_lane() -> dict[str, Any]:
    fault_names = ("duplicate", "fence", "cancel", "supersede", "outage", "injection", "deception")
    tasks = tuple(
        SimulationTask(
            task_id=name,
            mission_id=f"sim-{name}",
            fruit_points=1.0,
            latency_seconds=1.0,
            cost=0.1,
            deadline_seconds=60.0,
            tenant_id="tenant-a" if index % 2 == 0 else "tenant-b",
            effect_key="effect-duplicate" if name == "duplicate" else None,
        )
        for index, name in enumerate(fault_names)
    )
    injections = (
        FailureInjection("duplicate", FaultKind.DUPLICATE_DELIVERY),
        FailureInjection("fence", FaultKind.STALE_FENCE),
        FailureInjection("cancel", FaultKind.CANCELLATION),
        FailureInjection("supersede", FaultKind.SUPERSESSION),
        FailureInjection("outage", FaultKind.PROVIDER_OUTAGE),
        FailureInjection("injection", FaultKind.PROMPT_INJECTION),
        FailureInjection("deception", FaultKind.DECEPTIVE_WORKER),
    )
    baseline = DeterministicFaultSimulator.run(
        "cfbe-simulator-serial", tasks, injections, policy=SimulatorPolicy(parallelism=1)
    )
    candidate = DeterministicFaultSimulator.run(
        "cfbe-simulator-parallel-3", tasks, injections, policy=SimulatorPolicy(parallelism=3)
    )
    report = json.loads(
        CFBEEvaluator.evaluate(
            candidate,
            baseline=baseline,
            release_evidence=ReleaseEvidence(paired_suites=1, load_levels=1),
        ).to_json()
    )
    return {
        "scope": "DETERMINISTIC_LOCAL_SIMULATION_ONLY",
        "fault_cases": len(injections),
        "simulated_speedup": report["paired_measurement"]["throughput_speedup"],
        "score": report["total_score"],
        "hard_vetoes": report["hard_vetoes"],
        "release_decision": report["release_decision"],
        "report_sha256": report["report_sha256"],
    }


def main() -> int:
    repetitions = 3
    independent: list[dict[str, Any]] = []
    paired: list[dict[str, Any]] = []
    independent_repetitions = {25: repetitions, 70: repetitions, 120: repetitions, 240: 2}
    for load in (25, 70, 120, 240):
        by_parallelism: dict[int, dict[str, Any]] = {}
        for parallelism in (1, 3):
            runs = [
                independent_workload(load, repeat, parallelism)
                for repeat in range(1, independent_repetitions[load] + 1)
            ]
            aggregate = aggregate_repetitions(f"independent-{load}", parallelism, runs)
            independent.append(aggregate)
            by_parallelism[parallelism] = aggregate
        paired.append(paired_result(by_parallelism[1], by_parallelism[3]))

    structured: list[dict[str, Any]] = []
    for kind in ("heavy-tail", "wide-dag", "deep-dag", "long-latency-stub"):
        by_parallelism = {}
        for parallelism in (1, 3):
            runs = [structured_workload(kind, repeat, parallelism) for repeat in range(1, 3)]
            aggregate = aggregate_repetitions(kind, parallelism, runs)
            structured.append(aggregate)
            by_parallelism[parallelism] = aggregate
        paired.append(paired_result(by_parallelism[1], by_parallelism[3]))

    fairness = fairness_benchmark()
    persistence = persistence_write_amplification_benchmark()
    invariants = invariant_benchmarks()
    simulator = deterministic_simulator_lane()
    failed = [item for item in invariants if not item["passed"]]
    safety_failures = [item for item in failed if item["safety_critical"]]
    actual_speedups = [item["measured_speedup"] for item in paired]
    all_quality_preserved = all(item["quality_preserved"] for item in paired)
    release = "SHADOW_ONLY" if not safety_failures else "NO_GO"
    live_automation = "NO_GO"
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "empirical_scope": "ACTUAL_ENGINE_LOCAL_CONTROL_PATH_WITH_DETERMINISTIC_WORKER_STUB",
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpu_count": os.cpu_count(),
            "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "method": {
            "timer": "time.perf_counter",
            "throughput": "independently_proven_tasks / end_to_end_wall_seconds",
            "timed_boundary": "mission submission through final independent proof commit",
            "paired_parallelism": [1, 3],
            "independent_load_levels": [25, 70, 120, 240],
            "independent_repetitions_per_cell": {
                str(load): independent_repetitions[load] for load in sorted(independent_repetitions)
            },
            "structured_repetitions_per_cell": 2,
            "real_engine_methods_exercised": [
                "submit_mission", "schedule_next", "schedule_wave", "concurrency_plan", "submit_candidate", "fail_task",
                "cancel_mission", "issue_effect_permit", "record_simulated_effect",
                "mission_status", "verify_integrity",
                "persistence_status", "backup_state",
            ],
            "worker_execution": "deterministic time.sleep stub",
            "external_provider_calls": 0,
            "external_effects": 0,
        },
        "actual_engine": {
            "independent_runs": independent,
            "structured_runs": structured,
            "paired_results": paired,
            "speedup_summary": summarized(actual_speedups),
            "quality_preserved_all_pairs": all_quality_preserved,
            "fairness": fairness,
            "transactional_persistence": persistence,
            "invariants": {
                "total": len(invariants),
                "passed": len(invariants) - len(failed),
                "failed": len(failed),
                "safety_critical_failures": len(safety_failures),
                "checks": invariants,
            },
        },
        "deterministic_simulator": simulator,
        "release": {
            "actual_engine_cfbe_state": release,
            "live_automation_state": live_automation,
            "maximum_authorized_use": "LOCAL_SHADOW_TESTING_ONLY",
            "blocking_evidence_gaps": [
                "no live OpenAI, Gemini, or Copilot execution/readback benchmark",
                "no multi-host distributed datastore or leader-election test; SQLite WAL is same-host only",
                "no seven-day or 10,000-mission soak evidence",
                "no hidden-suite evidence",
                "no real image/video generation quality or export lineage benchmark",
            ] + [item["name"] for item in failed],
        },
        "capability_harvest_targets": [
            {
                "priority": 1,
                "target": "multi-host coordinator and lease store",
                "reason": "Extend the proven same-host SQLite revision fencing and idempotency contention controls to a distributed compare-and-swap store with leader election.",
            },
            {
                "priority": 2,
                "target": "wide-DAG persistence batching",
                "reason": "Batch independent READY-state transitions and WAL checkpoints without weakening proof commits or crash recovery.",
            },
            {
                "priority": 3,
                "target": "live provider adapters plus semantic readback",
                "reason": "Benchmark real OpenAI/Gemini/Copilot routes, provenance, retry, cost, privacy and provider-specific failure modes.",
            },
            {
                "priority": 4,
                "target": "transactional soak and forced-process-kill court",
                "reason": "Run 10,000 missions with forced termination during commit, outbox claim and proof completion, then verify bounded WAL growth and exact recovery.",
            },
            {
                "priority": 5,
                "target": "photo/video completion court",
                "reason": "Add asset lineage, visual-quality judges, temporal consistency, audio sync, regeneration and export verification.",
            },
        ],
    }
    report["report_sha256"] = sha256(report)
    encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if len(sys.argv) > 1:
        output_path = Path(sys.argv[1]).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(encoded, encoding="utf-8")
        print(
            json.dumps(
                {
                    "output_path": str(output_path),
                    "report_sha256": report["report_sha256"],
                    "actual_engine_cfbe_state": report["release"]["actual_engine_cfbe_state"],
                    "live_automation_state": report["release"]["live_automation_state"],
                    "invariants": report["actual_engine"]["invariants"],
                    "speedup_summary": report["actual_engine"]["speedup_summary"],
                },
                sort_keys=True,
            )
        )
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
