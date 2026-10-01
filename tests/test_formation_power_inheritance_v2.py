from __future__ import annotations

import json
from pathlib import Path
import unittest

from formation_omega.autonomic_fabric import ActionCandidate
from federation.formation_power_inheritance_v2 import (
    FormationPowerCompiler,
    FormationPowerMode,
    WorkflowClass,
    WorkflowFormationSpec,
)
from federation.formation_surface_load_balancer_v1 import (
    FormationWorkPackage,
    SurfaceRuntimeState,
    WorkKind,
)

ROOT = Path(__file__).resolve().parents[1]


def runtime(
    surface_id: str,
    *,
    provider_domain: str,
    quality: float = 0.9,
    latency_ms: float = 100.0,
    estimated_cost: float = 0.01,
) -> SurfaceRuntimeState:
    return SurfaceRuntimeState(
        surface_id=surface_id,
        authority_pass=True,
        privacy_pass=True,
        currentness_pass=True,
        proof_pass=True,
        health_pass=True,
        quota_pass=True,
        circuit_open=False,
        quality=quality,
        reliability=0.95,
        proof_strength=0.95,
        latency_ms=latency_ms,
        estimated_cost=estimated_cost,
        owner_burden=0.01,
        privacy_cost=0.01,
        maintenance_cost=0.01,
        strategic_value=0.7,
        parallel_slots=2,
        correlation_domains=(provider_domain,),
        proof_refs=(f"proof:{surface_id}",),
    )


