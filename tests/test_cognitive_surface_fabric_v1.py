from __future__ import annotations

import unittest

from federation.cognitive_surface_fabric_v1 import (
    CONTRACT_ID,
    CognitivePacket,
    CognitiveSurfaceFabric,
)
from federation.formation_surface_load_balancer_v1 import SurfaceRuntimeState
from superior_logic.hypercube_bottleneck_resolver import BottleneckKind, BottleneckSignal


def runtime(surface_id: str, domain: str) -> SurfaceRuntimeState:
    return SurfaceRuntimeState(
        surface_id=surface_id,
        authority_pass=True,
        privacy_pass=True,
        currentness_pass=True,
        proof_pass=True,
        health_pass=True,
        quota_pass=True,
        quality=0.9,
        reliability=0.95,
        proof_strength=0.9,
        latency_ms=100.0,
        estimated_cost=0.01,
        owner_burden=0.01,
        privacy_cost=0.01,
        maintenance_cost=0.01,
        strategic_value=0.7,
        correlation_domains=(domain,),
        proof_refs=(f"proof:{surface_id}",),
    )


class CognitiveSurfaceFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = CognitiveSurfaceFabric()

    def test_cross_surface_integration_selects_requested_specialists(self) -> None:
        packet = CognitivePacket(
            mission_id="M-INTEGRATE",
            objective="Bind bounded cognitive intelligence across owned surfaces.",
            acceptance_predicates=("formation_complete", "proof_bound"),
            evidence_refs=("control:cognitive-surface",),
            cost_ceiling=1.0,
            automation_required=True,
            research_required=True,
            creative_required=True,
            challenger_required=True,
            idempotency_key="M-INTEGRATE:1",
        )
        plan = self.fabric.compile(
            packet=packet,
            runtime_states=(
                runtime("GOOGLE-APPS-SCRIPT", "google-apps-script"),
                runtime("GOOGLE-AI-STUDIO-GEMINI", "google-gemini"),
                runtime("CANVA", "canva"),
                runtime("OPENROUTER", "openrouter"),
            ),
        )
        self.assertEqual(plan.contract_id, CONTRACT_ID)
        self.assertTrue(plan.complete)
        self.assertEqual(
            set(plan.formation.selected_surface_ids),
            {"GOOGLE-APPS-SCRIPT", "GOOGLE-AI-STUDIO-GEMINI", "CANVA", "OPENROUTER"},
        )
        self.assertFalse(plan.external_effect_authorized)
        self.assertFalse(plan.provider_execution_proven)
        self.assertFalse(plan.authority_minted)
        self.assertFalse(plan.alpha_omega.required)

    def test_simple_research_does_not_force_all_surfaces(self) -> None:
        packet = CognitivePacket(
            mission_id="M-RESEARCH",
            objective="Run one structured research lane.",
            acceptance_predicates=("answer_verified",),
            research_required=True,
            idempotency_key="M-RESEARCH:1",
        )
        plan = self.fabric.compile(
            packet=packet,
            runtime_states=(
                runtime("GOOGLE-AI-STUDIO-GEMINI", "google-gemini"),
                runtime("CANVA", "canva"),
                runtime("OPENROUTER", "openrouter"),
                runtime("GOOGLE-APPS-SCRIPT", "google-apps-script"),
            ),
        )
        self.assertTrue(plan.complete)
        self.assertEqual(plan.formation.selected_surface_ids, ("GOOGLE-AI-STUDIO-GEMINI",))

    def test_missing_capability_emits_alpha_omega_minimum_residual(self) -> None:
        packet = CognitivePacket(
            mission_id="M-GAP",
            objective="Close one missing capability.",
            acceptance_predicates=("capability_closed",),
            required_capabilities=("novel_owner_specific_capability",),
            evidence_refs=("gap:evidence:1",),
            idempotency_key="M-GAP:1",
        )
        plan = self.fabric.compile(packet=packet, runtime_states=())
        self.assertFalse(plan.complete)
        self.assertTrue(plan.hypercube_required)
        self.assertTrue(plan.alpha_omega.required)
        self.assertIn("novel_owner_specific_capability", plan.alpha_omega.residual_capabilities)
        self.assertFalse(plan.alpha_omega.provider_effect_authorized)
        self.assertFalse(plan.authority_minted)

    def test_measured_gap_can_be_harvested_by_existing_hypercube(self) -> None:
        packet = CognitivePacket(
            mission_id="M-HC",
            objective="Resolve a measured integration bottleneck.",
            acceptance_predicates=("gap_resolved",),
            required_capabilities=("novel_owner_specific_capability",),
            evidence_refs=("trace:gap:1",),
            idempotency_key="M-HC:1",
        )
        signal = BottleneckSignal(
            bottleneck_id="BOT-HC-1",
            kind=BottleneckKind.UNKNOWN,
            summary="Measured capability gap remains after surface formation.",
            evidence_refs=("trace:gap:1",),
            throughput_drag=0.7,
            latency_share=0.5,
            queue_wait_share=0.2,
            failure_recurrence=0.4,
            dependency_centrality=0.8,
            owner_burden=0.3,
            cost_pressure=0.2,
            proof_gap=0.7,
            risk=0.2,
            commercial_leverage=0.6,
            differentiation_potential=0.7,
            internal_coverage=0.1,
            affected_missions=2,
            internal_capabilities=("Formation", "ProofOS"),
        )
        plan = self.fabric.compile(
            packet=packet,
            runtime_states=(),
            bottleneck_signal=signal,
        )
        self.assertIsNotNone(plan.hypercube_resolution)
        assert plan.hypercube_resolution is not None
        self.assertFalse(plan.hypercube_resolution["external_effect_authorized"])
        self.assertFalse(plan.hypercube_resolution["stable_self_promotion_allowed"])
        self.assertTrue(plan.alpha_omega.required)

    def test_packet_fails_closed_above_internal_authority(self) -> None:
        packet = CognitivePacket(
            mission_id="M-EFFECT",
            objective="Do not widen authority.",
            acceptance_predicates=("held",),
            authority_ceiling="A2_OWNER_RESERVED",
            idempotency_key="M-EFFECT:1",
        )
        with self.assertRaisesRegex(ValueError, "AUTHORITY_CEILING"):
            self.fabric.compile(packet=packet, runtime_states=())


if __name__ == "__main__":
    unittest.main()
