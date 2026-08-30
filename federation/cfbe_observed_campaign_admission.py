from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "CFBE-SLOS-OBSERVED-CAMPAIGN-ADMISSION-BRIDGE-V1"
INPUT_SCHEMA = "BUBBLES-30-PAIR-SHADOW-CERTIFICATION-1"
BASE_SOURCE = "73963da2b1e23b87c0bb440c044a32fbc08d3ce8"
CURRENT_SOURCE = "fc9cc59f25ddb46f7daebf1a2739986067398ac3"
EXPECTED_RECEIPT_SHA256 = "c324d1b726677e5d2bea7bf01b8f7d9dc1e98616c86ab94d34ff1f259dfab437"
EXPECTED_MISSIONS = frozenset(
    {
        "CURRENT_STATE_READ",
        "PROVIDER_EFFECT",
        "LEGAL_FORENSIC",
        "FAILURE_RECOVERY",
        "EVOLUTION_BENCHMARK",
        "CROSS_CHAT_HEARTBEAT",
        "LARGE_TOOL_OUTPUT",
        "VISUAL_ARTIFACT_ASSURANCE",
    }
)
REQUIRED_PROOF_PREFIXES = frozenset({"provider", "baseline", "candidate", "source"})
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT_PATH = (
    REPOSITORY_ROOT
    / "benchmarking"
    / "cfbe_omega"
    / "bubbles_30_pair_observed_certification_20260830.json"
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def admit_observed_campaign(raw: bytes) -> dict[str, Any]:
    receipt_sha256 = _sha256_bytes(raw)
    _require(receipt_sha256 == EXPECTED_RECEIPT_SHA256, "RECEIPT_HASH_MISMATCH")
    receipt = json.loads(raw)
    return _validate_decoded_receipt(receipt, receipt_sha256)


def _validate_decoded_receipt(receipt: dict[str, Any], receipt_sha256: str) -> dict[str, Any]:
    _require(receipt.get("schema") == INPUT_SCHEMA, "INPUT_SCHEMA_MISMATCH")
    _require(receipt.get("source_commit") == BASE_SOURCE, "SOURCE_LINEAGE_MISMATCH")
    _require(receipt.get("host") == "CODEX_LOCAL_ZERO_EFFECT_SHADOW", "HOST_IDENTITY_MISMATCH")
    _require(receipt.get("external_effects") == 0, "EXTERNAL_EFFECT_PRESENT")
    _require(receipt.get("writes") == 0, "PROVIDER_WRITE_PRESENT")
    _require(receipt.get("communications") == 0, "COMMUNICATION_PRESENT")
    _require(receipt.get("provider_reads") == 30, "PROVIDER_READ_COUNT_MISMATCH")
    _require(receipt.get("provider_successes") == 30, "PROVIDER_SUCCESS_COUNT_MISMATCH")

    campaign = receipt.get("campaign") or {}
    pairs = receipt.get("pairs") or []
    _require(len(pairs) == 30, "PAIR_COUNT_MISMATCH")
    _require(campaign.get("pair_count") == 30, "CAMPAIGN_PAIR_COUNT_MISMATCH")
    _require(campaign.get("observed_pair_count") == 30, "OBSERVED_PAIR_COUNT_MISMATCH")
    _require(campaign.get("structural_pass_count") == 30, "STRUCTURAL_PASS_COUNT_MISMATCH")
    _require(campaign.get("zero_critical_omissions") is True, "CRITICAL_OMISSION_PRESENT")
    _require(campaign.get("structural_candidate") is True, "STRUCTURAL_CANDIDATE_REQUIRED")
    _require(campaign.get("empirical_value_candidate") is True, "EMPIRICAL_VALUE_CANDIDATE_REQUIRED")
    _require(campaign.get("stable_promotion_allowed") is False, "STABLE_PROMOTION_MUST_REMAIN_DISABLED")
    _require(float(campaign.get("median_context_reduction", 0)) >= 0.80, "CONTEXT_REDUCTION_BELOW_THRESHOLD")
    _require(float(campaign.get("median_tool_round_trip_delta", 1)) <= 0, "TOOL_ROUND_TRIP_REGRESSION")
    _require(float(campaign.get("median_owner_intervention_delta", 1)) <= 0, "OWNER_INTERVENTION_REGRESSION")

    mission_ids: set[str] = set()
    provider_counts: dict[str, int] = {}
    for pair in pairs:
        mission_id = pair.get("mission_class")
        mission_ids.add(mission_id)
        provider = pair.get("provider")
        provider_counts[provider] = provider_counts.get(provider, 0) + 1
        measurement = pair.get("measurement") or {}
        _require(measurement.get("mission_id") == mission_id, "MISSION_IDENTITY_MISMATCH")
        _require(measurement.get("mode") == "OBSERVED", "OBSERVATION_MODE_MISMATCH")
        _require(measurement.get("structural_pass") is True, "STRUCTURAL_PAIR_FAILURE")
        _require(float(measurement.get("candidate_control_coverage", 0)) == 1.0, "CONTROL_COVERAGE_INCOMPLETE")
        _require(not measurement.get("candidate_missing_controls"), "MISSING_CONTROL_PRESENT")
        _require(not measurement.get("candidate_behavior_failures"), "BEHAVIOR_FAILURE_PRESENT")
        _require(float(measurement.get("tool_round_trip_delta", 1)) <= 0, "PAIR_TOOL_REGRESSION")
        _require(float(measurement.get("owner_intervention_delta", 1)) <= 0, "PAIR_OWNER_BURDEN_REGRESSION")
        proof_refs = pair.get("proof_refs") or []
        prefixes = {str(ref).split(":", 1)[0] for ref in proof_refs}
        _require(REQUIRED_PROOF_PREFIXES.issubset(prefixes), "PAIR_PROOF_REFERENCES_INCOMPLETE")
        _require(f"source:{BASE_SOURCE}" in proof_refs, "PAIR_SOURCE_PROOF_MISMATCH")

    _require(mission_ids == EXPECTED_MISSIONS, "MISSION_ORACLE_SET_MISMATCH")
    _require(provider_counts == {"github": 8, "drive": 8, "gmail": 7, "canva": 7}, "PROVIDER_PORTFOLIO_MISMATCH")

    normalized = {
        "schema": SCHEMA,
        "decision": "ADMISSIBLE_AS_SEPARATE_OBSERVED_EMPIRICAL_VALUE_CANDIDATE",
        "canonical_admission_state": "ADAPTER_VALIDATED_NOT_PROVIDER_REGISTERED",
        "input_receipt_sha256": receipt_sha256,
        "input_schema": INPUT_SCHEMA,
        "source_lineage": {
            "base": BASE_SOURCE,
            "current": CURRENT_SOURCE,
            "base_is_verified_merge_base": True,
            "commits_ahead": 3,
        },
        "pair_count": 30,
        "observed_pair_count": 30,
        "structural_pass_count": 30,
        "zero_critical_omissions": True,
        "mission_oracle_set": sorted(mission_ids),
        "provider_counts": provider_counts,
        "median_context_reduction": campaign["median_context_reduction"],
        "median_tool_round_trip_delta": campaign["median_tool_round_trip_delta"],
        "median_owner_intervention_delta": campaign["median_owner_intervention_delta"],
        "empirical_value_candidate": True,
        "stable_promotion_allowed": False,
        "provider_authority_granted": False,
        "runtime_deployment_proven": False,
        "owner_value_proven": False,
        "external_effects": 0,
        "provider_writes": 0,
        "truth_boundary": (
            "The source-pinned Bubbles receipt is compatible with the latest CFBE OBSERVED "
            "measurement core. It is not the fc9cc59 HOSTED_SHADOW runner receipt, does not "
            "prove deployment or owner value, and cannot authorize stable SLOS promotion."
        ),
    }
    normalized["bridge_receipt_sha256"] = _sha256_bytes(_canonical_json(normalized).encode("utf-8"))
    return normalized


def main() -> int:
    print(
        json.dumps(
            admit_observed_campaign(DEFAULT_RECEIPT_PATH.read_bytes()),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
