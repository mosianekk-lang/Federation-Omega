from __future__ import annotations

import unittest

from federation.formation_surface_load_balancer_v1 import (
    FormationSurfaceLoadBalancer,
    FormationWorkPackage,
    SurfaceRuntimeState,
    WorkKind,
)
from federation.omnisurface_fabric_v2 import EffectClass, build_default_registry


def runtime(
    surface_id: str,
    *,
    quality: float = 0.9,
    reliability: float = 0.95,
    proof_strength: float = 0.9,
    latency_ms: float = 100.0,
    estimated_cost: float = 0.01,
    strategic_value: float = 0.5,
    provider_domain: str | None = None,
    proof_pass: bool = True,
) -> SurfaceRuntimeState:
    return SurfaceRuntimeState(
        surface_id=surface_id,
        authority_pass=True,
        privacy_pass=True,
        currentness_pass=True,
        proof_pass=proof_pass,
        health_pass=True,
        quota_pass=True,
        quality=quality,
        reliability=reliability,
        proof_strength=proof_strength,
        latency_ms=latency_ms,
        estimated_cost=estimated_cost,
        owner_burden=0.01,
        privacy_cost=0.01,
        maintenance_cost=0.01,
        strategic_value=strategic_value,
        correlation_domains=((provider_domain or surface_id.lower()),),
        proof_refs=(f"proof:{surface_id}",),
    )


class FormationSurfaceLoadBalancerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = build_default_registry()
        self.balancer = FormationSurfaceLoadBalancer(self.registry)

    def test_required_user_surfaces_are_globally_discoverable(self) -> None:
        for surface_id in (
            "GOOGLE-APPS-SCRIPT",
            "GOOGLE-CLOUD",
            "GOOGLE-AI-STUDIO-GEMINI",
            "CANVA",
            "OPENROUTER",
        ):
            self.assertIn(surface_id, self.registry.surfaces)

    def test_specialist_formation_load_balances_across_requested_surfaces(self) -> None:
        packages = (
            FormationWorkPackage(
                "workspace",
                WorkKind.AUTOMATION,
                ("workspace_automation",),
                preferred_surface_ids=("GOOGLE-APPS-SCRIPT",),
            ),
            FormationWorkPackage(
                "runtime",
                WorkKind.RUNTIME,
                ("cloud_run", "eventarc"),
                preferred_surface_ids=("GOOGLE-CLOUD",),
            ),
            FormationWorkPackage(
                "google-cognition",
                WorkKind.COGNITION,
                ("function_calling",),
                preferred_surface_ids=("GOOGLE-AI-STUDIO-GEMINI",),
            ),
            FormationWorkPackage(
                "visual",
                WorkKind.CREATIVE,
                ("design", "presentation"),
                preferred_surface_ids=("CANVA",),
            ),
            FormationWorkPackage(
                "challenger",
                WorkKind.COGNITION,
                ("provider_marketplace", "challenger"),
                preferred_surface_ids=("OPENROUTER",),
            ),
        )
        states = (
            runtime("GOOGLE-APPS-SCRIPT", provider_domain="google-apps-script"),
            runtime("GOOGLE-CLOUD", provider_domain="google-cloud"),
            runtime("GOOGLE-AI-STUDIO-GEMINI", provider_domain="google-gemini"),
            runtime("CANVA", provider_domain="canva"),
            runtime("OPENROUTER", provider_domain="openrouter"),
        )
        plan = self.balancer.compile(
            mission_id="M-SPECIALIST",
            packages=packages,
            runtime_states=states,
            max_parallel_surfaces=4,
            total_cost_ceiling=1.0,
        )
        self.assertTrue(plan.complete)
        for surface_id in (
            "GOOGLE-APPS-SCRIPT",
            "GOOGLE-CLOUD",
            "GOOGLE-AI-STUDIO-GEMINI",
            "CANVA",
            "OPENROUTER",
        ):
            self.assertIn(surface_id, plan.selected_surface_ids)
        self.assertFalse(plan.external_effect_authorized)
        self.assertFalse(plan.provider_execution_proven)
        self.assertFalse(plan.authority_minted)

    def test_simple_task_uses_minimum_sufficient_surface_not_all_surfaces(self) -> None:
        plan = self.balancer.compile(
            mission_id="M-SIMPLE",
            packages=(
                FormationWorkPackage(
                    "source",
                    WorkKind.SOURCE_CONTROL,
                    ("pull_requests",),
                ),
            ),
            runtime_states=(
                runtime("GITHUB", quality=0.95, provider_domain="github"),
                runtime("CANVA", quality=1.0, provider_domain="canva"),
                runtime("GOOGLE-CLOUD", quality=1.0, provider_domain="google-cloud"),
                runtime("OPENROUTER", quality=1.0, provider_domain="openrouter"),
            ),
        )
        self.assertTrue(plan.complete)
        self.assertEqual(plan.selected_surface_ids, ("GITHUB",))

    def test_fusion_requires_provider_and_correlation_independence(self) -> None:
        package = FormationWorkPackage(
            "fusion",
            WorkKind.COGNITION,
            ("reasoning",),
            require_independent_candidates=True,
            candidate_count=2,
        )
        plan = self.balancer.compile(
            mission_id="M-FUSION",
            packages=(package,),
            runtime_states=(
                runtime("OPENAI-GPT6-ASTRA", quality=0.99, provider_domain="openai"),
                runtime("GOOGLE-AI-STUDIO-GEMINI", quality=0.97, provider_domain="google"),
                runtime("OPENROUTER", quality=0.96, provider_domain="openrouter"),
            ),
        )
        self.assertTrue(plan.complete)
        assignment = plan.assignments[0]
        self.assertTrue(assignment.independent)
        self.assertEqual(len(assignment.selected_surface_ids), 2)
        providers = {self.registry.surfaces[x].provider for x in assignment.selected_surface_ids}
        self.assertEqual(len(providers), 2)

    def test_two_same_provider_models_do_not_satisfy_independence(self) -> None:
        plan = self.balancer.compile(
            mission_id="M-CORRELATED",
            packages=(
                FormationWorkPackage(
                    "fusion",
                    WorkKind.COGNITION,
                    ("reasoning",),
                    require_independent_candidates=True,
                    candidate_count=2,
                ),
            ),
            runtime_states=(
                runtime("OPENAI-GPT6-ASTRA", provider_domain="openai-shared"),
                runtime("OPENAI-GPT56-LUNA", provider_domain="openai-shared"),
            ),
        )
        self.assertFalse(plan.complete)
        self.assertEqual(plan.missing_packages, ("fusion",))

    def test_unproven_surface_is_held_not_silently_used(self) -> None:
        plan = self.balancer.compile(
            mission_id="M-CREATIVE",
            packages=(
                FormationWorkPackage(
                    "visual",
                    WorkKind.CREATIVE,
                    ("design",),
                ),
            ),
            runtime_states=(runtime("CANVA", proof_pass=False, provider_domain="canva"),),
        )
        self.assertFalse(plan.complete)
        held = [x for x in plan.held_surfaces if x.surface_id == "CANVA"]
        self.assertTrue(held)
        self.assertIn("PROOF_HOLD", held[0].reasons)

    def test_cost_ceiling_can_hold_an_otherwise_eligible_surface(self) -> None:
        plan = self.balancer.compile(
            mission_id="M-BUDGET",
            packages=(
                FormationWorkPackage(
                    "visual",
                    WorkKind.CREATIVE,
                    ("design",),
                ),
            ),
            runtime_states=(
                runtime("CANVA", estimated_cost=5.0, provider_domain="canva"),
            ),
            total_cost_ceiling=1.0,
        )
        self.assertFalse(plan.complete)
        self.assertEqual(plan.total_estimated_cost, 0.0)

    def test_parallel_waves_respect_global_parallel_ceiling(self) -> None:
        packages = (
            FormationWorkPackage("p1", WorkKind.AUTOMATION, ("workspace_automation",)),
            FormationWorkPackage("p2", WorkKind.RUNTIME, ("cloud_run",)),
            FormationWorkPackage("p3", WorkKind.CREATIVE, ("design",)),
        )
        plan = self.balancer.compile(
            mission_id="M-WAVES",
            packages=packages,
            runtime_states=(
                runtime("GOOGLE-APPS-SCRIPT"),
                runtime("GOOGLE-CLOUD"),
                runtime("CANVA"),
            ),
            max_parallel_surfaces=2,
        )
        self.assertTrue(plan.complete)
        self.assertTrue(all(len(wave) <= 2 for wave in plan.execution_waves))
        self.assertGreaterEqual(len(plan.execution_waves), 2)

    def test_consequential_requirement_cannot_use_internal_only_surface(self) -> None:
        plan = self.balancer.compile(
            mission_id="M-EFFECT",
            packages=(
                FormationWorkPackage(
                    "effect",
                    WorkKind.GENERAL,
                    ("provider_marketplace",),
                    maximum_effect=EffectClass.CONSEQUENTIAL,
                ),
            ),
            runtime_states=(runtime("OPENROUTER"),),
        )
        self.assertFalse(plan.complete)
        held = [x for x in plan.held_surfaces if x.surface_id == "OPENROUTER"]
        self.assertTrue(held)
        self.assertIn("EFFECT_CEILING_TOO_LOW", held[0].reasons)


if __name__ == "__main__":
    unittest.main()
