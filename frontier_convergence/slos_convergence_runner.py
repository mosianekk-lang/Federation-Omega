from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from benchmarking.omega_one_cfbe_local import (
    GITHUB_HOST_OBSERVATION_SOURCE,
    run_campaign as run_omega_one_campaign,
)

from federation.superior_logic_convergence_measurement import (
    ObservationMode,
    ProfileObservation,
    aggregate_campaign,
    compare_pair,
    compile_control_slice,
    default_mission_oracles,
    full_control_universe,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BASELINE_OBSERVATION_PATH = (
    REPOSITORY_ROOT
    / "benchmarking"
    / "cfbe_omega"
    / "bubbles_chatbridge_payload_ingress_observation_20260830_v1.json"
)
OMEGA_ONE_HOST_PAIR_COUNT = 30


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_baseline(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    baseline = json.loads(raw)
    if baseline.get("schema") != "CFBE-BUBBLES-CHATBRIDGE-PAYLOAD-INGRESS-OBSERVATION-V1":
        raise ValueError("HOSTED_SHADOW_BASELINE_SCHEMA_MISMATCH")
    measurements = baseline.get("measurements", {})
    if int(measurements.get("raw_chars", 0)) <= 0:
        raise ValueError("HOSTED_SHADOW_BASELINE_CHARS_REQUIRED")
    if measurements.get("failure_signal_preserved") is not True:
        raise ValueError("HOSTED_SHADOW_BASELINE_SIGNAL_REQUIRED")
    if baseline.get("canary", {}).get("external_effects") != 0:
        raise ValueError("HOSTED_SHADOW_BASELINE_EXTERNAL_EFFECT")
    return baseline, _sha256_bytes(raw)


def _candidate_context_chars(*, mission_id: str, sequence: int, controls: frozenset[str]) -> int:
    capsule = {
        "schema": "CFBE-SLOS-HOSTED-SHADOW-CAPSULE-V1",
        "mission_id": mission_id,
        "sequence": sequence,
        "profile": "CONSTITUTIONAL_CORE_PLUS_MISSION_SLICE_PLUS_CAPSULE",
        "active_controls": sorted(controls),
        "cold_history": "POINTERS_ONLY",
        "external_effect": False,
    }
    return len(_canonical_json(capsule))


def run_hosted_shadow_campaign(
    *,
    pair_count: int = 30,
    run_id: str | None = None,
    source_sha: str | None = None,
    baseline_path: Path = BASELINE_OBSERVATION_PATH,
) -> dict[str, Any]:
    if pair_count < 30:
        raise ValueError("HOSTED_SHADOW_MINIMUM_30_PAIRS_REQUIRED")
    if pair_count > 300:
        raise ValueError("HOSTED_SHADOW_MAXIMUM_300_PAIRS")
    baseline, baseline_sha256 = _load_baseline(baseline_path)
    runtime_run_id = run_id or os.environ.get("GITHUB_RUN_ID") or "LOCAL_NO_EFFECT"
    runtime_source_sha = source_sha or os.environ.get("GITHUB_SHA") or "UNBOUND_SOURCE_SHA"
    oracles = default_mission_oracles()
    full_controls = full_control_universe(oracles)
    baseline_chars = int(baseline["measurements"]["raw_chars"])
    pairs = []

    for index in range(pair_count):
        sequence = index + 1
        oracle = oracles[index % len(oracles)]
        proof_refs = (
            f"github-actions://{runtime_run_id}/{runtime_source_sha}/pair/{sequence}",
            f"sha256:{baseline_sha256}",
        )
        baseline_observation = ProfileObservation(
            profile="FULL_DOCTRINE_ACTIVE_CONTEXT",
            mission_id=oracle.mission_id,
            mode=ObservationMode.HOSTED_SHADOW,
            active_controls=full_controls,
            context_chars=baseline_chars,
            tool_round_trips=0,
            owner_interventions=0,
            stale_state_rejected=True,
            duplicate_suppressed=True,
            trace_complete=True,
            proof_refs=proof_refs,
        )
        candidate_controls = compile_control_slice(oracle)
        candidate_observation = ProfileObservation(
            profile="CONSTITUTIONAL_CORE_PLUS_MISSION_SLICE_PLUS_CAPSULE",
            mission_id=oracle.mission_id,
            mode=ObservationMode.HOSTED_SHADOW,
            active_controls=candidate_controls,
            context_chars=_candidate_context_chars(
                mission_id=oracle.mission_id,
                sequence=sequence,
                controls=candidate_controls,
            ),
            tool_round_trips=0,
            owner_interventions=0,
            stale_state_rejected=True,
            duplicate_suppressed=True,
            trace_complete=True,
            proof_refs=proof_refs,
        )
        pairs.append(compare_pair(oracle, baseline_observation, candidate_observation))

    campaign = aggregate_campaign(pairs)
    passed = (
        campaign.pair_count == pair_count
        and campaign.hosted_shadow_pair_count == pair_count
        and campaign.structural_pass_count == pair_count
        and campaign.zero_critical_omissions
        and campaign.observed_pair_count == 0
        and not campaign.empirical_value_candidate
        and not campaign.stable_promotion_allowed
    )
    receipt = {
        "schema": "CFBE-SLOS-HOSTED-SHADOW-CAMPAIGN-V1",
        "state": "HOSTED_SHADOW_30_OF_30_PASS" if passed else "HOSTED_SHADOW_HOLD",
        "runtime": "FRONTIER_RUNTIME_QUALIFICATION_PROVIDER_DISABLED",
        "runtime_run_id": runtime_run_id,
        "source_sha": runtime_source_sha,
        "baseline_observation_sha256": baseline_sha256,
        "pair_count": campaign.pair_count,
        "hosted_shadow_pair_count": campaign.hosted_shadow_pair_count,
        "observed_pair_count": campaign.observed_pair_count,
        "structural_pass_count": campaign.structural_pass_count,
        "zero_critical_omissions": campaign.zero_critical_omissions,
        "median_context_reduction": campaign.median_context_reduction,
        "median_tool_round_trip_delta": campaign.median_tool_round_trip_delta,
        "median_owner_intervention_delta": campaign.median_owner_intervention_delta,
        "structural_candidate": campaign.structural_candidate,
        "empirical_value_candidate": campaign.empirical_value_candidate,
        "stable_promotion_allowed": campaign.stable_promotion_allowed,
        "provider_effects": False,
        "external_effect": False,
        "manual_interventions": 0,
        "full_doctrine_rollback": "PRESERVED",
        "observed_empirical_campaign_progress": "0/30",
        "truth_boundary": (
            "This receipt proves 30 deterministic, proof-referenced, identical-oracle pairs "
            "executed on the existing provider-disabled hosted shadow runner. It does not "
            "prove provider behavior, native ChatGPT interception, owner-value improvement, "
            "production deployment, or stable SLOS promotion."
        ),
        "pairs": [asdict(pair) for pair in pairs],
    }
    receipt["receipt_sha256"] = _sha256_bytes(_canonical_json(receipt).encode("utf-8"))
    return receipt


def run_omega_one_host_campaign(
    *,
    pair_count: int = OMEGA_ONE_HOST_PAIR_COUNT,
    operations: int = 200,
    attempts: int = 4,
    environment: Mapping[str, str] | None = None,
    campaign_runner: Callable[..., dict[str, object]] = run_omega_one_campaign,
) -> dict[str, object]:
    runtime = os.environ if environment is None else environment
    if runtime.get("GITHUB_ACTIONS") != "true":
        raise ValueError("GITHUB_ACTIONS_HOST_IDENTITY_REQUIRED")
    if runtime.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise ValueError("GITHUB_HOSTED_RUNNER_REQUIRED")
    return campaign_runner(
        pair_count=pair_count,
        operations=operations,
        attempts=attempts,
        observation_source=GITHUB_HOST_OBSERVATION_SOURCE,
        runtime_run_id=runtime.get("GITHUB_RUN_ID"),
        source_sha=runtime.get("GITHUB_SHA"),
        runtime_environment=runtime.get("RUNNER_ENVIRONMENT"),
    )


def main() -> int:
    receipt = run_hosted_shadow_campaign()
    exit_code = 0
    if os.environ.get("GITHUB_ACTIONS") == "true":
        try:
            omega_receipt = run_omega_one_host_campaign()
        except (RuntimeError, ValueError) as exc:
            omega_receipt = {
                "schema": "OMEGA_ONE_CFBE_HOST_OBSERVED_BENCHMARK_V1",
                "campaign_state": "HOST_OBSERVED_HOLD",
                "campaign_reasons": [str(exc)],
                "provider_effects": False,
                "external_effect": False,
                "stable_promotion_allowed": False,
            }
        qualified = (
            omega_receipt.get("campaign_state")
            == "QUALIFIED_HOST_OBSERVED_NO_EFFECT"
            and omega_receipt.get("observed_pair_count") == OMEGA_ONE_HOST_PAIR_COUNT
            and omega_receipt.get("cold_replayable_pair_count")
            == OMEGA_ONE_HOST_PAIR_COUNT
            and omega_receipt.get("semantic_parity") is True
            and omega_receipt.get("one_canonical_receipt_per_mission") is True
            and omega_receipt.get("provider_effects") is False
            and omega_receipt.get("external_effect") is False
        )
        receipt["omega_one_host_observed_campaign"] = omega_receipt
        receipt["omega_one_host_gate"] = "PASS" if qualified else "HOLD"
        receipt.pop("receipt_sha256", None)
        receipt["receipt_sha256"] = _sha256_bytes(
            _canonical_json(receipt).encode("utf-8")
        )
        exit_code = 0 if qualified else 2
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
