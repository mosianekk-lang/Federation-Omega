from __future__ import annotations

import unittest
from dataclasses import replace
from federation.omnisurface_fabric_v2 import EffectClass

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
            cost_ceiling=0.01,
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

    def test_zero_budget_holds_paid_surface_and_preserves_residual(self) -> None:
        packet = CognitivePacket(
            mission_id="M-ZERO-BUDGET",
            objective="Keep default zero-cost work within the owner's ceiling.",
            acceptance_predicates=("no_paid_route_selected",),
            research_required=True,
            idempotency_key="M-ZERO-BUDGET:1",
        )
        plan = self.fabric.compile(
            packet=packet,
            runtime_states=(runtime("GOOGLE-AI-STUDIO-GEMINI", "google-gemini"),),
        )
        self.assertEqual(plan.formation.selected_surface_ids, ())
        self.assertEqual(plan.formation.total_estimated_cost, 0.0)
        self.assertFalse(plan.complete)
        self.assertTrue(plan.alpha_omega.required)

    def test_zero_budget_allows_qualified_free_surface(self) -> None:
        packet = CognitivePacket(
            mission_id="M-FREE",
            objective="Use an existing included route without extra spending.",
            acceptance_predicates=("free_route_selected",),
            research_required=True,
            idempotency_key="M-FREE:1",
        )
        free = replace(runtime("GOOGLE-AI-STUDIO-GEMINI", "google-gemini"), estimated_cost=0.0)
        plan = self.fabric.compile(packet=packet, runtime_states=(free,))
        self.assertEqual(plan.formation.selected_surface_ids, ("GOOGLE-AI-STUDIO-GEMINI",))
        self.assertEqual(plan.formation.total_estimated_cost, 0.0)
        self.assertTrue(plan.complete)

    def test_nonfinite_budget_is_rejected_before_planning(self) -> None:
        for cost in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(cost=cost):
                packet = CognitivePacket(
                    mission_id="M-INVALID-BUDGET",
                    objective="A nonfinite amount is not a bounded budget.",
                    acceptance_predicates=("held",),
                    cost_ceiling=cost,
                    idempotency_key="M-INVALID-BUDGET:1",
                )
                with self.assertRaisesRegex(ValueError, "COST_CEILING"):
                    self.fabric.compile(packet=packet, runtime_states=())

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

    def test_every_intent_boundary_survives_and_changes_plan_identity(self):
        packet = CognitivePacket(
            mission_id="M-INTENT", objective="Preserve the full mission",
            acceptance_predicates=("original acceptance",),
            idempotency_key="M-INTENT:1",
        )
        plan = self.fabric.compile(packet=packet, runtime_states=())
        self.assertEqual(plan.intent, packet)
        changes = {
            "objective": "Changed objective", "acceptance_predicates": ("changed acceptance",),
            "authority_ceiling": "A0_INTERNAL", "privacy_class": "P2_CONFIDENTIAL",
            "cost_ceiling": 0.25, "required_capabilities": ("new capability",),
            "evidence_refs": ("source:2",), "uncertainty": ("unknown:2",),
            "falsifiers": ("falsifier:2",), "deadline_seconds": 600,
            "proof_floor": "INDEPENDENT_SEMANTIC_READBACK", "idempotency_key": "M-INTENT:2",
            "maximum_effect": EffectClass.OBSERVE,
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                changed = self.fabric.compile(packet=replace(packet, **{field: value}), runtime_states=())
                self.assertEqual(getattr(changed.intent, field), value)
                self.assertNotEqual(changed.intent_sha256, plan.intent_sha256)
                self.assertNotEqual(changed.plan_id, plan.plan_id)
        self.assertFalse(plan.to_dict()["execution_complete"])

    def test_observe_effect_is_carried_to_every_package(self):
        packet = CognitivePacket(
            mission_id="M-OBSERVE", objective="Observe only",
            acceptance_predicates=("no effects",), idempotency_key="M-OBSERVE:1",
            automation_required=True, research_required=True, creative_required=True,
            challenger_required=True, required_capabilities=("extra-capability",),
            maximum_effect=EffectClass.OBSERVE,
        )
        packages = self.fabric._packages(packet)
        self.assertEqual(len(packages), 5)
        self.assertTrue(all(item.maximum_effect is EffectClass.OBSERVE for item in packages))
        fallback = replace(packet, automation_required=False, research_required=False,
                           creative_required=False, challenger_required=False, required_capabilities=())
        self.assertIs(self.fabric._packages(fallback)[0].maximum_effect, EffectClass.OBSERVE)

    def test_intent_snapshot_cannot_change_when_callers_mutate_lists(self):
        acceptance = ["verified outcome"]
        packet = CognitivePacket(mission_id="M-FROZEN", objective="Freeze intent",
                                 acceptance_predicates=acceptance, idempotency_key="M-FROZEN:1")
        plan = self.fabric.compile(packet=packet, runtime_states=())
        acceptance.append("later change")
        self.assertEqual(plan.intent.acceptance_predicates, ("verified outcome",))

    def test_malformed_deadlines_and_required_fields_are_rejected(self):
        packet = CognitivePacket(mission_id="M-VALIDATE", objective="Validate before planning",
                                 acceptance_predicates=("held",), idempotency_key="M-VALIDATE:1")
        for changes in (
            {"deadline_seconds": float("nan")}, {"deadline_seconds": float("inf")},
            {"deadline_seconds": True}, {"deadline_seconds": 1.5},
            {"acceptance_predicates": ()}, {"acceptance_predicates": (" ",)},
            {"acceptance_predicates": tuple("x" for _ in range(33))},
            {"idempotency_key": ""}, {"proof_floor": ""}, {"privacy_class": ""},
            {"cost_ceiling": True}, {"automation_required": "false"},
            {"research_required": "false"}, {"creative_required": "false"},
            {"challenger_required": "false"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.fabric.compile(packet=replace(packet, **changes), runtime_states=())


if __name__ == "__main__":
    unittest.main()
