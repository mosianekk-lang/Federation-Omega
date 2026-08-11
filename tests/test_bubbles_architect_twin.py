import unittest

from bubbles.architect_twin import BubblesArchitectTwin, MaturityStage, Project
from bubbles.portfolio_loader import load_twin


class BubblesArchitectTwinTests(unittest.TestCase):
    def test_stage_does_not_jump_over_missing_runtime(self):
        proofs = {"source", "tests", "provider_canary_contract"}
        self.assertEqual(
            BubblesArchitectTwin.verified_stage(proofs),
            MaturityStage.DETERMINISTIC_TESTED,
        )

    def test_provider_execution_without_readback_is_not_provider_verified(self):
        proofs = {
            "source",
            "tests",
            "runtime",
            "provider_canary_contract",
            "provider_execution",
        }
        self.assertEqual(
            BubblesArchitectTwin.verified_stage(proofs),
            MaturityStage.PROVIDER_EXECUTED_UNREADBACK,
        )

    def test_deployed_requires_health_persistence_and_rollback(self):
        incomplete = {
            "source",
            "tests",
            "runtime",
            "provider_canary_contract",
            "provider_execution",
            "provider_readback",
            "deployment_receipt",
            "health",
        }
        self.assertEqual(
            BubblesArchitectTwin.verified_stage(incomplete),
            MaturityStage.PROVIDER_VERIFIED,
        )

        complete = incomplete | {"persistence", "rollback"}
        self.assertEqual(
            BubblesArchitectTwin.verified_stage(complete),
            MaturityStage.DEPLOYED,
        )

    def test_portfolio_demonstrable_requires_user_demo_and_case_study(self):
        proofs = {
            "source",
            "tests",
            "runtime",
            "provider_canary_contract",
            "provider_execution",
            "provider_readback",
            "deployment_receipt",
            "health",
            "persistence",
            "rollback",
            "observability",
        }
        self.assertEqual(
            BubblesArchitectTwin.verified_stage(proofs),
            MaturityStage.OPERATIONAL_VERIFIED,
        )

        proofs |= {"user_demo", "case_study"}
        self.assertEqual(
            BubblesArchitectTwin.verified_stage(proofs),
            MaturityStage.PORTFOLIO_DEMONSTRABLE,
        )

    def test_receipt_never_claims_authority_expansion(self):
        twin = BubblesArchitectTwin(
            [
                Project(
                    project_id="X",
                    name="Test",
                    career_value=50,
                    verified_proofs=frozenset({"source"}),
                )
            ]
        )
        receipt = twin.proof_receipt("X", {"source", "tests"})
        self.assertEqual(receipt["authority_ceiling"], "A1_INTERNAL")
        self.assertIn("does not create provider authority", receipt["truth_boundary"])

    def test_seed_portfolio_loads_and_prioritises_cios(self):
        twin = load_twin()
        ranked = twin.rank()
        self.assertEqual(ranked[0].project_id, "CIOS")
        self.assertEqual(
            twin.assess(twin.project("CIOS")).verified_stage,
            MaturityStage.PROVIDER_CANARY_READY,
        )

    def test_caseforge_next_gate_is_runtime_not_provider_execution(self):
        twin = load_twin()
        assessment = twin.assess(twin.project("CASEFORGE"))
        self.assertEqual(assessment.verified_stage, MaturityStage.DETERMINISTIC_TESTED)
        self.assertEqual(assessment.next_gate, "runtime")


if __name__ == "__main__":
    unittest.main()
