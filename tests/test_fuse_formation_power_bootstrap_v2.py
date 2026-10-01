from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FormationPowerBootstrapV2Tests(unittest.TestCase):
    def test_bootstrap_inheritance_orders_power_before_surface_route_compile(self) -> None:
        bootstrap = json.loads(
            (ROOT / "config" / "fuse-bootstrap-inheritance-v3.json").read_text(encoding="utf-8")
        )
        order = bootstrap["required_order"]
        self.assertIn("FORMATION_POWER_INHERITANCE", order)
        self.assertIn("FORMATION_SURFACE_LOAD_BALANCER", order)
        self.assertIn("ROUTE_COMPILE", order)
        self.assertLess(order.index("FORMATION_POWER_INHERITANCE"), order.index("FORMATION_SURFACE_LOAD_BALANCER"))
        self.assertLess(order.index("FORMATION_POWER_INHERITANCE"), order.index("ROUTE_COMPILE"))
        bound = bootstrap["formation_power_inheritance"]
        self.assertEqual(bound["contract_id"], "FUSE-FORMATION-POWER-002")
        self.assertEqual(bound["applies_to"], "ALL_FUSE_WORKFLOWS")
        self.assertEqual(bound["agentic_frontier_gene_pool"], 53)
        self.assertEqual(bound["max_mutating_lanes"], 1)
        self.assertFalse(bound["builder_self_certification"])

    def test_respawn_manifest_requires_global_formation_power(self) -> None:
        manifest = json.loads(
            (ROOT / "respawn" / "federation_manifest.json").read_text(encoding="utf-8")
        )
        order = manifest["bootstrap_order"]
        self.assertIn("load_formation_power_inheritance_contract", order)
        self.assertIn("compile_workflow_formation_power", order)
        self.assertIn("compile_surface_formation", order)
        self.assertIn("execute", order)
        self.assertLess(order.index("compile_workflow_formation_power"), order.index("compile_surface_formation"))
        self.assertLess(order.index("compile_workflow_formation_power"), order.index("execute"))
        invariants = set(manifest["bootstrap_invariants"])
        expected = {
            "ALL_FUSE_WORKFLOWS_REQUIRE_FORMATION_POWER_COMPILE",
            "FORMATION_POWER_USES_EXISTING_ORGANS_NO_DUPLICATE_CONTROL_PLANE",
            "FORMATION_POWER_MAX_ONE_MUTATING_LANE",
            "FORMATION_POWER_BUILDER_CANNOT_SELF_CERTIFY",
            "FORMATION_POWER_PARALLELIZES_ONLY_DISJOINT_READY_WORK",
            "FORMATION_POWER_DYNAMIC_REPLAN_ON_CURRENTNESS_HEALTH_PROOF_OR_EPOCH_CHANGE",
            "FORMATION_POWER_LEARNING_CANNOT_EXPAND_AUTHORITY",
        }
        self.assertTrue(expected.issubset(invariants))
        bound = manifest["formation_power_inheritance"]
        self.assertEqual(bound["contract_id"], "FUSE-FORMATION-POWER-002")
        self.assertFalse(bound["authority_expansion"])
        self.assertFalse(bound["provider_execution_proven"])

    def test_respawn_bootstrap_service_contains_fail_closed_formation_power_guard(self) -> None:
        source = (ROOT / "respawn" / "bootstrap_service.py").read_text(encoding="utf-8")
        self.assertIn("def formation_power_inheritance_bootstrap_guard", source)
        self.assertIn("FUSE_FORMATION_POWER_BOOTSTRAP_GUARD_V2", source)
        self.assertIn("FORMATION_POWER_AFTER_SURFACE_FORMATION", source)
        self.assertIn("formation_power_guard = formation_power_inheritance_bootstrap_guard", source)
        self.assertIn('"formation_power_inheritance_guard": formation_power_guard', source)

    def test_power_contract_is_additive_and_non_authoritative(self) -> None:
        contract = json.loads(
            (ROOT / "config" / "fuse-formation-power-inheritance-v2.json").read_text(encoding="utf-8")
        )
        self.assertFalse(contract["creates_new_controller"])
        self.assertFalse(contract["creates_new_scheduler"])
        self.assertFalse(contract["creates_new_mission_bus"])
        self.assertFalse(contract["creates_new_authority_root"])
        self.assertFalse(contract["creates_new_truth_memory_proof_root"])
        self.assertFalse(contract["external_effect_authority"])
        self.assertFalse(contract["provider_execution_authority"])
        self.assertFalse(contract["builder_self_certification"])
        self.assertTrue(contract["dynamic_gene_inheritance"])
        self.assertTrue(contract["all_workflows_compile_formation"])
        self.assertFalse(contract["forced_multi_provider_fanout"])


if __name__ == "__main__":
    unittest.main()
