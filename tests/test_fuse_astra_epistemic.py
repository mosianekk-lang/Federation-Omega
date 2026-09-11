import unittest

from fuse_astra_semantic_kernel.causal import CausalImpactGraph
from fuse_astra_semantic_kernel.epistemic import ClaimStatus, EpistemicLedger, Evidence
from fuse_astra_semantic_kernel.experiments import ActiveExperimentPlanner, Experiment, Hypothesis


class EpistemicEngineTests(unittest.TestCase):
    def test_two_independent_strong_sources_can_reach_known(self):
        ledger = EpistemicLedger()
        ledger.add_evidence("claim", Evidence("a", True, 0.9, 0.9, 1.0, "g1"))
        claim = ledger.add_evidence("claim", Evidence("b", True, 0.9, 0.9, 1.0, "g2"))
        self.assertEqual(claim.status, ClaimStatus.KNOWN)

    def test_echoed_sources_do_not_fake_independence(self):
        ledger = EpistemicLedger()
        ledger.add_evidence("claim", Evidence("a", True, 0.95, 0.95, 1.0, "same"))
        claim = ledger.add_evidence("claim", Evidence("b", True, 0.95, 0.95, 1.0, "same"))
        self.assertNotEqual(claim.status, ClaimStatus.KNOWN)

    def test_material_counterevidence_marks_contested(self):
        ledger = EpistemicLedger()
        ledger.add_evidence("claim", Evidence("support", True, 0.9, 0.9, 1.0, "s"))
        claim = ledger.add_evidence("claim", Evidence("oppose", False, 0.9, 0.9, 1.0, "o"))
        self.assertEqual(claim.status, ClaimStatus.CONTESTED)

    def test_expired_evidence_marks_stale(self):
        ledger = EpistemicLedger()
        ledger.add_evidence("claim", Evidence("a", True, 0.9, 0.9, 1.0, "g1"))
        ledger.invalidate_freshness("claim")
        self.assertEqual(ledger.claim("claim").status, ClaimStatus.STALE)


class CausalImpactTests(unittest.TestCase):
    def test_source_change_invalidates_downstream_claims(self):
        graph = CausalImpactGraph()
        graph.add_node("source", "source")
        graph.add_node("summary", "summary")
        graph.add_node("decision", "decision")
        graph.add_node("artifact", "artifact")
        graph.add_dependency("source", "summary")
        graph.add_dependency("summary", "decision")
        graph.add_dependency("decision", "artifact")
        affected = graph.invalidate("source", "provider state changed")
        self.assertEqual(affected, ("source", "summary", "decision", "artifact"))
        self.assertFalse(graph.nodes["artifact"].valid)

    def test_cannot_revalidate_with_invalid_upstream(self):
        graph = CausalImpactGraph()
        graph.add_dependency("source", "claim")
        graph.invalidate("source", "changed")
        with self.assertRaises(RuntimeError):
            graph.revalidate("claim")


class ActiveExperimentTests(unittest.TestCase):
    def test_low_cost_discriminating_experiment_wins(self):
        planner = ActiveExperimentPlanner(
            [Hypothesis("A", 0.6), Hypothesis("B", 0.4)],
            [
                Experiment("cheap", 0.5, 0.1, 100, 0.05, frozenset({"A", "B"})),
                Experiment("expensive", 0.8, 2.0, 100, 0.05, frozenset({"A"})),
            ],
        )
        self.assertEqual(planner.best().experiment_id, "cheap")

    def test_unsafe_experiment_never_enters_ranking(self):
        planner = ActiveExperimentPlanner(
            [Hypothesis("A", 1.0)],
            [
                Experiment("unsafe", 1.0, 0.01, 1, 0.0, frozenset({"A"}), safety_ok=False),
                Experiment("safe", 0.2, 0.5, 100, 0.1, frozenset({"A"})),
            ],
        )
        self.assertEqual(planner.best().experiment_id, "safe")

    def test_irreversibility_is_penalized(self):
        planner = ActiveExperimentPlanner(
            [Hypothesis("A", 1.0)],
            [
                Experiment("reversible", 0.5, 0.2, 100, 0.1, frozenset({"A"}), reversible=True),
                Experiment("irreversible", 0.5, 0.2, 100, 0.1, frozenset({"A"}), reversible=False),
            ],
        )
        self.assertEqual(planner.best().experiment_id, "reversible")


if __name__ == "__main__":
    unittest.main()
