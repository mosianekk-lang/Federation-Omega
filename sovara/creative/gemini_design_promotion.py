from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any


EXPECTED_RUN_ID = 33206987595
EXPECTED_SOURCE_SHA = "fe8c4bf15a47e0f7a7873c195a320aeb192f1b62"
EXPECTED_ARTIFACT_ID = 9700068344
EXPECTED_ARTIFACT_DIGEST = "7c9f77d4ec6ca32f692bcc7d87ad955f04b6595ed04dbde45a8f40b68429a5cf"
EXPECTED_OUTPUT_SHA256 = "2130be2e7ac9ea4a82386fd441a2df5bc7fa4b3fb40257166314f74246dd4000"
EXPECTED_PROVIDER_RECEIPT_SHA256 = "4b0d9eb55339c209f2426d454c3aa2a92f64ad7925d7a47c8e944ce3f71e04fa"
EXPECTED_WORKFLOW_RECEIPT_SHA256 = "31c660a75a5590a2fd0e8a7a25eef97447369525beaeb355d9e9e92dad2bede4"
EXPECTED_CHALLENGE_ID = "SC-GEMINI-ARCH-20260828-001"
EXPECTED_MODEL_VERSION = "gemini-3.1-pro-preview"
EXPECTED_PROVIDER = "GOOGLE_VERTEX_AI"
EXPECTED_TRANSPORT = "VERTEX_AI_WIF_DIRECT"
EXPECTED_PROPOSALS = {f"PROP-{i:02d}" for i in range(1, 13)}


class PromotionDisposition(str, Enum):
    SOURCE_CANDIDATE = "SOURCE_CANDIDATE"
    EVIDENCE_HOLD = "EVIDENCE_HOLD"


@dataclass(frozen=True, slots=True)
class PromotionSummary:
    status: str
    source_candidates: tuple[str, ...]
    evidence_holds: tuple[str, ...]
    promotion_ceiling: str
    deployment_authorized: bool
    provider_effect_authorized: bool


class PromotionError(ValueError):
    pass


