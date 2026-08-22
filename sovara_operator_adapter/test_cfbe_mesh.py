from __future__ import annotations

import unittest

from sovara_operator_adapter.cfbe_mesh import (
    MeshNodeProfile,
    MeshObjective,
    NodeAutoscaleSignal,
    can_continue_local_observation,
    decide_node_autoscale,
    mesh_resilience_state,
    node_conformance_state,
    promotion_gate,
    route_mesh_objective,
)


def node(node_id: str, *tags: str, **kwargs) -> MeshNodeProfile:
    defaults = dict(
        node_id=node_id,
        node_class="DOMAIN_CELL",
        parent_node="CFBE-OMEGA",
        domain_tags=tuple(tags),
        failure_domain=node_id,
        shard_key=node_id,
        authority_ceiling="A1_INTERNAL",
        source_current=True,
        health="HEALTHY",
        maturity="LOGICAL",
        cost_class="INCLUDED",
        existing_authority=True,
        external_state=True,
        async_operation=True,
        independent_readback_available=True,
        local_observation_without_sovereign=True,
        runtime_proven=False,
        reversible=True,
        reliability_score=0.8,
        value_score=0.8,
        information_gain_score=0.7,
    )
    defaults.update(kwargs)
    return MeshNodeProfile(**defaults)


