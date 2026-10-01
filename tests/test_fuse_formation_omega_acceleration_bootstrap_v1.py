from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FormationOmegaAccelerationBootstrapV1Tests(unittest.TestCase):
    def test_bootstrap_order_places_acceleration_before_surface_route_compile(self) -> None:
        bootstrap = json.loads(
            (ROOT / "config" / "fuse-bootstrap-inheritance-v3.json").read_text(encoding="utf-8")
        )
        order = bootstrap["required_order"]
        self.assertIn("FORMATION_POWER_INHERITANCE", order)
        self.assertIn("FORMATION_OMEGA_ACCELERATION", order)
        self.assertIn("FORMATION_SURFACE_LOAD_BALANCER", order)
        self.assertLess(order.index("FORMATION_POWER_INHERITANCE"), order.index("FORMATION_OMEGA_ACCELERATION"))
        self.assertLess(order.index("FORMATION_OMEGA_ACCELERATION"), order.index("FORMATION_SURFACE_LOAD_BALANCER"))
        bound = bootstrap["formation_omega_acceleration"]
        self.assertEqual(bound["contract_id"], "FUSE-FORMATION-OMEGA-ACCEL-001")
        self.assertEqual(bound["five_minute_slo_seconds"], 300)
        self.assertTrue(bound["omega_scientia_required"])
        self.assertEqual(bound["ultimate_programming_profile"], "FORMATION_ULTIMATE_PROGRAMMING_V1")
        self.assertEqual(bound["alpha_omega_compiler_profile"], "FORMATION_ALPHA_OMEGA_COMPILER_V1")

    def test_respawn_requires_all_acceleration_compile_steps_before_execute(self) -> None:
        manifest = json.loads(
            (ROOT / "respawn" / "federation_manifest.json").read_text(encoding="utf-8")
        )
        order = manifest["bootstrap_order"]
        for step in (
            "load_formation_omega_acceleration_contract",
            "compile_five_minute_scientia",
            "compile_applicable_ultimate_programming",
            "compile_applicable_alpha_omega",
        ):
            self.assertIn(step, order)
            self.assertLess(order.index(step), order.index("execute"))
        self.assertLess(
            order.index("compile_applicable_alpha_omega"),
            order.index("compile_surface_formation"),
        )
        invariants = set(manifest["bootstrap_invariants"])
        self.assertIn("ALL_FUSE_WORKFLOWS_GET_FIVE_MINUTE_SCIENTIA_PREFLIGHT", invariants)
        self.assertIn("OVER_BUDGET_FORMATION_MUST_RECOMPILE_BEFORE_EXECUTION", invariants)
        self.assertIn("PROGRAMMING_WORK_INHERITS_FORMATION_ULTIMATE_PROGRAMMING", invariants)
        self.assertIn("BUILD_AND_RESIDUAL_WORK_INHERITS_ALPHA_OMEGA_COMPILER", invariants)

    def test_respawn_source_has_fail_closed_acceleration_guard(self) -> None:
        source = (ROOT / "respawn" / "bootstrap_service.py").read_text(encoding="utf-8")
        self.assertIn("def formation_omega_acceleration_bootstrap_guard", source)
        self.assertIn("FUSE_FORMATION_OMEGA_ACCELERATION_BOOTSTRAP_GUARD_V1", source)
        self.assertIn("FORMATION_ACCELERATION_FIVE_MINUTE_BUDGET_MISMATCH", source)
        self.assertIn("formation_acceleration_guard = formation_omega_acceleration_bootstrap_guard", source)
        self.assertIn('"formation_omega_acceleration_guard": formation_acceleration_guard', source)


if __name__ == "__main__":
    unittest.main()
