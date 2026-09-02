from __future__ import annotations

from dataclasses import replace
import unittest

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import Prediction, PredictionOutcome
from federation.living_state.edpf_prediction_adapter import (
    OPEN_STATE,
    RESOLVED_FALSE_STATE,
    RESOLVED_TRUE_STATE,
    ProspectiveOutcomeRecord,
    ProspectivePredictionRecord,
    record_prospective_prediction,
    resolve_prospective_prediction,
)
from federation.living_state.model import LivingWorldModel as BaseLivingWorldModel
from federation.living_state.types import FabricError, NodeKind, ProofMaturity, Provenance, WorldNode
from federation.living_state.world_model import LivingWorldModel

NOW = "2026-09-02T14:00:00+00:00"


def prov(
    *,
    source: str = "source",
    proof: str = "proof",
    when: str = "2026-09-02T13:00:00+00:00",
    maturity: ProofMaturity = ProofMaturity.DETERMINISTIC_TESTED,
    scope: str = "GLOBAL",
    source_class: str = "TEST",
) -> Provenance:
    return Provenance(
        source_ref=source,
        proof_ref=proof,
        observed_at=when,
        proof_maturity=maturity,
        ttl_seconds=3600,
        confidence=0.9,
        matter_scope=scope,
        source_class=source_class,
    )


def node(
    state: str,
    *,
    when: str,
    maturity: ProofMaturity = ProofMaturity.DETERMINISTIC_TESTED,
    proof: str,
) -> WorldNode:
    return WorldNode(
        node_id="system:transition-test",
        kind=NodeKind.SYSTEM,
        label="transition-test",
        state=state,
        payload={},
        provenance=prov(when=when, maturity=maturity, proof=proof),
    )


def prediction_record() -> ProspectivePredictionRecord:
    return ProspectivePredictionRecord(
        mission_id="mission-transition-lineage",
        system_source_head_sha="a" * 40,
        mission_snapshot_digest="snapshot:transition-lineage:v1",
        predictor_source_fingerprint="predictor:test:v1",
        predictor_version="test-v1",
        observed_at="2026-09-02T13:00:00+00:00",
        prediction_proof_ref="receipt:prediction:transition-lineage",
        prediction=Prediction(
            prediction_id="prediction-transition-lineage",
            predictor_id="TEST_PREDICTOR",
            domain="living-state",
            event="transition resolves",
            probability=0.8,
            expected_value=0.7,
            expected_latency=0.1,
            expected_owner_burden=0.0,
            evidence_refs=("evidence:pre:1",),
        ),
    )


def outcome_record(*, occurred: bool = True, when: str = "2026-09-02T13:05:00+00:00") -> ProspectiveOutcomeRecord:
    return ProspectiveOutcomeRecord(
        prediction_id="prediction-transition-lineage",
        observed_at=when,
        outcome_source_ref="runtime:transition-lineage",
        proof_maturity=ProofMaturity.RUNTIME_READBACK,
        outcome=PredictionOutcome(
            prediction_id="prediction-transition-lineage",
            occurred=occurred,
            realised_value=1.0 if occurred else 0.0,
            realised_latency=0.1,
            realised_owner_burden=0.0,
            proof_refs=("proof:outcome:transition-lineage",),
        ),
    )