def load_manifest(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "SOVARA_GEMINI_G2_DESIGN_PROMOTION_V1":
        raise PromotionError("unexpected promotion schema")
    return payload


def _require_equal(name: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        raise PromotionError(f"{name} mismatch: {observed!r} != {expected!r}")


def validate_source_proof(source: dict[str, Any]) -> None:
    _require_equal("workflow_run_id", source.get("workflow_run_id"), EXPECTED_RUN_ID)
    _require_equal("workflow_source_sha", source.get("workflow_source_sha"), EXPECTED_SOURCE_SHA)
    _require_equal("artifact_id", source.get("artifact_id"), EXPECTED_ARTIFACT_ID)
    _require_equal("artifact_digest_sha256", source.get("artifact_digest_sha256"), EXPECTED_ARTIFACT_DIGEST)
    _require_equal("challenge_id", source.get("challenge_id"), EXPECTED_CHALLENGE_ID)
    _require_equal("transport", source.get("transport"), EXPECTED_TRANSPORT)
    _require_equal("provider", source.get("provider"), EXPECTED_PROVIDER)
    _require_equal("model_version", source.get("model_version"), EXPECTED_MODEL_VERSION)
    _require_equal("proposal_count", source.get("proposal_count"), 12)
    _require_equal("output_sha256", source.get("output_sha256"), EXPECTED_OUTPUT_SHA256)
    _require_equal("provider_receipt_sha256", source.get("provider_receipt_sha256"), EXPECTED_PROVIDER_RECEIPT_SHA256)
    _require_equal("workflow_receipt_sha256", source.get("workflow_receipt_sha256"), EXPECTED_WORKFLOW_RECEIPT_SHA256)

    response_id = str(source.get("response_id", "")).strip()
    if not response_id:
        raise PromotionError("provider response_id is required")
    if source.get("semantic_verified") is not True:
        raise PromotionError("semantic_verified must be true")
    if source.get("provider_native_readback") is not True:
        raise PromotionError("provider_native_readback must be true")


def validate_promotion_boundary(promotion: dict[str, Any]) -> None:
    _require_equal("promotion status", promotion.get("status"), "PERMITTED_WITH_GATES")
    _require_equal("promotion ceiling", promotion.get("promotion_ceiling"), "SOURCE_CANDIDATE")
    for forbidden in (
        "model_ranking_authority",
        "model_output_is_design_authority",
        "automatic_production_promotion",
        "deployment_authorized",
        "provider_effect_authorized",
        "spend_authorized",
        "publishing_authorized",
        "external_communication_authorized",
        "case_data_authorized",
        "real_person_data_authorized",
    ):
        if promotion.get(forbidden) is not False:
            raise PromotionError(f"{forbidden} must remain false")
    if not str(promotion.get("truth_boundary", "")).strip():
        raise PromotionError("truth_boundary is required")


def validate_normalization_rules(rules: dict[str, Any]) -> None:
    if rules.get("absolute_claims_promoted") is not False:
        raise PromotionError("absolute model claims must not be promoted")
    required_true = (
        "guarantee_language_becomes_testable_hypothesis",
        "predicted_roi_is_not_realised_roi",
        "provider_cost_savings_require_same-run_observation",
        "live_performance_tuning_starts_shadow_only",
        "new_last_requires_reuse_scan",
    )
    for key in required_true:
        if rules.get(key) is not True:
            raise PromotionError(f"normalization rule {key} must be true")


def validate_decisions(decisions: list[dict[str, Any]]) -> None:
    if len(decisions) != 12:
        raise PromotionError("exactly 12 proposal decisions are required")
    ids = [str(item.get("proposal_id", "")).strip() for item in decisions]
    if set(ids) != EXPECTED_PROPOSALS or len(set(ids)) != 12:
        raise PromotionError("proposal decisions must cover PROP-01..PROP-12 exactly once")

    for item in decisions:
        disposition = item.get("disposition")
        if disposition not in {x.value for x in PromotionDisposition}:
            raise PromotionError(f"unsupported disposition for {item.get('proposal_id')}")
        if item.get("authority_ceiling") != "A1_INTERNAL":
            raise PromotionError(f"authority ceiling widened for {item.get('proposal_id')}")
        if not str(item.get("normalized_objective", "")).strip():
            raise PromotionError(f"normalized objective missing for {item.get('proposal_id')}")
        if not str(item.get("proof_gate", "")).strip():
            raise PromotionError(f"proof gate missing for {item.get('proposal_id')}")
        if disposition == PromotionDisposition.EVIDENCE_HOLD.value and not item.get("hold_gates"):
            raise PromotionError(f"evidence hold lacks hold_gates for {item.get('proposal_id')}")


def evaluate_manifest(payload: dict[str, Any]) -> PromotionSummary:
    validate_source_proof(payload.get("source_proof") or {})
    validate_promotion_boundary(payload.get("promotion") or {})
    validate_normalization_rules(payload.get("normalization_rules") or {})
    decisions = payload.get("decisions") or []
    if not isinstance(decisions, list):
        raise PromotionError("decisions must be a list")
    validate_decisions(decisions)

    source = tuple(sorted(x["proposal_id"] for x in decisions if x["disposition"] == PromotionDisposition.SOURCE_CANDIDATE.value))
    holds = tuple(sorted(x["proposal_id"] for x in decisions if x["disposition"] == PromotionDisposition.EVIDENCE_HOLD.value))
    promotion = payload["promotion"]
    return PromotionSummary(
        status=promotion["status"],
        source_candidates=source,
        evidence_holds=holds,
        promotion_ceiling=promotion["promotion_ceiling"],
        deployment_authorized=promotion["deployment_authorized"],
        provider_effect_authorized=promotion["provider_effect_authorized"],
    )


def can_promote_to_source_candidate(payload: dict[str, Any]) -> bool:
    """Return true only for the controlled design/source-candidate layer.

    This function intentionally does not authorize deployment, provider effects,
    production traffic, spend, publishing, rights clearance, or external changes.
    """
    summary = evaluate_manifest(payload)
    return (
        summary.status == "PERMITTED_WITH_GATES"
        and summary.promotion_ceiling == "SOURCE_CANDIDATE"
        and not summary.deployment_authorized
        and not summary.provider_effect_authorized
    )
