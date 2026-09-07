import unittest

from federation.aarek_v1 import (
    AarekKernel,
    AarekState,
    Decision,
    Evidence,
    EvidenceKind,
    MissionSnapshot,
    RegressionCode,
    RouteCandidate,
)


class AarekV1Test(unittest.TestCase):
    def setUp(self):
        self.kernel = AarekKernel()
        self.base = dict(
            mission_id="M1",
            objective="Close the mission with action-specific proof",
            required_terminal_predicates=("P1",),
        )

    def ev(self, kind, ref, action=True, provider=False, substantive=False):
        return Evidence(kind, ref, action, provider, substantive)

    def test_source_and_schedule_do_not_count_as_execution(self):
        receipt = self.kernel.evaluate(MissionSnapshot(
            **self.base,
            evidence=(self.ev(EvidenceKind.SOURCE, "src"), self.ev(EvidenceKind.SCHEDULE, "sched")),
        ))
        self.assertEqual(AarekState.BINDING_REQUIRED, receipt.state)
        self.assertFalse(receipt.provider_runtime_proven)

    def test_binding_then_execution_required(self):
        receipt = self.kernel.evaluate(MissionSnapshot(
            **self.base,
            evidence=(self.ev(EvidenceKind.BINDING, "binding"),),
        ))
        self.assertEqual(Decision.EXECUTE, receipt.decision)

    def test_execution_requires_semantic_readback(self):
        receipt = self.kernel.evaluate(MissionSnapshot(
            **self.base,
            evidence=(
                self.ev(EvidenceKind.BINDING, "binding"),
                self.ev(EvidenceKind.EXECUTION, "run", provider=True),
            ),
        ))
        self.assertEqual(AarekState.READBACK_REQUIRED, receipt.state)
        self.assertIn(RegressionCode.SEMANTIC_READBACK_MISSING.value, receipt.regressions)

    def test_unchanged_failed_route_forces_challenge(self):
        receipt = self.kernel.evaluate(MissionSnapshot(
            **self.base,
            evidence=(
                self.ev(EvidenceKind.BINDING, "binding"),
                self.ev(EvidenceKind.EXECUTION, "run"),
                self.ev(EvidenceKind.SEMANTIC_READBACK, "readback"),
            ),
            failure_fingerprint="F1",
            prior_failure_fingerprint="F1",
            selected_route_id="R1",
            prior_route_id="R1",
        ))
        self.assertEqual(AarekState.CHANGED_ROUTE_REQUIRED, receipt.state)
        self.assertIn(RegressionCode.UNCHANGED_ROUTE_RETRY.value, receipt.regressions)

    def test_materially_stronger_challenger_is_selected(self):
        routes = (
            RouteCandidate("R1", proof_strength=.3, semantic_readback=.3, correctness=.5),
            RouteCandidate("R2", callable_now=True, proof_strength=.9, semantic_readback=.9, correctness=.9),
        )
        receipt = self.kernel.evaluate(MissionSnapshot(
            **self.base,
            evidence=(
                self.ev(EvidenceKind.BINDING, "binding"),
                self.ev(EvidenceKind.EXECUTION, "run"),
                self.ev(EvidenceKind.SEMANTIC_READBACK, "readback"),
            ),
            failure_fingerprint="F2",
            failure_predicate_changed=True,
            selected_route_id="R1",
            route_candidates=routes,
        ))
        self.assertEqual(AarekState.CHALLENGER_SELECTED, receipt.state)
        self.assertEqual("R2", receipt.selected_route_id)

    def test_owner_offload_is_regression_while_machine_routes_remain(self):
        receipt = self.kernel.evaluate(MissionSnapshot(
            **self.base,
            owner_offload_proposed=True,
        ))
        self.assertIn(RegressionCode.OWNER_OFFLOAD_WHILE_MACHINE_ROUTE_EXISTS.value, receipt.regressions)
        self.assertTrue(receipt.auto_continue_required)

    def test_verified_win_spawns_next_improvement(self):
        receipt = self.kernel.evaluate(MissionSnapshot(
            **self.base,
            evidence=(
                self.ev(EvidenceKind.BINDING, "binding"),
                self.ev(EvidenceKind.EXECUTION, "run"),
                self.ev(EvidenceKind.SEMANTIC_READBACK, "readback"),
            ),
            verified_win=True,
        ))
        self.assertEqual(Decision.CAPTURE_WIN_AND_SPAWN_IMPROVEMENT, receipt.decision)

    def test_completion_requires_closed_terminal_debt_and_recompile(self):
        receipt = self.kernel.evaluate(MissionSnapshot(
            **self.base,
            evidence=(
                self.ev(EvidenceKind.BINDING, "binding"),
                self.ev(EvidenceKind.EXECUTION, "run", provider=True),
                self.ev(EvidenceKind.SEMANTIC_READBACK, "readback", provider=True),
            ),
            satisfied_terminal_predicates=("P1",),
            mission_recompiled=True,
        ))
        self.assertEqual(AarekState.COMPLETE_VERIFIED, receipt.state)
        self.assertEqual(Decision.ALLOW_COMPLETE_VERIFIED, receipt.decision)
        self.assertTrue(receipt.provider_runtime_proven)
        self.assertFalse(receipt.auto_continue_required)

    def test_owner_only_boundary_requires_machine_route_exhaustion(self):
        not_exhausted = self.kernel.evaluate(MissionSnapshot(
            **self.base,
            evidence=(
                self.ev(EvidenceKind.BINDING, "binding"),
                self.ev(EvidenceKind.EXECUTION, "run"),
                self.ev(EvidenceKind.SEMANTIC_READBACK, "readback"),
            ),
            satisfied_terminal_predicates=("P1",),
            owner_only_boundary="IAM consent",
            machine_routes_exhausted=False,
        ))
        self.assertNotEqual(AarekState.HELD_OWNER_ONLY, not_exhausted.state)

        exhausted = self.kernel.evaluate(MissionSnapshot(
            **self.base,
            evidence=(
                self.ev(EvidenceKind.BINDING, "binding"),
                self.ev(EvidenceKind.EXECUTION, "run"),
                self.ev(EvidenceKind.SEMANTIC_READBACK, "readback"),
            ),
            satisfied_terminal_predicates=("P1",),
            owner_only_boundary="IAM consent",
            machine_routes_exhausted=True,
        ))
        self.assertEqual(AarekState.HELD_OWNER_ONLY, exhausted.state)
        self.assertTrue(exhausted.owner_surface_allowed)


if __name__ == "__main__":
    unittest.main()