class CFBEMeshTests(unittest.TestCase):
    def test_conformant_logical_node_does_not_require_runtime_proof(self) -> None:
        self.assertEqual(node_conformance_state(node("CFBE-GCP", "cloud")), "NODE_CONFORMANT")

    def test_raw_secret_requirement_is_prohibited(self) -> None:
        self.assertEqual(
            node_conformance_state(node("CFBE-SEC", "security", raw_secret_required=True)),
            "HOLD_RAW_SECRET_PROHIBITED",
        )

    def test_node_cannot_widen_authority_locally(self) -> None:
        held = node("CFBE-GCP", "cloud", iam_change_required=True)
        self.assertEqual(node_conformance_state(held), "HOLD_AUTHORITY_BOUNDARY")

    def test_local_observation_survives_sovereign_loss(self) -> None:
        n = node("CFBE-GITHUB", "software")
        self.assertTrue(can_continue_local_observation(n, sovereign_available=False))
        self.assertEqual(mesh_resilience_state([n], sovereign_available=False), "MESH_LOCAL_CONTINUITY_WITH_SOVEREIGN_LOSS")

    def test_unhealthy_node_isolated_without_collapsing_other_nodes(self) -> None:
        bad = node("CFBE-GCP", "cloud", health="UNHEALTHY")
        good = node("CFBE-GITHUB", "software")
        self.assertFalse(can_continue_local_observation(bad, sovereign_available=False))
        self.assertTrue(can_continue_local_observation(good, sovereign_available=False))
        self.assertEqual(mesh_resilience_state([bad, good], sovereign_available=False), "MESH_LOCAL_CONTINUITY_WITH_SOVEREIGN_LOSS")

    def test_route_prefers_matching_healthy_cell(self) -> None:
        objective = MeshObjective("OBJ-1", ("cloud",), "STATE-1")
        result = route_mesh_objective(objective, [node("CFBE-GITHUB", "software"), node("CFBE-GCP", "cloud")])
        self.assertEqual(result.status, "NODE_SELECTED")
        self.assertEqual(result.selected_node_id, "CFBE-GCP")
        self.assertFalse(result.sovereign_required)
        self.assertTrue(result.preserves_state)

    def test_runtime_required_excludes_logical_only_cell(self) -> None:
        objective = MeshObjective("OBJ-2", ("cloud",), "STATE-2", require_runtime=True)
        logical = node("CFBE-GCP", "cloud", runtime_proven=False)
        proven = node("CFBE-GITHUB", "cloud", runtime_proven=True)
        result = route_mesh_objective(objective, [logical, proven])
        self.assertEqual(result.selected_node_id, "CFBE-GITHUB")

    def test_correlated_failure_hint_prefers_different_domain_when_other_scores_equal(self) -> None:
        a = node("CELL-A", "runtime", failure_domain="provider-a")
        b = node("CELL-B", "runtime", failure_domain="provider-b")
        objective = MeshObjective("OBJ-3", ("runtime",), "STATE-3", preferred_failure_domain="provider-a")
        result = route_mesh_objective(objective, [a, b])
        self.assertEqual(result.selected_node_id, "CELL-B")

    def test_paid_or_consequential_objective_is_not_autonomously_routed(self) -> None:
        for objective in (
            MeshObjective("PAID", ("cloud",), "S", cost_class="PAID"),
            MeshObjective("IAM", ("cloud",), "S", iam_or_secret_change=True),
            MeshObjective("EXT", ("cloud",), "S", external_effect=True),
        ):
            result = route_mesh_objective(objective, [node("CFBE-GCP", "cloud")])
            self.assertEqual(result.status, "OWNER_OR_PROVIDER_TRIGGER_REQUIRED")
            self.assertTrue(result.owner_trigger_required)
            self.assertTrue(result.continue_unaffected_nodes)

    def test_high_pressure_separable_node_can_split_logically(self) -> None:
        decision = decide_node_autoscale(
            NodeAutoscaleSignal(
                "SIG-SPLIT",
                "CFBE-GCP",
                pressure=0.85,
                complexity=0.8,
                change_rate=0.7,
                opportunity_pressure=0.9,
                information_gain=0.8,
                value_density=0.75,
                distinct_subdomains=3,
            )
        )
        self.assertEqual(decision.status, "AUTONOMOUS_CONTROL_SPLIT_ADMISSIBLE")
        self.assertEqual(decision.action, "SPLIT_LOGICAL_CELL")
        self.assertFalse(decision.authorizes_provider_resource_creation)

    def test_low_value_duplicate_node_can_consolidate_without_deletion(self) -> None:
        decision = decide_node_autoscale(
            NodeAutoscaleSignal(
                "SIG-MERGE",
                "CFBE-LEGACY",
                pressure=0.2,
                complexity=0.3,
                change_rate=0.15,
                opportunity_pressure=0.15,
                information_gain=0.2,
                value_density=0.3,
                duplicate_overlap=0.9,
            )
        )
        self.assertEqual(decision.status, "AUTONOMOUS_NONDESTRUCTIVE_CONSOLIDATION_ADMISSIBLE")
        self.assertFalse(decision.authorizes_destructive_retirement)
        self.assertTrue(decision.preserves_history)

    def test_unhealthy_node_is_demoted_and_unaffected_nodes_continue(self) -> None:
        decision = decide_node_autoscale(
            NodeAutoscaleSignal(
                "SIG-HEALTH",
                "CFBE-GAS",
                pressure=0.7,
                complexity=0.7,
                change_rate=0.7,
                opportunity_pressure=0.7,
                information_gain=0.7,
                value_density=0.7,
                health="UNHEALTHY",
            )
        )
        self.assertEqual(decision.action, "DEMOTE_AND_REROUTE")
        self.assertTrue(decision.continue_unaffected_nodes)

    def test_evd_hold_blocks_mesh_expansion(self) -> None:
        decision = decide_node_autoscale(
            NodeAutoscaleSignal(
                "SIG-EVD",
                "CFBE-GCP",
                pressure=0.9,
                complexity=0.9,
                change_rate=0.9,
                opportunity_pressure=0.9,
                information_gain=0.9,
                value_density=0.9,
                distinct_subdomains=4,
                evd_verdict="HOLD_ARCHITECTURE_EXPANSION",
            )
        )
        self.assertEqual(decision.status, "HOLD_ARCHITECTURE_EXPANSION")

    def test_node_promotion_requires_runtime_and_positive_value_for_operational(self) -> None:
        logical = node("CFBE-GCP", "cloud", runtime_proven=False)
        self.assertEqual(promotion_gate(logical, shadow_passed=True, canary_passed=True, measured_value_positive=True), "CANARY_VERIFIED")
        runtime = node("CFBE-GITHUB", "software", runtime_proven=True)
        self.assertEqual(promotion_gate(runtime, shadow_passed=True, canary_passed=True, measured_value_positive=False), "CANARY_VERIFIED_VALUE_PENDING")
        self.assertEqual(promotion_gate(runtime, shadow_passed=True, canary_passed=True, measured_value_positive=True), "OPERATIONAL_NODE")


if __name__ == "__main__":
    unittest.main()
