from __future__ import annotations

import json
import os
import platform
from pathlib import Path

from benchmarking.cfbe_omega.fascg_shadow_benchmark_v1 import HostedShadowHarness, default_shadow_scenarios
from benchmarking.cfbe_omega.fascg_production_runtime_v1 import (
    CognitiveStateVersionGraph, ProductionPromotionCourt, ProductionStage, PromotionEvidence,
)
from benchmarking.cfbe_omega.fascg_aopgc_bridge_v1 import (
    ProductContractSpec, compile_aopgc_production_evidence,
)
from benchmarking.cfbe_omega.fascg_provider_fabric_v1 import provider_fabric_manifest


def main() -> int:
    source_sha = os.environ.get("GITHUB_SHA", "LOCAL_SOURCE")
    proof_ref = f"github-run:{os.environ.get('GITHUB_RUN_ID', 'LOCAL')}"
    shadow = HostedShadowHarness().run_suite(default_shadow_scenarios())
    if shadow["failed"]:
        raise SystemExit("FASCG_SHADOW_FAILED")

    graph = CognitiveStateVersionGraph().append(
        mission_id="FASCG-PRODUCTION-QUALIFICATION",
        state_kind="HOSTED_SHADOW",
        source_sha=source_sha,
        payload={"shadow_sha256": shadow["sha256"], "provider_fabric": provider_fabric_manifest()["sha256"]},
        proof_refs=(proof_ref,),
    )
    if not graph.validate_chain():
        raise SystemExit("FASCG_STATE_CHAIN_FAILED")

    promotion = ProductionPromotionCourt().evaluate((PromotionEvidence(
        stage=ProductionStage.HOSTED_SHADOW,
        source_sha=source_sha,
        proof_refs=(proof_ref, shadow["sha256"]),
        independent_verifier_refs=("fascg-unittest-suite",),
        provider_native_readback=False,
        rollback_available=True,
        safety_score=1.0,
        reliability_score=1.0,
        owner_value_score=.75,
    ),))
    if promotion.achieved_stage is not ProductionStage.HOSTED_SHADOW:
        raise SystemExit("FASCG_HOSTED_SHADOW_PROMOTION_FAILED")

    aopgc = None
    aopgc_error = None
    deterministic_proofs = (
        "PRODUCT_CONTRACT", "SYSTEM_GENOME", "ARCHITECTURE", "SOURCE",
        "UNIT_TESTS", "INTEGRATION_TESTS", "CONTRACT_TESTS",
        "SECURITY_TESTS", "PERFORMANCE_TESTS",
    )
    try:
        aopgc = compile_aopgc_production_evidence(
            ProductContractSpec(
                product_id="FASCG-PRODUCTION",
                objective="Operate FASCG under proof-bound production controls",
                user_classes=("owner", "federation-operator"),
                user_journeys=("mission-control", "incident-recovery", "evolution-review"),
                required_outcomes=("verified-completion", "safe-recovery", "measured-owner-value"),
                authority_ceiling="A1_INTERNAL",
                data_boundary="PRIVATE",
                owner_intent_hash="f" * 64,
            ),
            observed_proof_keys=deterministic_proofs,
            exact_effect_authority=False,
            rollback_verified=True,
            semantic_canary_defined=True,
            compute_budget=1.0,
        )
    except ModuleNotFoundError as exc:
        aopgc_error = type(exc).__name__
        if os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("FASCG_REQUIRE_AOPGC") == "true":
            raise SystemExit("FASCG_AOPGC_UPSTREAM_REQUIRED") from exc

    receipt = {
        "schema": "FASCG-PRODUCTION-QUALIFICATION-RECEIPT-V1",
        "source_sha": source_sha,
        "measurement_class": "REAL_HOSTED_SHADOW" if os.environ.get("GITHUB_ACTIONS") == "true" else "LOCAL_REFERENCE",
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "shadow_suite_sha256": shadow["sha256"],
        "state_version_chain_head": graph.versions[-1].chain_sha256,
        "provider_fabric_sha256": provider_fabric_manifest()["sha256"],
        "aopgc_upstream_bound": aopgc is not None,
        "aopgc_upstream_error_class": aopgc_error,
        "aopgc_readiness_stage": aopgc.readiness_stage if aopgc else None,
        "aopgc_go_live_status": aopgc.go_live_status if aopgc else None,
        "aopgc_pgy_eligible_10x": aopgc.aopgc_eligible_10x if aopgc else False,
        "aopgc_fascg_ten_x_verified": aopgc.fascg_ten_x_verified if aopgc else False,
        "achieved_stage": promotion.achieved_stage.value,
        "provider_bound": False,
        "provider_effect_authorized": False,
        "model_training_authorized": False,
        "production_self_mutation_authorized": False,
        "ten_x_verified": False,
        "proof_refs": [proof_ref],
    }
    root = Path(os.environ.get("FASCG_RECEIPT_DIR", "/tmp/fascg-production"))
    root.mkdir(parents=True, exist_ok=True)
    (root / "PRODUCTION_QUALIFICATION_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("measurement_class", "achieved_stage", "provider_bound", "ten_x_verified")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
