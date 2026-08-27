import unittest

import formation_omega


class FormationOmegaPublicAPITests(unittest.TestCase):
    def test_mce_amcf_and_soe_exports_are_public(self):
        expected = {
            "MissionConvergenceEngine",
            "MissionSpec",
            "ClosureLock",
            "ConvergenceLedger",
            "ChangeCapsule",
            "SourceConvergenceClass",
            "classify_convergence",
            "AutonomicMissionFabric",
            "ProofDirectedScheduler",
            "MonotonicClosureGate",
            "CounterfactualPlanner",
            "FailureHorizon",
            "MissionGenome",
            "MissionSwarmPlanner",
            "StrategicObjectiveEcology",
            "MissionGenesisEngine",
            "PortfolioAllocator",
            "CapabilityCentrality",
            "MissionDeduplicator",
            "StrategicGenomeLibrary",
        }
        self.assertTrue(expected.issubset(set(formation_omega.__all__)))
        for name in expected:
            self.assertTrue(hasattr(formation_omega, name), name)

    def test_existing_public_api_is_not_diluted(self):
        existing = {
            "AAAError",
            "AAACycleReport",
            "FormationOmega",
            "ProofState",
            "ReleaseGate",
            "SurfaceReadback",
            "choose_operational_route",
            "resolve_current_truth",
        }
        self.assertTrue(existing.issubset(set(formation_omega.__all__)))
        for name in existing:
            self.assertTrue(hasattr(formation_omega, name), name)


if __name__ == "__main__":
    unittest.main()