class FormationPowerInheritanceV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = FormationPowerCompiler()

    def test_global_config_applies_to_all_fuse_workflows(self) -> None:
        cfg = json.loads(
            (ROOT / "config" / "fuse-formation-power-inheritance-v2.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(cfg["schema"], "FUSE_FORMATION_POWER_INHERITANCE_V2")
        self.assertEqual(cfg["version"], "2.0.0")
        self.assertEqual(cfg["applies_to"], "ALL_FUSE_WORKFLOWS")
        self.assertTrue(cfg["all_workflows_compile_formation"])
        self.assertEqual(cfg["agentic_frontier_gene_pool"], 53)
        self.assertEqual(cfg["max_mutating_lanes"], 1)
        self.assertFalse(cfg["creates_new_controller"])
        self.assertFalse(cfg["creates_new_scheduler"])
        self.assertFalse(cfg["creates_new_authority_root"])
        self.assertFalse(cfg["builder_self_certification"])

    def test_simple_workflow_stays_fast_and_minimum_sufficient(self) -> None:
        plan = self.compiler.compile(
            spec=WorkflowFormationSpec(
                workflow_id="WF-SIMPLE",
                objective="Inspect source state.",
                workflow_class=WorkflowClass.ENGINEERING,
                domains=frozenset({"ROUTING", "EVALUATION"}),
            ),
            packages=(
                FormationWorkPackage(
                    "source",
                    WorkKind.SOURCE_CONTROL,
                    ("pull_requests",),
                ),
            ),
            runtime_states=(
                runtime("GITHUB", provider_domain="github"),
                runtime("GOOGLE-CLOUD", provider_domain="google"),
                runtime("CANVA", provider_domain="canva"),
            ),
        )
        self.assertTrue(plan.complete)
        self.assertEqual(plan.mode, FormationPowerMode.FAST.value)
        self.assertEqual(plan.surface_plan.selected_surface_ids, ("GITHUB",))
        self.assertIn("WITNESS", plan.swarm_roles)
        self.assertEqual(plan.max_mutating_lanes, 1)
        self.assertFalse(plan.external_effect_authorized)

    def test_high_consequence_workflow_becomes_adversarial_and_independent(self) -> None:
        plan = self.compiler.compile(
            spec=WorkflowFormationSpec(
                workflow_id="WF-HIGH",
                objective="Produce high-consequence recommendation with independent challenge.",
                workflow_class=WorkflowClass.EVIDENCE,
                domains=frozenset({"ORCHESTRATION", "EVALUATION", "PROOF", "GOVERNANCE"}),
                consequential=True,
                multi_agent=True,
                requires_dynamic_models=True,
                requires_strict_self_verification=True,
            ),
            packages=(
                FormationWorkPackage(
                    "cognition",
                    WorkKind.COGNITION,
                    ("reasoning",),
                ),
            ),
            runtime_states=(
                runtime("OPENAI-GPT6-ASTRA", provider_domain="openai"),
                runtime("GOOGLE-AI-STUDIO-GEMINI", provider_domain="google"),
                runtime("OPENROUTER", provider_domain="openrouter"),
            ),
        )
        self.assertTrue(plan.complete)
        self.assertEqual(plan.mode, FormationPowerMode.ADVERSARIAL.value)
        self.assertIn("FALSIFIER", plan.swarm_roles)
        self.assertIn("WITNESS", plan.swarm_roles)
        assignment = plan.surface_plan.assignments[0]
        self.assertTrue(assignment.independent)
        self.assertEqual(len(assignment.selected_surface_ids), 2)
        self.assertFalse(plan.builder_self_certification_allowed)

    def test_research_hypothesis_workflow_inherits_deep_hypothesis_evolution(self) -> None:
        plan = self.compiler.compile(
            spec=WorkflowFormationSpec(
                workflow_id="WF-RESEARCH",
                objective="Research competing hypotheses and preserve falsifiers.",
                workflow_class=WorkflowClass.RESEARCH,
                domains=frozenset({"KNOWLEDGE", "ORCHESTRATION", "EVALUATION", "METACOGNITION"}),
                multi_agent=True,
                requires_hypothesis_evolution=True,
                requires_dynamic_tools=True,
                requires_memory=True,
            ),
            packages=(
                FormationWorkPackage(
                    "research",
                    WorkKind.KNOWLEDGE,
                    ("search",),
                    preferred_surface_ids=("GOOGLE-DRIVE",),
                ),
                FormationWorkPackage(
                    "reasoning",
                    WorkKind.COGNITION,
                    ("reasoning",),
                ),
            ),
            runtime_states=(
                runtime("GOOGLE-DRIVE", provider_domain="google-drive"),
                runtime("OPENAI-GPT6-ASTRA", provider_domain="openai"),
            ),
        )
        self.assertTrue(plan.complete)
        self.assertEqual(plan.mode, FormationPowerMode.DEEP.value)
        self.assertIn("AGF-049", plan.selected_gene_ids)
        self.assertIn("AGF-050", plan.selected_gene_ids)
        self.assertIn("EVIDENCE", plan.swarm_roles)
        self.assertIn("RECOVERY", plan.swarm_roles)

    def test_long_running_workflow_inherits_checkpoint_and_persistent_agent_genes(self) -> None:
        plan = self.compiler.compile(
            spec=WorkflowFormationSpec(
                workflow_id="WF-DURABLE",
                objective="Run a durable workflow with checkpoint and resume.",
                workflow_class=WorkflowClass.LONG_RUNNING,
                domains=frozenset({"DURABILITY", "CONTROL", "OBSERVABILITY"}),
                long_running=True,
                requires_persistent_agent=True,
                requires_cross_window_context=True,
            ),
            packages=(
                FormationWorkPackage(
                    "runtime",
                    WorkKind.RUNTIME,
                    ("cloud_run",),
                    preferred_surface_ids=("GOOGLE-CLOUD",),
                ),
            ),
            runtime_states=(runtime("GOOGLE-CLOUD", provider_domain="google-cloud"),),
        )
        self.assertTrue(plan.complete)
        for gene in ("AGF-007", "AGF-031", "AGF-042", "AGF-046", "AGF-047", "AGF-050"):
            self.assertIn(gene, plan.selected_gene_ids)
        self.assertIn("DURABLE_CHECKPOINT_RESUME", plan.orchestration)
        self.assertIn("CHECKPOINT_ON_LONG_RUNNING_WAIT", plan.checkpoint_policy)

    def test_creative_artifact_workflow_inherits_professional_artifact_gene(self) -> None:
        plan = self.compiler.compile(
            spec=WorkflowFormationSpec(
                workflow_id="WF-CREATIVE",
                objective="Create a professional visual artifact.",
                workflow_class=WorkflowClass.CREATIVE,
                domains=frozenset({"VALUE", "GOVERNANCE", "EVALUATION"}),
                requires_artifact_production=True,
            ),
            packages=(
                FormationWorkPackage(
                    "visual",
                    WorkKind.CREATIVE,
                    ("design",),
                    preferred_surface_ids=("CANVA",),
                ),
            ),
            runtime_states=(runtime("CANVA", provider_domain="canva"),),
        )
        self.assertTrue(plan.complete)
        self.assertIn("AGF-052", plan.selected_gene_ids)
        self.assertIn("AGF-038", plan.selected_gene_ids)
        self.assertEqual(plan.surface_plan.selected_surface_ids, ("CANVA",))

    def test_proof_directed_parallel_wave_serializes_shared_state(self) -> None:
        actions = (
            ActionCandidate(
                "A1",
                "read one",
                closure_leverage=0.8,
                information_gain=0.8,
                success_probability=0.9,
                reversibility=1.0,
                cost=0.1,
                risk=0.1,
                latency=0.1,
                shared_state_key="SAME",
            ),
            ActionCandidate(
                "A2",
                "read two",
                closure_leverage=0.7,
                information_gain=0.7,
                success_probability=0.9,
                reversibility=1.0,
                cost=0.1,
                risk=0.1,
                latency=0.1,
                shared_state_key="SAME",
            ),
            ActionCandidate(
                "A3",
                "read independent",
                closure_leverage=0.6,
                information_gain=0.8,
                success_probability=0.9,
                reversibility=1.0,
                cost=0.1,
                risk=0.1,
                latency=0.1,
                shared_state_key="OTHER",
            ),
        )
        plan = self.compiler.compile(
            spec=WorkflowFormationSpec(
                workflow_id="WF-PARALLEL",
                objective="Parallelize only collision-safe work.",
                max_parallel=3,
            ),
            packages=(
                FormationWorkPackage("source", WorkKind.SOURCE_CONTROL, ("pull_requests",)),
            ),
            runtime_states=(runtime("GITHUB", provider_domain="github"),),
            actions=actions,
        )
        self.assertEqual(len(plan.selected_action_ids), 2)
        self.assertIn("A1", plan.selected_action_ids)
        self.assertIn("A3", plan.selected_action_ids)
        self.assertNotIn("A2", plan.selected_action_ids)

    def test_no_workflow_formation_mints_effect_or_provider_authority(self) -> None:
        plan = self.compiler.compile(
            spec=WorkflowFormationSpec(
                workflow_id="WF-SAFE",
                objective="Compile without authority expansion.",
            ),
            packages=(
                FormationWorkPackage("source", WorkKind.SOURCE_CONTROL, ("pull_requests",)),
            ),
            runtime_states=(runtime("GITHUB", provider_domain="github"),),
        )
        self.assertFalse(plan.external_effect_authorized)
        self.assertFalse(plan.provider_execution_proven)
        self.assertFalse(plan.creates_new_controller)
        self.assertFalse(plan.creates_new_scheduler)
        self.assertFalse(plan.creates_new_authority_root)
        self.assertIn("UNKNOWN_EFFECT_REQUIRES_READBACK", json.loads(
            (ROOT / "config" / "fuse-formation-power-inheritance-v2.json").read_text(encoding="utf-8")
        )["global_invariants"])


if __name__ == "__main__":
    unittest.main()
