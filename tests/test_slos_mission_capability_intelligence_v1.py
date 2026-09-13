import unittest

from superior_logic.mission_capability_intelligence import (
    ExecutionSurface,
    MachineGenome,
    MissionCapabilityIntelligence,
    MissionResourceRequest,
    SurfaceReadiness,
)


class MissionCapabilityIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = MissionCapabilityIntelligence()
        self.request = MissionResourceRequest(
            mission_id="repair-1",
            required_capabilities=("PYTHON", "FUZZ"),
            preferred_capabilities=("MUTATION",),
            heavy_compute=True,
            prefer_owner_controlled=True,
        )

    def test_unbound_windows_is_not_fake_execution(self):
        windows = ExecutionSurface(
            surface_id="WINDOWS-H1",
            surface_type="WINDOWS_H1",
            provider="OWNER",
            readiness=SurfaceReadiness.AUTHENTICATED,
            capabilities=("PYTHON", "FUZZ", "MUTATION"),
            owner_controlled=True,
            proof_ref="",
            genome=MachineGenome(os_family="WINDOWS", logical_cores=16, ram_mib=32768),
        )
        github = ExecutionSurface(
            surface_id="GITHUB",
            surface_type="HOSTED_CI",
            provider="GITHUB",
            readiness=SurfaceReadiness.EXECUTION_PROVEN,
            capabilities=("PYTHON", "FUZZ"),
            proof_ref="RUN-1",
        )
        plan = self.engine.compile(self.request, (windows, github))
        self.assertEqual(plan.selected_surface_ids, ("GITHUB",))
        self.assertTrue(plan.degraded_compute_mode)
        self.assertFalse(plan.windows_execution_proven)
        self.assertIn("OWNER_CONTROLLED_HEAVY_COMPUTE", plan.capability_gaps)
        self.assertFalse(plan.effect_authority_granted)

    def test_proven_windows_becomes_preferred_heavy_compute_at_matched_readiness(self):
        windows = ExecutionSurface(
            surface_id="WINDOWS-H1",
            surface_type="WINDOWS_H1",
            provider="OWNER",
            readiness=SurfaceReadiness.LOAD_TESTED,
            capabilities=("PYTHON", "FUZZ", "MUTATION"),
            owner_controlled=True,
            proof_ref="MACHINE-RECEIPT-1",
            throughput_rank=100,
        )
        hosted = ExecutionSurface(
            surface_id="HOSTED",
            surface_type="HOSTED_CI",
            provider="GITHUB",
            readiness=SurfaceReadiness.LOAD_TESTED,
            capabilities=("PYTHON", "FUZZ", "MUTATION"),
            proof_ref="RUN-2",
            throughput_rank=200,
        )
        plan = self.engine.compile(self.request, (hosted, windows))
        self.assertEqual(plan.selected_surface_ids, ("WINDOWS-H1",))
        self.assertFalse(plan.degraded_compute_mode)
        self.assertTrue(plan.owner_controlled_heavy_compute_available)
        self.assertTrue(plan.windows_execution_proven)

    def test_higher_readiness_beats_owner_preference(self):
        windows = ExecutionSurface(
            surface_id="WINDOWS-H1",
            surface_type="WINDOWS_H1",
            provider="OWNER",
            readiness=SurfaceReadiness.EXECUTION_PROVEN,
            capabilities=("PYTHON", "FUZZ"),
            owner_controlled=True,
            proof_ref="MACHINE-R1",
        )
        hosted = ExecutionSurface(
            surface_id="HOSTED",
            surface_type="HOSTED_CI",
            provider="GITHUB",
            readiness=SurfaceReadiness.FAILOVER_PROVEN,
            capabilities=("PYTHON", "FUZZ"),
            proof_ref="RUN-HIGH",
        )
        plan = self.engine.compile(self.request, (windows, hosted))
        self.assertEqual(plan.selected_surface_ids, ("HOSTED",))
        self.assertFalse(plan.degraded_compute_mode)
        self.assertTrue(plan.owner_controlled_heavy_compute_available)
        self.assertFalse(plan.windows_execution_proven)

    def test_owner_surface_without_required_authority_does_not_close_heavy_compute_gap(self):
        request = MissionResourceRequest(
            mission_id="repair-auth",
            required_capabilities=("PYTHON", "FUZZ"),
            required_authority_actions=("RUN_ISOLATED_TESTS",),
            heavy_compute=True,
            prefer_owner_controlled=True,
        )
        windows = ExecutionSurface(
            surface_id="WINDOWS-H1",
            surface_type="WINDOWS_H1",
            provider="OWNER",
            readiness=SurfaceReadiness.LOAD_TESTED,
            capabilities=("PYTHON", "FUZZ"),
            authority_actions=(),
            owner_controlled=True,
            proof_ref="MACHINE-R2",
        )
        hosted = ExecutionSurface(
            surface_id="HOSTED",
            surface_type="HOSTED_CI",
            provider="GITHUB",
            readiness=SurfaceReadiness.LOAD_TESTED,
            capabilities=("PYTHON", "FUZZ"),
            authority_actions=("RUN_ISOLATED_TESTS",),
            proof_ref="RUN-AUTH",
        )
        plan = self.engine.compile(request, (windows, hosted))
        self.assertEqual(plan.selected_surface_ids, ("HOSTED",))
        self.assertTrue(plan.degraded_compute_mode)
        self.assertFalse(plan.owner_controlled_heavy_compute_available)
        self.assertIn("OWNER_CONTROLLED_HEAVY_COMPUTE", plan.capability_gaps)

    def test_missing_capability_fails_closed(self):
        surface = ExecutionSurface(
            surface_id="HOSTED",
            surface_type="HOSTED_CI",
            provider="GITHUB",
            readiness=SurfaceReadiness.EXECUTION_PROVEN,
            capabilities=("PYTHON",),
            proof_ref="RUN-3",
        )
        plan = self.engine.compile(self.request, (surface,))
        self.assertEqual(plan.selected_surface_ids, ())
        self.assertIn("CAPABILITY:FUZZ", plan.capability_gaps)
        self.assertIn("LIVE_EXECUTION_BINDING", plan.capability_gaps)

    def test_duplicate_surface_identity_is_rejected(self):
        row = ExecutionSurface(
            surface_id="X",
            surface_type="LOCAL",
            provider="OWNER",
            readiness=SurfaceReadiness.EXECUTION_PROVEN,
            capabilities=("PYTHON", "FUZZ"),
            proof_ref="R",
        )
        with self.assertRaises(ValueError):
            self.engine.compile(self.request, (row, row))


if __name__ == "__main__":
    unittest.main()
