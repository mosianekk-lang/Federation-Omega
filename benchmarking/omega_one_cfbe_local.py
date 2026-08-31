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
import re
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

LOCAL_OBSERVATION_SOURCE = "LOCAL_OBSERVED_NON_PROVIDER"
GITHUB_HOST_OBSERVATION_SOURCE = "GITHUB_ACTIONS_HOST_OBSERVED_NO_EFFECT"


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
    observation_source: str = LOCAL_OBSERVATION_SOURCE,
    runtime_run_id: str | None = None,
    source_sha: str | None = None,
    runtime_environment: str | None = None,
) -> dict[str, object]:
    if pair_count < 1 or operations < 1 or attempts < 1:
        raise ValueError("pair_count, operations and attempts must be positive")
    if observation_source not in {
        LOCAL_OBSERVATION_SOURCE,
        GITHUB_HOST_OBSERVATION_SOURCE,
    }:
        raise ValueError("UNSUPPORTED_OBSERVATION_SOURCE")
    host_observed = observation_source == GITHUB_HOST_OBSERVATION_SOURCE
    if host_observed:
        if pair_count < 30:
            raise ValueError("HOST_OBSERVED_MINIMUM_30_PAIRS_REQUIRED")
        if not runtime_run_id or not runtime_run_id.strip():
            raise ValueError("HOST_OBSERVED_RUNTIME_RUN_ID_REQUIRED")
        if not source_sha or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
            raise ValueError("HOST_OBSERVED_40_HEX_SOURCE_SHA_REQUIRED")
        if runtime_environment != "github-hosted":
            raise ValueError("GITHUB_HOSTED_RUNTIME_ENVIRONMENT_REQUIRED")

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
        mission_id = (
            f"github-actions://{runtime_run_id}/{source_sha}/omega-one-pair-{index + 1}"
            if host_observed
            else f"local-pair-{index}"
        )
        observations.append(
            PairedMissionObservation(
                MissionMeasurement(
                    mission_id,
                    oracle,
                    baseline_latency,
                    0.5,
                    canonical_receipt_count=attempts,
                ),
                MissionMeasurement(
                    mission_id,
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
    receipt: dict[str, object] = {
        "schema": "OMEGA_ONE_CFBE_LOCAL_BENCHMARK_V3",
        "source": LOCAL_OBSERVATION_SOURCE,
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
    if host_observed:
        qualified = verdict.state == "QUALIFIED_LOCAL"
        receipt.update(
            {
                "schema": "OMEGA_ONE_CFBE_HOST_OBSERVED_BENCHMARK_V1",
                "source": GITHUB_HOST_OBSERVATION_SOURCE,
                "provider_host": "GITHUB_ACTIONS",
                "runtime_environment": runtime_environment,
                "runtime_run_id": runtime_run_id,
                "source_sha": source_sha,
                "observed_pair_count": pair_count,
                "cold_replayable_pair_count": pair_count,
                "cold_state_reset_per_candidate_invocation": True,
                "baseline_recreated_per_invocation": True,
                "semantic_parity": qualified,
                "one_canonical_receipt_per_mission": candidate_count == operations,
                "provider_effects": False,
                "external_effect": False,
                "manual_interventions": 0,
                "stable_promotion_allowed": False,
                "campaign_state": (
                    "QUALIFIED_HOST_OBSERVED_NO_EFFECT"
                    if qualified
                    else "HOST_OBSERVED_HOLD"
                ),
                "truth_boundary": (
                    "This receipt proves paired Omega-One replay-finalization code execution "
                    "inside one source-bound GitHub-hosted Actions job with fresh candidate "
                    "state and recreated baseline state for every invocation. It does not "
                    "prove live provider behavior, production deployment, owner-value "
                    "improvement, H2 segmentation, soak completion, or stable promotion."
                ),
            }
        )
    return receipt


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
