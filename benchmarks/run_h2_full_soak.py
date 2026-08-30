#!/usr/bin/env python3
"""Checkpointed 10,000-mission H2 segmented resilience court."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = PROJECT_ROOT / "benchmarks" / "run_h2_preflight_canary.py"
SCENARIO_COUNT = 5
EXPECTED_ENGINE_COMMIT = "bd29324411701371623277a32f9fce9ca5173365"
EXPECTED_ENGINE_BLOBS = {
    "omega_one/transaction_store.py": "d665f9e93523c8ae7c6da8b063e16d7cab4c8ca7",
    "omega_one/work_engine.py": "66e0db898f08dcff968f0430c66ee383e9acc2c3",
}
WAL_BOUND_BYTES = 16 * 1024 * 1024
RSS_BOUND_KIB = 256 * 1024
CANDIDATE_LATENCY_BOUND_SECONDS = 270.0


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    content = path.read_bytes()
    return hashlib.sha1(f"blob {len(content)}\0".encode("ascii") + content).hexdigest()


def percentile(values: Iterable[float], quantile: float) -> float:
    rows = sorted(float(value) for value in values)
    if not rows or not 0.0 <= quantile <= 1.0:
        raise ValueError("PERCENTILE_INPUT_INVALID")
    position = (len(rows) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return rows[lower]
    return rows[lower] + (rows[upper] - rows[lower]) * (position - lower)


def jain_index(values: Iterable[float]) -> float:
    rows = tuple(float(value) for value in values)
    denominator = len(rows) * sum(value * value for value in rows)
    return 0.0 if not rows or denominator == 0 else (sum(rows) ** 2) / denominator


def validate_segment_report(report: dict[str, Any], index: int) -> None:
    embedded = report.get("report_sha256")
    body = {key: value for key, value in report.items() if key != "report_sha256"}
    if embedded != canonical_digest(body):
        raise RuntimeError(f"SEGMENT_REPORT_HASH_INVALID:{index}")


def run_segment(
    index: int,
    missions_per_scenario: int,
    artifact_root: Path,
    timeout_seconds: int,
) -> tuple[dict[str, Any], Path]:
    path = artifact_root / "segments" / f"segment-{index:04d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [sys.executable, str(PREFLIGHT), "--missions", str(missions_per_scenario), "--output", str(path)],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        shell=False,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise RuntimeError(f"SEGMENT_TIMEOUT:{index}")
    finally:
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()
    if process.returncode != 0:
        raise RuntimeError(f"SEGMENT_FAILED:{index}:{stderr.decode('utf-8', errors='replace')[-1000:]}")
    if not path.exists():
        raise RuntimeError(f"SEGMENT_REPORT_MISSING:{index}:{stdout.decode('utf-8', errors='replace')[-500:]}")
    report = json.loads(path.read_text(encoding="utf-8"))
    validate_segment_report(report, index)
    return report, path


def segment_summary(report: dict[str, Any], path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "file_sha256": file_sha256(path),
        "report_sha256": report["report_sha256"],
        "workload_fingerprint": report["workload_fingerprint"],
        "candidate_missions": report["candidate"]["mission_count"],
        "baseline_missions": report["baseline"]["mission_count"],
        "candidate_elapsed_seconds": report["candidate"]["elapsed_seconds"],
        "baseline_elapsed_seconds": report["baseline"]["elapsed_seconds"],
        "candidate_process_kills": report["candidate"]["process_kills"],
        "baseline_process_kills": report["baseline"]["process_kills"],
        "candidate_jain_fairness": report["candidate"]["jain_fairness"],
        "candidate_max_peak_rss_kib": report["candidate"]["max_peak_rss_kib"],
        "candidate_max_wal_bytes": report["candidate"]["max_wal_bytes_at_crash"],
        "candidate_exact_event_cardinality": report["candidate"]["exact_event_cardinality"],
        "candidate_duplicate_proof_receipts": report["candidate"]["duplicate_proof_receipts"],
        "candidate_dispatch_counts": report["candidate"]["dispatch_counts"],
        "failed_gates": [key for key, passed in report["gates"].items() if not passed],
        "candidate_boundary_recovery_seconds": {
            row["scenario"]: row["elapsed_total_seconds"] - row["elapsed_to_kill_seconds"]
            for row in report["candidate"]["shards"]
        },
    }


def aggregate_segment_reports(
    reports: list[tuple[dict[str, Any], Path]],
    *,
    target_candidate_missions: int,
    engine_source_commit: str,
    wall_elapsed_seconds: float,
) -> dict[str, Any]:
    summaries = [segment_summary(report, path) for report, path in reports]
    if not summaries:
        raise ValueError("SEGMENT_REPORTS_REQUIRED")
    candidate_missions = sum(int(row["candidate_missions"]) for row in summaries)
    baseline_missions = sum(int(row["baseline_missions"]) for row in summaries)
    candidate_elapsed = sum(float(row["candidate_elapsed_seconds"]) for row in summaries)
    baseline_elapsed = sum(float(row["baseline_elapsed_seconds"]) for row in summaries)
    candidate_kills = sum(int(row["candidate_process_kills"]) for row in summaries)
    baseline_kills = sum(int(row["baseline_process_kills"]) for row in summaries)
    dispatch = Counter()
    for row in summaries:
        dispatch.update({key: int(value) for key, value in row["candidate_dispatch_counts"].items()})
    normalized = [dispatch["tenant-a"] / 1.0, dispatch["tenant-b"] / 2.0, dispatch["tenant-c"] / 4.0]
    recovery = [
        float(value)
        for row in summaries
        for value in row["candidate_boundary_recovery_seconds"].values()
    ]
    segment_latency = [float(row["candidate_elapsed_seconds"]) for row in summaries]
    source_blob_observed = {path: git_blob_sha(PROJECT_ROOT / path) for path in EXPECTED_ENGINE_BLOBS}
    candidate_rss = max(int(row["candidate_max_peak_rss_kib"]) for row in summaries)
    candidate_wal = max(int(row["candidate_max_wal_bytes"]) for row in summaries)
    paired_speedup = baseline_elapsed / candidate_elapsed if candidate_elapsed else 0.0
    gates = {
        "engine_source_commit_pinned": engine_source_commit == EXPECTED_ENGINE_COMMIT,
        "engine_critical_blobs_exact": source_blob_observed == EXPECTED_ENGINE_BLOBS,
        "exact_candidate_10000_mission_executions": candidate_missions == target_candidate_missions == 10_000,
        "exact_baseline_10000_mission_executions": baseline_missions == target_candidate_missions == 10_000,
        "all_segments_gate_clean": all(not row["failed_gates"] for row in summaries),
        "five_candidate_kills_per_segment": candidate_kills == len(summaries) * SCENARIO_COUNT,
        "five_baseline_kills_per_segment": baseline_kills == len(summaries) * SCENARIO_COUNT,
        "raw_task_events_exactly_once": all(bool(row["candidate_exact_event_cardinality"]) for row in summaries),
        "proof_receipts_exactly_once": sum(int(row["candidate_duplicate_proof_receipts"]) for row in summaries) == 0,
        "fairness": jain_index(normalized) >= 0.995,
        "rss_measurement_valid": candidate_rss > 0,
        "rss_bounded": candidate_rss <= RSS_BOUND_KIB,
        "wal_bounded": candidate_wal <= WAL_BOUND_BYTES,
        "actual_candidate_latency_bounded": candidate_elapsed <= CANDIDATE_LATENCY_BOUND_SECONDS,
        "paired_speedup_at_least_2x": paired_speedup >= 2.0,
    }
    passed = all(gates.values())
    report: dict[str, Any] = {
        "schema_version": "H2-SEGMENTED-1.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "classification": "LOCAL_SHADOW_CHECKPOINTED_FORCED_INTERRUPTION_COURT",
        "engine_source_commit": engine_source_commit,
        "engine_critical_blob_expected": EXPECTED_ENGINE_BLOBS,
        "engine_critical_blob_observed": source_blob_observed,
        "harness_sha256": file_sha256(PREFLIGHT),
        "orchestrator_sha256": file_sha256(Path(__file__).resolve()),
        "workload": {
            "target_candidate_mission_executions": target_candidate_missions,
            "candidate_mission_executions": candidate_missions,
            "baseline_mission_executions": baseline_missions,
            "segments": len(summaries),
            "mission_identity_scope": "the deterministic 100-mission identity set is replayed in each isolated segment; 10,000 executions are proven, not 10,000 globally unique mission IDs",
            "candidate_forced_process_kills": candidate_kills,
            "baseline_forced_process_kills": baseline_kills,
            "paired_identical_segment_fingerprints": len({row["workload_fingerprint"] for row in summaries}) == 1,
        },
        "measurement": {
            "candidate_elapsed_seconds": candidate_elapsed,
            "baseline_elapsed_seconds": baseline_elapsed,
            "wall_elapsed_seconds": wall_elapsed_seconds,
            "paired_speedup": paired_speedup,
            "candidate_throughput_missions_per_second": candidate_missions / candidate_elapsed,
            "segment_latency_seconds": {"p50": percentile(segment_latency, 0.50), "p95": percentile(segment_latency, 0.95), "p99": percentile(segment_latency, 0.99), "max": max(segment_latency)},
            "boundary_recovery_seconds": {"p50": percentile(recovery, 0.50), "p95": percentile(recovery, 0.95), "p99": percentile(recovery, 0.99), "max": max(recovery)},
            "candidate_max_peak_rss_kib": candidate_rss,
            "candidate_max_wal_bytes_at_crash": candidate_wal,
            "jain_fairness": jain_index(normalized),
            "dispatch_counts": dict(sorted(dispatch.items())),
        },
        "gates": gates,
        "segments": summaries,
        "verdict": {
            "state": "H2_LOCAL_SHADOW_SEGMENTED_COURT_PASSED" if passed else "H2_HELD",
            "passed": passed,
            "failed_gates": [key for key, value in gates.items() if not value],
            "full_single_state_soak_proven": False,
            "deployment": "NOT_AUTHORIZED",
            "provider_execution": False,
            "distributed_multi_host_proof": False,
            "cfbe_gold": False,
            "external_effects": 0,
        },
    }
    report["report_sha256"] = canonical_digest(report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-candidate-missions", type=int, default=10_000)
    parser.add_argument("--segment-candidate-missions", type=int, default=100)
    parser.add_argument("--segment-timeout-seconds", type=int, default=120)
    parser.add_argument("--engine-source-commit", default=EXPECTED_ENGINE_COMMIT)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.target_candidate_missions != 10_000:
        raise ValueError("FULL_H2_TARGET_MUST_BE_10000")
    if args.segment_candidate_missions < SCENARIO_COUNT or args.segment_candidate_missions % SCENARIO_COUNT:
        raise ValueError("SEGMENT_MISSIONS_MUST_BE_POSITIVE_MULTIPLE_OF_FIVE")
    if args.target_candidate_missions % args.segment_candidate_missions:
        raise ValueError("TARGET_MUST_BE_DIVISIBLE_BY_SEGMENT")
    if args.segment_timeout_seconds < 1:
        raise ValueError("SEGMENT_TIMEOUT_MUST_BE_POSITIVE")
    segment_count = args.target_candidate_missions // args.segment_candidate_missions
    missions_per_scenario = args.segment_candidate_missions // SCENARIO_COUNT
    started = time.perf_counter()
    reports = [
        run_segment(index, missions_per_scenario, args.artifact_root, args.segment_timeout_seconds)
        for index in range(segment_count)
    ]
    aggregate = aggregate_segment_reports(
        reports,
        target_candidate_missions=args.target_candidate_missions,
        engine_source_commit=args.engine_source_commit,
        wall_elapsed_seconds=time.perf_counter() - started,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({
        "output": str(args.output),
        "report_sha256": aggregate["report_sha256"],
        "verdict": aggregate["verdict"]["state"],
        "failed_gates": aggregate["verdict"]["failed_gates"],
        "candidate_mission_executions": aggregate["workload"]["candidate_mission_executions"],
        "baseline_mission_executions": aggregate["workload"]["baseline_mission_executions"],
        "candidate_process_kills": aggregate["workload"]["candidate_forced_process_kills"],
    }, indent=2, sort_keys=True))
    return 0 if aggregate["verdict"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
