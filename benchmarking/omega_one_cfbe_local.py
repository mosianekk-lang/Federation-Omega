#!/usr/bin/env python3
"""Reproducible local CFBE campaign for Omega-One replay finalization.

The baseline emits one receipt for every recovered attempt. The candidate reuses
trace-spine content hashes and collapses a verified replay batch into one canonical
receipt. Results are local observations only; they do not imply provider, deployment,
soak, owner-value, or company-wide superiority.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import statistics
import time
import tracemalloc
from typing import Callable

from omega_one.hyperperformance import (
    CampaignPolicy,
    ExactlyOnceFinalizer,
    MissionMeasurement,
    OutcomeState,
    PairedMissionObservation,
    canonical_sha256,
    evaluate_paired_campaign,
)


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _baseline(*, operations: int, attempts: int) -> int:
    receipts: list[dict[str, object]] = []
    for index in range(operations):
        payload = {"mission": index, "value": "x" * 32}
        result = {"ok": True, "mission": index}
        proof = {"proof": index}
        for _ in range(attempts):
            body = {
                "operation_id": f"op-{index}",
                "payload_sha256": _digest(payload),
                "result_sha256": _digest(result),
                "proof_sha256": _digest(proof),
                "outcome": "SUCCEEDED",
            }
            receipts.append({"receipt_id": _digest(body), **body})
    return len(receipts)


def _candidate(*, operations: int, attempts: int) -> int:
    finalizer = ExactlyOnceFinalizer()
    for index in range(operations):
        finalizer.finalize_hashed_replay_batch(
            f"op-{index}",
            payload_sha256=canonical_sha256(
                {"mission": index, "value": "x" * 32}
            ),
            result_sha256=canonical_sha256({"ok": True, "mission": index}),
            proof_sha256=canonical_sha256({"proof": index}),
            outcome=OutcomeState.SUCCEEDED,
            attempt_count=attempts,
        )
    return finalizer.committed_count


def _timed(function: Callable[[], int]) -> tuple[float, int]:
    gc.collect()
    started = time.perf_counter_ns()
    count = function()
    return (time.perf_counter_ns() - started) / 1_000_000, count


def _peak_bytes(function: Callable[[], int]) -> int:
    gc.collect()
    tracemalloc.start()
    function()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


def run_campaign(
    *,
    pair_count: int = 30,
    operations: int = 200,
    attempts: int = 4,
) -> dict[str, object]:
    if pair_count < 1 or operations < 1 or attempts < 1:
        raise ValueError("pair_count, operations and attempts must be positive")

    baseline_function = lambda: _baseline(
        operations=operations, attempts=attempts
    )
    candidate_function = lambda: _candidate(
        operations=operations, attempts=attempts
    )
    baseline_ms: list[float] = []
    candidate_ms: list[float] = []
    observations: list[PairedMissionObservation] = []
    baseline_count = candidate_count = 0

    for index in range(pair_count):
        if index % 2:
            candidate_latency, candidate_count = _timed(candidate_function)
            baseline_latency, baseline_count = _timed(baseline_function)
        else:
            baseline_latency, baseline_count = _timed(baseline_function)
            candidate_latency, candidate_count = _timed(candidate_function)
        baseline_ms.append(baseline_latency)
        candidate_ms.append(candidate_latency)
        oracle = _digest({"operations": operations, "successful": operations})
        observations.append(
            PairedMissionObservation(
                MissionMeasurement(
                    f"local-pair-{index}",
                    oracle,
                    baseline_latency,
                    0.5,
                    canonical_receipt_count=attempts,
                ),
                MissionMeasurement(
                    f"local-pair-{index}",
                    oracle,
                    candidate_latency,
                    1.0,
                    canonical_receipt_count=1,
                ),
            )
        )

    expected_baseline = operations * attempts
    if baseline_count != expected_baseline or candidate_count != operations:
        raise RuntimeError("receipt cardinality invariant failed")
    verdict = evaluate_paired_campaign(
        observations,
        CampaignPolicy(
            minimum_pairs=pair_count,
            minimum_median_speedup=1.0,
            maximum_p95_latency_ratio=1.0,
        ),
    )
    baseline_peak = _peak_bytes(baseline_function)
    candidate_peak = _peak_bytes(candidate_function)
    return {
        "schema": "OMEGA_ONE_CFBE_LOCAL_BENCHMARK_V3",
        "source": "LOCAL_OBSERVED_NON_PROVIDER",
        "candidate_route": "PREHASHED_RECOVERED_REPLAY_BATCH",
        "pair_count": pair_count,
        "operations_per_pair": operations,
        "attempts_per_operation": attempts,
        "baseline_receipts_per_pair": expected_baseline,
        "candidate_receipts_per_pair": operations,
        "canonical_receipt_reduction_ratio": 1 - (operations / expected_baseline),
        "baseline_median_ms": statistics.median(baseline_ms),
        "candidate_median_ms": statistics.median(candidate_ms),
        "median_speedup": verdict.median_speedup,
        "p95_latency_ratio": verdict.p95_latency_ratio,
        "campaign_state": verdict.state,
        "campaign_reasons": list(verdict.reasons),
        "measurement_sha256": verdict.measurement_sha256,
        "baseline_peak_bytes": baseline_peak,
        "candidate_peak_bytes": candidate_peak,
        "peak_memory_reduction_ratio": 1 - (candidate_peak / baseline_peak),
        "truth_boundary": verdict.truth_boundary,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=30)
    parser.add_argument("--operations", type=int, default=200)
    parser.add_argument("--attempts", type=int, default=4)
    args = parser.parse_args()
    result = run_campaign(
        pair_count=args.pairs,
        operations=args.operations,
        attempts=args.attempts,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["campaign_state"] == "QUALIFIED_LOCAL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
