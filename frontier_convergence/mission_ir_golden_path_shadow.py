from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from typing import Any

from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import BubblesWorkNode
from benchmarking.cfbe_omega.mission_execution_adapter_v1 import shadow_compile_mission_execution
from federation.bubbles_frontier_hyperperformance import WorkCell
from federation.mission_ir import ContextBudgetIR
from sovara.creative.genome import CreativeMissionGenome, RightsState
from sovara.creative.mission_ir_adapter import compile_creative_mission_ir
from sovara.creative.policy import ContentClass, PrivacyClass


SCHEMA = "FEDERATION-MISSION-IR-GOLDEN-PATH-SHADOW-CERTIFICATION-1"
MISSION_ID = "SC-MSN-CANARY-001"
BINDING_ID = "SC-MIR-20260831-001"
REFERENCE_SOURCE_MAIN = "dd7ff7b86c3aa4ed9cd49e0323d621384b28dc9f"
CONTROL_BINDING_EXPECTED_SHA256 = "f1980b968442991a33d2ad8e36a30dac2a2c33502bb8636c9fe6821f8616a331"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _mission():
    genome = CreativeMissionGenome.build(
        mission_id=MISSION_ID,
        content_class=ContentClass.BRAND_COMMERCIAL,
        objective=(
            "From ordinary-English Director input, produce one public-synthetic luxury fashion launch "
            "poster concept for fictional AURORA VEIL: synthetic adult model only, no real person or "
            "third-party brand/IP, 1080x1350 portrait, headline + subhead + CTA, preview-only and never "
            "publish automatically."
        ),
        privacy_class=PrivacyClass.PUBLIC,
        required_modalities=("image", "copy"),
        target_channels=("instagram",),
        rights_state=RightsState.NOT_APPLICABLE,
        owner_approval_required=True,
    )
    return compile_creative_mission_ir(
        genome,
        source_frontier=f"main@{REFERENCE_SOURCE_MAIN}",
        outcome_contract=(
            "One saved reviewable Canva design bound to Asset Registry with provider readback, QA receipt "
            "and owner decision; no automatic publication."
        ),
        proof_requirements=(
            "ASSET_ID",
            "OWNER_DECISION",
            "PROVIDER_READBACK",
            "QA_RECEIPT",
            "SAVED_DESIGN_ID",
        ),
        authority_requirements=("CANVA_BOUNDED_CREATE",),
        effect_class="BOUNDED_EFFECT",
        provider_allowlist=("CANVA",),
        context_budget=ContextBudgetIR(max_active_sources=5, max_heavy_sources=2),
        value_metrics=("latency_ms", "owner_interventions", "owner_minutes", "qa_result"),
    )


def _nodes() -> tuple[BubblesWorkNode, ...]:
    return (
        BubblesWorkNode(
            "SC-PLAN",
            "Producer plan",
            "CREATIVE",
            "Compile the bounded production plan without provider effect.",
            priority=1,
        ),
        BubblesWorkNode(
            "SC-QA",
            "QA contract",
            "QA",
            "Prepare preregistered QA courts.",
            dependencies=("SC-PLAN",),
            priority=2,
        ),
        BubblesWorkNode(
            "SC-SAVE",
            "Saved Canva design",
            "EFFECT",
            "Hold until owner selection and CANVA_BOUNDED_CREATE authority.",
            dependencies=("SC-QA",),
            priority=3,
            closure_state="PROVIDER_GATED",
        ),
    )


def _cells() -> tuple[WorkCell, ...]:
    return (
        WorkCell("cell-canva", ("canva", "creative-provider", "region-global")),
        WorkCell("cell-gemini", ("gemini", "reasoning-provider", "region-global")),
        WorkCell("cell-adobe", ("adobe", "creative-provider", "region-global")),
    )


def _legacy_structural_profile() -> dict[str, Any]:
    # This is a control-structure baseline, not observed runtime telemetry. It is
    # derived from the canonical SOVARA preparation surfaces used before MissionIR:
    # CREATIVE_MISSIONS, FIRST_COHORT_PLAN, QA_RELEASE_GATES, PROVIDER_POLICY,
    # MODEL_ROUTE_MATRIX and ASSET_REGISTRY.
    return {
        "evidence_mode": "CONTROL_STRUCTURE_NOT_RUNTIME_TELEMETRY",
        "control_surfaces_required": 6,
        "constraint_join_edges": 5,
        "proof_requirement_locations": 3,
        "single_execution_contract_digest": False,
        "context_budget_bound": False,
        "provider_policy_bound_to_cell_placement": False,
        "runtime_tool_calls": None,
        "runtime_latency_ms": None,
        "owner_interventions": None,
        "owner_minutes": None,
    }


