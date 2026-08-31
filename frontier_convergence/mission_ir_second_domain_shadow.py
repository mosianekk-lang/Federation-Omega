from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from typing import Any

from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import BubblesWorkNode
from benchmarking.cfbe_omega.mission_execution_adapter_v1 import shadow_compile_mission_execution
from federation.bubbles_frontier_hyperperformance import WorkCell
from federation.idea_to_system_compiler import compile_idea_to_system


SCHEMA = "FEDERATION-MISSION-IR-SECOND-DOMAIN-SHADOW-CERTIFICATION-1"
OBJECTIVE = (
    "Audit the current Federation execution architecture for duplicated mission contracts, fragmented "
    "proof/context/authority semantics, and MissionIR reuse opportunities without performing provider mutations."
)
MISSION_ID = "IDEA-305D6E9EF3876052"
REFERENCE_SOURCE_MAIN = "7b4fa3d747d7421e04fea1e4548ffb0f660b8306"
CONTROL_BINDING_EXPECTED_SHA256 = "e1cece11ef78b56eeb44d90c05e16a80316084c81b45dd2b5a5dce84d6b61f17"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _plan():
    return compile_idea_to_system(
        OBJECTIVE,
        source_frontier=f"main@{REFERENCE_SOURCE_MAIN}",
        domain_hint="RESEARCH",
    )


def _nodes() -> tuple[BubblesWorkNode, ...]:
    return (
        BubblesWorkNode(
            "FED-AUDIT-SOURCE",
            "Current source frontier read",
            "SOURCE",
            "Read current source and bind provenance without provider mutation.",
            priority=1,
        ),
        BubblesWorkNode(
            "FED-AUDIT-CONTROL",
            "Control-plane evidence read",
            "CONTROL",
            "Read only the CFBE/Sentinel/KDV pages needed by the active audit question.",
            dependencies=("FED-AUDIT-SOURCE",),
            priority=2,
        ),
        BubblesWorkNode(
            "FED-AUDIT-SYNTH",
            "Evidence synthesis",
            "SYNTHESIS",
            "Produce the proof-bounded architecture audit and MissionIR reuse decision.",
            dependencies=("FED-AUDIT-CONTROL",),
            priority=3,
        ),
    )


def _cells() -> tuple[WorkCell, ...]:
    return (
        WorkCell("cell-github-read", ("github", "source-read", "region-global")),
        WorkCell("cell-drive-read", ("drive", "control-read", "region-global")),
        WorkCell("cell-local-synth", ("local", "deterministic-synthesis", "region-local")),
    )


def build_receipt(*, certification_source_sha: str) -> dict[str, Any]:
    plan = _plan()
    mission = plan.mission_ir
    shadow = shadow_compile_mission_execution(mission, _nodes(), _cells())
    calculated_sha = mission.digest()
    selected_cells = {
        cell_id
        for placement in shadow.cell_placements
        for cell_id in placement.selected_cell_ids
    }
    binding_hash_matches = calculated_sha == CONTROL_BINDING_EXPECTED_SHA256
    semantic_pass = all(
        (
            mission.mission_id == MISSION_ID,
            mission.domain == "RESEARCH",
            mission.effect_class == "READ_ONLY",
            mission.authority_requirements == (),
            plan.intent.intent_classes == ("RESEARCH",),
            plan.intent.deliverables == ("EVIDENCE_MATRIX", "SOURCE_SET", "SYNTHESIS"),
            len(plan.intent.required_capabilities) == 13,
            shadow.cell_shadow_state == "SHADOW_READY",
            shadow.selected_work_ids == ("FED-AUDIT-SOURCE",),
            len(selected_cells) == 1,
            shadow.context_budget.max_active_sources == 8,
            shadow.context_budget.max_heavy_sources == 3,
            set(shadow.proof_requirements)
            == {"ACCEPTANCE_CRITERIA", "NO_REGRESSION", "SEMANTIC_READBACK", "SOURCE_PROVENANCE", "TRACE_RECEIPT"},
            shadow.serving_route_changed is False,
            shadow.provider_effect_authorized is False,
            shadow.financial_effect_authorized is False,
            shadow.publication_authorized is False,
        )
    )
    state = "HOSTED_SHADOW_SECOND_DOMAIN_PASS" if semantic_pass and binding_hash_matches else "HOSTED_SHADOW_SECOND_DOMAIN_DRIFT"
    receipt = {
        "schema": SCHEMA,
        "state": state,
        "certification_source_sha": certification_source_sha,
        "reference_source_main": REFERENCE_SOURCE_MAIN,
        "mission_id": MISSION_ID,
        "control_binding_expected_sha256": CONTROL_BINDING_EXPECTED_SHA256,
        "calculated_mission_ir_sha256": calculated_sha,
        "binding_hash_matches": binding_hash_matches,
        "intent_classes": list(plan.intent.intent_classes),
        "deliverables": list(plan.intent.deliverables),
        "capability_requirement_count": len(plan.intent.required_capabilities),
        "workflow_pattern": plan.workflow_pattern,
        "cell_shadow_state": shadow.cell_shadow_state,
        "selected_work_ids": list(shadow.selected_work_ids),
        "selected_cell_ids": sorted(selected_cells),
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
        "stable_promotion_allowed": False,
        "truth_boundary": (
            "Hosted zero-effect second-domain certification proves the generic Idea→System compiler can produce a "
            "registered READ_ONLY MissionIR that enters the existing CFBE/Bubbles shadow execution fabric without "
            "creative-domain adapters or effect authority. It does not prove provider serving, latency superiority, "
            "owner-value improvement, or that MissionIR replaces paged GitHub/CFBE/Sentinel/KDV truth."
        ),
    }
    receipt["receipt_sha256"] = _sha256(receipt)
    return receipt


def main() -> int:
    print(json.dumps(build_receipt(certification_source_sha=os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED")), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
