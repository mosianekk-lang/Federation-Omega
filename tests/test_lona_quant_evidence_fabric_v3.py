import unittest

from federation.lona_quant_node.fabric_v3.evidence import EvidenceReceipt, verify_chain
from federation.lona_quant_node.fabric_v3.mutation import FailureSignature, materially_changed, propose_from_failure
from federation.lona_quant_node.fabric_v3.queue import Experiment, ExperimentState, deduplicate
from federation.lona_quant_node.fabric_v3.tournament import Candidate, eligible_for_backtest, validate_tournament
from federation.lona_quant_node.fabric_v3.walkforward import build_survival_battery, expanding_walk_forward


class QuantEvidenceFabricV3Tests(unittest.TestCase):
    def test_queue_never_equates_dispatch_with_verified_evidence(self):
        item = Experiment("e1", "fp1", ExperimentState.PLANNED)
        item = item.transition(ExperimentState.DISPATCHED)
        self.assertEqual(item.state, ExperimentState.DISPATCHED)
        with self.assertRaises(ValueError):
            item.transition(ExperimentState.RESEARCH_ADMITTED)

    def test_evidence_transition_requires_reference(self):
        item = Experiment("e1", "fp1", ExperimentState.PLANNED)
        item = item.transition(ExperimentState.DISPATCHED)
        item = item.transition(ExperimentState.COMPLETED_UNVERIFIED)
        with self.assertRaises(ValueError):
            item.transition(ExperimentState.EVIDENCE_VERIFIED)

    def test_duplicate_fingerprints_are_not_dispatched_twice(self):
        a = Experiment("a", "same", ExperimentState.PLANNED)
        b = Experiment("b", "same", ExperimentState.PLANNED)
        self.assertEqual(deduplicate([a, b]), [a])

    def test_hash_chain_detects_reordering_or_missing_links(self):
        first = EvidenceReceipt("e1", "DISPATCHED", {"report_id": "r1"})
        second = EvidenceReceipt("e1", "COMPLETED", {"report_id": "r1"}, previous_hash=first.receipt_hash())
        self.assertTrue(verify_chain([first, second]))
        self.assertFalse(verify_chain([second, first]))

    def test_provider_failure_is_valid_evidence_not_candidate(self):
        candidates = (
            Candidate("openai", "j1", "COMPLETED", "s1", "h1", 8),
            Candidate("xai", "j2", "FAILED", failure="API key missing"),
        )
        validate_tournament(candidates, {"openai", "xai"})
        self.assertTrue(eligible_for_backtest(candidates[0]))
        self.assertFalse(eligible_for_backtest(candidates[1]))

    def test_completed_provider_without_code_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_tournament((Candidate("google", "j1", "COMPLETED", "s1", None, 9),), {"google"})

    def test_walk_forward_has_separate_train_and_holdout_windows(self):
        windows = expanding_walk_forward()
        self.assertTrue(any(w.role == "TRAIN" for w in windows))
        self.assertTrue(any(w.role == "HOLDOUT" for w in windows))
        self.assertTrue(all(w.start_date <= w.end_date for w in windows))

    def test_survival_battery_spans_assets_windows_parameters_and_costs(self):
        cases = build_survival_battery(assets=("SPY", "QQQ", "IWM"), base_parameters={"fast": 20, "slow": 50})
        self.assertEqual(len(cases), 3 * 4 * 3 * 2)
        self.assertEqual({c.asset for c in cases}, {"SPY", "QQQ", "IWM"})

    def test_failure_win_mutation_is_causally_derived_and_material(self):
        sig = FailureSignature(
            parent_strategy_id="parent",
            evidence_ref="receipt",
            failures=("HOLDOUT_SAMPLE_TOO_SMALL", "MATERIAL_BENCHMARK_UNDERPERFORMANCE", "CROSS_ASSET_GENERALISATION_FAILURE"),
        )
        proposal = propose_from_failure(sig)
        self.assertEqual(set(proposal.changed_dimensions), {"entry_exit_frequency", "trend_participation", "regime_adaptation"})
        self.assertTrue(materially_changed({"a": 1}, {"a": 2}))
        self.assertFalse(materially_changed({"a": 1}, {"a": 1}))


if __name__ == "__main__":
    unittest.main()