def build_receipt(*, certification_source_sha: str) -> dict[str, Any]:
    mission = _mission()
    shadow = shadow_compile_mission_execution(
        mission,
        _nodes(),
        _cells(),
        cell_provider_aliases={
            "cell-canva": "CANVA",
            "cell-gemini": "GEMINI",
            "cell-adobe": "ADOBE",
        },
    )
    legacy = _legacy_structural_profile()
    candidate = {
        "evidence_mode": "HOSTED_ZERO_EFFECT_SHADOW_STRUCTURE",
        "control_surfaces_required": 2,
        "constraint_join_edges": 1,
        "proof_requirement_locations": 1,
        "single_execution_contract_digest": True,
        "context_budget_bound": True,
        "provider_policy_bound_to_cell_placement": True,
        "runtime_tool_calls": None,
        "runtime_latency_ms": None,
        "owner_interventions": None,
        "owner_minutes": None,
    }
    calculated_sha = mission.digest()
    provider_excluded = set(shadow.provider_policy_excluded_cell_ids)
    selected_cells = {
        cell_id
        for placement in shadow.cell_placements
        for cell_id in placement.selected_cell_ids
    }
    binding_hash_matches = calculated_sha == CONTROL_BINDING_EXPECTED_SHA256
    semantic_pass = all(
        (
            shadow.cell_shadow_state == "SHADOW_READY",
            shadow.selected_work_ids == ("SC-PLAN",),
            selected_cells == {"cell-canva"},
            provider_excluded == {"cell-adobe", "cell-gemini"},
            not shadow.provider_policy_unmapped_cell_ids,
            shadow.context_budget.max_active_sources == 5,
            shadow.context_budget.max_heavy_sources == 2,
            set(shadow.proof_requirements)
            == {"ASSET_ID", "OWNER_DECISION", "PROVIDER_READBACK", "QA_RECEIPT", "SAVED_DESIGN_ID"},
            set(shadow.authority_requirements) == {"CANVA_BOUNDED_CREATE", "OWNER_RELEASE"},
            shadow.effect_class == "BOUNDED_EFFECT",
            shadow.serving_route_changed is False,
            shadow.provider_effect_authorized is False,
            shadow.financial_effect_authorized is False,
            shadow.publication_authorized is False,
        )
    )
    state = "HOSTED_SHADOW_REFERENCE_PASS" if semantic_pass and binding_hash_matches else "HOSTED_SHADOW_REFERENCE_DRIFT"
    receipt = {
        "schema": SCHEMA,
        "state": state,
        "certification_source_sha": certification_source_sha,
        "reference_source_main": REFERENCE_SOURCE_MAIN,
        "binding_id": BINDING_ID,
        "mission_id": MISSION_ID,
        "control_binding_expected_sha256": CONTROL_BINDING_EXPECTED_SHA256,
        "calculated_mission_ir_sha256": calculated_sha,
        "binding_hash_matches": binding_hash_matches,
        "shadow_execution_digest": shadow.execution_digest,
        "cell_shadow_state": shadow.cell_shadow_state,
        "selected_work_ids": list(shadow.selected_work_ids),
        "cell_placements": [
            {
                "work_id": item.work_id,
                "state": item.state,
                "selected_cell_ids": list(item.selected_cell_ids),
                "candidate_cell_ids": list(item.candidate_cell_ids),
                "excluded_cell_ids": list(item.excluded_cell_ids),
                "allocation_digest": item.allocation_digest,
            }
            for item in shadow.cell_placements
        ],
        "provider_policy_excluded_cell_ids": list(shadow.provider_policy_excluded_cell_ids),
        "provider_policy_unmapped_cell_ids": list(shadow.provider_policy_unmapped_cell_ids),
        "context_budget": asdict(shadow.context_budget),
        "proof_requirements": list(shadow.proof_requirements),
        "authority_requirements": list(shadow.authority_requirements),
        "effect_class": shadow.effect_class,
        "semantic_pass": semantic_pass,
        "serving_route_changed": False,
        "provider_effect_authorized": False,
        "financial_effect_authorized": False,
        "publication_authorized": False,
        "external_effects": 0,
        "legacy_structural_profile": legacy,
        "mission_ir_structural_profile": candidate,
        "structural_deltas": {
            "control_surfaces": candidate["control_surfaces_required"] - legacy["control_surfaces_required"],
            "constraint_join_edges": candidate["constraint_join_edges"] - legacy["constraint_join_edges"],
            "proof_requirement_locations": candidate["proof_requirement_locations"] - legacy["proof_requirement_locations"],
        },
        "runtime_metrics": {
            "tool_call_delta": None,
            "latency_delta_ms": None,
            "owner_intervention_delta": None,
            "owner_minutes_delta": None,
            "observed_runtime_comparison_proven": False,
        },
        "stable_promotion_allowed": False,
        "truth_boundary": (
            "Hosted zero-effect shadow certification proves structural MissionIR compilation, CFBE work selection, "
            "CANVA provider-policy cell filtering, bounded context/proof/authority propagation and no-effect ceilings. "
            "Structural deltas are control-model comparisons, not observed runtime performance. Tool-call, latency and "
            "owner-burden deltas remain unmeasured until a like-for-like observed comparison is executed."
        ),
    }
    receipt["receipt_sha256"] = _sha256(receipt)
    return receipt


def main() -> int:
    source_sha = os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED")
    print(json.dumps(build_receipt(certification_source_sha=source_sha), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
