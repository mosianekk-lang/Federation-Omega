from __future__ import annotations

import unittest

from services.sol62_client_runtime.asia_frontier_p0 import (
    Decision,
    DemonstrationStep,
    RouteCandidate,
    SandboxGrant,
    SandboxRequest,
    SpecialistModelCell,
    SpecialistRegistry,
    SwarmTask,
    WorkflowEpisode,
    compile_bounded_swarm,
    compile_demonstration_workflow,
    compile_p0_plan,
    evaluate_real_workflow,
    pareto_route_portfolio,
    sandbox_preflight,
    select_pareto_route,
)


class Sol62AsiaFrontierP0Tests(unittest.TestCase):
    def test_bounded_swarm_separates_authority_and_privacy_envelopes(self):
        result = compile_bounded_swarm(
            (
                SwarmTask("a", "search", 2, privacy_class="INTERNAL", authority_scope="READ_ONLY"),
                SwarmTask("b", "build", 3, ("a",), privacy_class="INTERNAL", authority_scope="READ_ONLY"),
                SwarmTask("c", "private", 1, privacy_class="PRIVATE", authority_scope="READ_ONLY"),
                SwarmTask("d", "write", 1, privacy_class="INTERNAL", authority_scope="LOCAL_WRITE"),
            ),
            max_subagents=8,
            max_tool_calls=16,
        )
        self.assertEqual(result["state"], "READY")
        self.assertEqual(result["subagent_count"], 3)
        self.assertFalse(result["authority_granted"])
        envelopes = {(row["privacy_class"], row["authority_scope"]) for row in result["shards"]}
        self.assertEqual(
            envelopes,
            {("INTERNAL", "READ_ONLY"), ("PRIVATE", "READ_ONLY"), ("INTERNAL", "LOCAL_WRITE")},
        )

    def test_swarm_cycle_and_budget_fail_closed(self):
        cycle = compile_bounded_swarm(
            (
                SwarmTask("a", "x", dependency_ids=("b",)),
                SwarmTask("b", "y", dependency_ids=("a",)),
            )
        )
        self.assertEqual(cycle["state"], "HOLD")
        self.assertEqual(cycle["reason"], "DEPENDENCY_CYCLE")
        budget = compile_bounded_swarm(
            (SwarmTask("a", "x", estimated_tool_calls=20),),
            max_tool_calls=2,
        )
        self.assertEqual(budget["reason"], "TOOL_CALL_BUDGET_EXCEEDED")

    def test_real_workflow_measurement_never_self_promotes(self):
        result = evaluate_real_workflow(
            (
                WorkflowEpisode("e1", True, True, 0, 4, 1000),
                WorkflowEpisode("e2", False, True, 1, 7, 2000),
            )
        )
        self.assertEqual(result["state"], "MEASURED")
        self.assertEqual(result["acceptance_rate"], 0.5)
        self.assertFalse(result["promotion_allowed"])

    def test_critical_real_workflow_regression_holds(self):
        result = evaluate_real_workflow(
            (WorkflowEpisode("e1", True, True, 0, 1, 100, critical_regressions=1),)
        )
        self.assertEqual(result["state"], "REGRESSION_HOLD")

    def test_sandbox_is_deny_first_and_exact_scope(self):
        request = SandboxRequest(
            "RUN",
            ("subprocess", "filesystem"),
            "sha256:abc",
            network_domains=("api.example.test",),
            filesystem_roots=("/workspace",),
        )
        self.assertEqual(sandbox_preflight(request, None)["decision"], Decision.DENY.value)
        grant = SandboxGrant(
            allowed_capabilities=("subprocess", "filesystem"),
            allowed_network_domains=("api.example.test",),
            allowed_filesystem_roots=("/workspace",),
            exact_command_fingerprint="sha256:abc",
        )
        allowed = sandbox_preflight(request, grant)
        self.assertEqual(allowed["decision"], Decision.ALLOW.value)
        self.assertFalse(allowed["authority_granted"])
        wrong = SandboxRequest(
            "RUN",
            ("subprocess", "filesystem"),
            "sha256:other",
            network_domains=("api.example.test",),
            filesystem_roots=("/workspace",),
        )
        self.assertEqual(
            sandbox_preflight(wrong, grant)["reason"],
            "COMMAND_FINGERPRINT_MISMATCH",
        )

    def test_pareto_portfolio_eliminates_dominated_routes_and_hard_gates(self):
        routes = (
            RouteCandidate("strong", 0.95, 0.95, 0.95, 0.9, 100, 1, 1),
            RouteCandidate("dominated", 0.8, 0.8, 0.8, 0.8, 200, 2, 2),
            RouteCandidate("cheap", 0.85, 0.9, 0.9, 0.95, 80, 0.2, 0.3),
            RouteCandidate("unauthorized", 1.0, 1.0, 1.0, 1.0, 1, 0, 0, authority_valid=False),
        )
        frontier = pareto_route_portfolio(routes)
        self.assertNotIn("dominated", {row.route_id for row in frontier})
        self.assertNotIn("unauthorized", {row.route_id for row in frontier})
        result = select_pareto_route(routes)
        self.assertEqual(result["state"], "READY")
        self.assertIn(result["selected_route_id"], {"strong", "cheap"})
        self.assertFalse(result["authority_granted"])

    def test_demonstration_compiler_requires_semantics_origin_and_effect_class(self):
        compiled = compile_demonstration_workflow(
            (
                DemonstrationStep("SEMANTIC_SNAPSHOT", {}),
                DemonstrationStep(
                    "CLICK_ELEMENT",
                    {"role": "button", "name": "New chat"},
                    effect_class="WEBSITE_STATE",
                ),
            )
        )
        self.assertEqual(compiled["state"], "READY")
        self.assertEqual(compiled["command_count"], 2)
        self.assertTrue(compiled["commands"][1]["requires_action_bound_authority"])
        self.assertFalse(compiled["authority_granted"])

        coordinate = compile_demonstration_workflow(
            (
                DemonstrationStep(
                    "CLICK_ELEMENT",
                    {"x": "100", "y": "200"},
                    effect_class="WEBSITE_STATE",
                ),
            )
        )
        self.assertEqual(coordinate["reason"], "UNSAFE_OR_BRITTLE_TARGET_ENCODING")

        cross_origin = compile_demonstration_workflow(
            (DemonstrationStep("SEMANTIC_SNAPSHOT", {}, origin="https://evil.example"),)
        )
        self.assertEqual(cross_origin["reason"], "ORIGIN_NOT_ADMITTED")

    def test_specialist_registry_selects_role_under_privacy_floor(self):
        registry = SpecialistRegistry(
            (
                SpecialistModelCell(
                    "local-guard",
                    ("GUARD",),
                    "LOCAL",
                    "OWNER_DEVICE",
                    True,
                    1.0,
                    0.9,
                    0.1,
                    100,
                ),
                SpecialistModelCell(
                    "remote-guard",
                    ("GUARD",),
                    "REMOTE",
                    "CLOUD",
                    True,
                    0.5,
                    0.98,
                    0.01,
                    50,
                ),
                SpecialistModelCell(
                    "reranker",
                    ("RERANK",),
                    "LOCAL",
                    "OWNER_DEVICE",
                    True,
                    1.0,
                    0.88,
                    0.1,
                    120,
                ),
            )
        )
        result = registry.select("guard", minimum_privacy=0.9)
        self.assertEqual(result["selected_cell_id"], "local-guard")
        self.assertFalse(result["authority_granted"])
        self.assertEqual(registry.select("embedding", minimum_privacy=0.9)["state"], "HOLD")

    def test_p0_plan_exposes_six_residuals_without_market_claim(self):
        plan = compile_p0_plan(
            objective="improve browser workflow, parallelism, cost and retrieval",
            reason="market frontier convergence",
        )
        self.assertEqual(plan["state"], "P0_RUNTIME_MECHANISMS_AVAILABLE")
        self.assertEqual(plan["mechanism_count"], 6)
        self.assertEqual(len({row["gene_id"] for row in plan["selected"]}), 6)
        self.assertFalse(plan["source_mutation_authority_granted"])
        self.assertFalse(plan["provider_effect_authority_granted"])
        self.assertFalse(plan["market_superiority_proven"])


if __name__ == "__main__":
    unittest.main()