class LivingStateTransitionLineageTests(unittest.TestCase):
    def test_explicit_transition_supersedes_exact_predecessor_without_split_brain(self) -> None:
        model = LivingWorldModel()
        first = node("READY", when="2026-09-02T13:00:00+00:00", proof="p1")
        model.observe_node(first)
        second = node("RESOLVED", when="2026-09-02T13:01:00+00:00", proof="p2")
        event = model.transition_node(second, supersedes_fingerprint=first.fingerprint)
        self.assertEqual("NODE_TRANSITIONED", event.event_type)
        estimate = model.state_estimate(first.node_id, now=NOW)
        self.assertEqual("RESOLVED", estimate.state)
        self.assertFalse(estimate.split_brain)
        self.assertEqual((), estimate.alternatives)
        self.assertEqual(0, model.debt_report(now=NOW)["split_brain_debt"])

    def test_independent_conflicting_observations_still_split_brain(self) -> None:
        model = LivingWorldModel()
        model.observe_node(node("READY", when="2026-09-02T13:00:00+00:00", proof="p1"))
        model.observe_node(node("DOWN", when="2026-09-02T13:01:00+00:00", proof="p2"))
        estimate = model.state_estimate("system:transition-test", now=NOW)
        self.assertTrue(estimate.split_brain)
        self.assertIn("READY", estimate.alternatives)

    def test_branching_transitions_remain_conflicting_with_each_other(self) -> None:
        model = LivingWorldModel()
        first = node("OPEN", when="2026-09-02T13:00:00+00:00", proof="p0")
        model.observe_node(first)
        left = node("RESOLVED_TRUE", when="2026-09-02T13:01:00+00:00", proof="p1")
        right = node("RESOLVED_FALSE", when="2026-09-02T13:02:00+00:00", proof="p2")
        model.transition_node(left, supersedes_fingerprint=first.fingerprint, transition_class="BRANCH_LEFT")
        model.transition_node(right, supersedes_fingerprint=first.fingerprint, transition_class="BRANCH_RIGHT")
        estimate = model.state_estimate(first.node_id, now=NOW)
        self.assertEqual("RESOLVED_FALSE", estimate.state)
        self.assertTrue(estimate.split_brain)
        self.assertIn("RESOLVED_TRUE", estimate.alternatives)
        self.assertNotIn("OPEN", estimate.alternatives)

    def test_transition_rejects_weaker_proof(self) -> None:
        model = LivingWorldModel()
        first = node(
            "READY",
            when="2026-09-02T13:00:00+00:00",
            proof="provider",
            maturity=ProofMaturity.PROVIDER_READBACK,
        )
        model.observe_node(first)
        weak = node(
            "DOWN",
            when="2026-09-02T13:01:00+00:00",
            proof="source",
            maturity=ProofMaturity.SOURCE_READBACK,
        )
        with self.assertRaisesRegex(FabricError, "weaker proof"):
            model.transition_node(weak, supersedes_fingerprint=first.fingerprint)

    def test_transition_rejects_time_reversal(self) -> None:
        model = LivingWorldModel()
        first = node("READY", when="2026-09-02T13:05:00+00:00", proof="p1")
        model.observe_node(first)
        earlier = node("DOWN", when="2026-09-02T13:04:00+00:00", proof="p2")
        with self.assertRaisesRegex(FabricError, "later than predecessor"):
            model.transition_node(earlier, supersedes_fingerprint=first.fingerprint)

    def test_transition_journal_replays_with_exact_digest_and_lineage(self) -> None:
        model = LivingWorldModel()
        first = node("READY", when="2026-09-02T13:00:00+00:00", proof="p1")
        second = node("RESOLVED", when="2026-09-02T13:01:00+00:00", proof="p2")
        model.observe_node(first)
        model.transition_node(second, supersedes_fingerprint=first.fingerprint)
        replayed = LivingWorldModel.replay(model.export_event_log())
        self.assertTrue(replayed.verify_event_chain())
        self.assertEqual(model.event_head_digest, replayed.event_head_digest)
        self.assertFalse(replayed.state_estimate(first.node_id, now=NOW).split_brain)

    def test_old_observation_journal_is_not_retroactively_reclassified(self) -> None:
        old = BaseLivingWorldModel()
        old.observe_node(node("READY", when="2026-09-02T13:00:00+00:00", proof="p1"))
        old.observe_node(node("DOWN", when="2026-09-02T13:01:00+00:00", proof="p2"))
        replayed = LivingWorldModel.replay(old.export_event_log())
        self.assertEqual(old.event_head_digest, replayed.event_head_digest)
        self.assertTrue(replayed.state_estimate("system:transition-test", now=NOW).split_brain)
        self.assertTrue(all(event["event_type"] == "NODE_OBSERVED" for event in replayed.export_event_log()))

    def test_edpf_open_to_resolved_is_transition_not_split_brain(self) -> None:
        model = LivingWorldModel()
        first_event = record_prospective_prediction(model, prediction_record())
        second_event = resolve_prospective_prediction(model, outcome_record())
        self.assertEqual("NODE_OBSERVED", first_event.event_type)
        self.assertEqual("NODE_TRANSITIONED", second_event.event_type)
        current = next(iter(model.current_nodes().values()))
        self.assertEqual(RESOLVED_TRUE_STATE, current.state)
        estimate = model.state_estimate(current.node_id, now="2026-09-02T13:05:01+00:00")
        self.assertFalse(estimate.split_brain)
        self.assertNotIn(current.node_id, model.split_brain_nodes(now="2026-09-02T13:05:01+00:00"))
        self.assertFalse(any(item["signal"] == "SPLIT_BRAIN" for item in model.reflexes(now="2026-09-02T13:05:01+00:00")))
        self.assertEqual(0, model.debt_report(now="2026-09-02T13:05:01+00:00")["split_brain_debt"])

    def test_edpf_false_resolution_uses_same_lifecycle_transition(self) -> None:
        model = LivingWorldModel()
        record_prospective_prediction(model, prediction_record())
        resolve_prospective_prediction(model, outcome_record(occurred=False))
        current = next(iter(model.current_nodes().values()))
        self.assertEqual(RESOLVED_FALSE_STATE, current.state)
        self.assertFalse(model.state_estimate(current.node_id, now="2026-09-02T13:05:01+00:00").split_brain)


if __name__ == "__main__":
    unittest.main()
