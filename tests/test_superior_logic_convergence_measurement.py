import unittest

from federation.bubbles_hyperperformance import (
    CurrentStateLease,
    CurrentStateLeaseError,
    IdempotencyEnvelope,
    IdempotencyLedger,
    TraceEvent,
    TraceSpine,
)
from federation.bubbles_tool_payload_firewall import (
    ToolPayloadFirewall,
    ToolPayloadObservation,
)
from federation.superior_logic_convergence_measurement import (
    CONSTITUTIONAL_CORE,
    MissionOracle,
    ObservationMode,
    ProfileObservation,
    aggregate_campaign,
    compare_pair,
    compile_control_slice,
    default_mission_oracles,
    full_control_universe,
    truth_boundary,
)


class SuperiorLogicConvergenceMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.oracles = default_mission_oracles()
        self.universe = full_control_universe(self.oracles)

    def observation(
        self,
        oracle,
        *,
        profile,
        mode=ObservationMode.SYNTHETIC,
        controls=None,
        context_chars=15_000,
        tool_round_trips=5,
        owner_interventions=0,
        stale_state_rejected=True,
        duplicate_suppressed=True,
        trace_complete=True,
        proof_refs=(),
    ):
        return ProfileObservation(
            profile=profile,
            mission_id=oracle.mission_id,
            mode=mode,
            active_controls=frozenset(controls if controls is not None else oracle.required_controls),
            context_chars=context_chars,
            tool_round_trips=tool_round_trips,
            owner_interventions=owner_interventions,
            stale_state_rejected=stale_state_rejected,
            duplicate_suppressed=duplicate_suppressed,
            trace_complete=trace_complete,
            proof_refs=proof_refs,
        )

    def pair(self, oracle, *, mode=ObservationMode.SYNTHETIC, suffix=""):
        refs = (f"proof:{oracle.mission_id}:{suffix or 'run'}",) if mode == ObservationMode.OBSERVED else ()
        baseline = self.observation(
            oracle,
            profile="FULL_DOCTRINE",
            mode=mode,
            controls=self.universe,
            context_chars=170_807,
            tool_round_trips=12,
            owner_interventions=1,
            proof_refs=refs,
        )
        candidate = self.observation(
            oracle,
            profile="COMPILED_CORE_CAPSULE",
            mode=mode,
            controls=compile_control_slice(oracle),
            context_chars=15_000,
            tool_round_trips=5,
            owner_interventions=0,
            proof_refs=refs,
        )
        return compare_pair(oracle, baseline, candidate)

    def test_default_corpus_covers_eight_distinct_mission_classes(self):
        self.assertEqual(len(self.oracles), 8)
        self.assertEqual(len({oracle.mission_id for oracle in self.oracles}), 8)
        self.assertTrue(CONSTITUTIONAL_CORE.issubset(self.universe))

    def test_compiled_slice_contains_every_oracle_requirement(self):
        for oracle in self.oracles:
            compiled = compile_control_slice(oracle)
            self.assertTrue(oracle.required_controls.issubset(compiled))
            self.assertTrue(CONSTITUTIONAL_CORE.issubset(compiled))

    def test_missing_critical_control_holds_pair(self):
        oracle = next(item for item in self.oracles if item.mission_id == "PROVIDER_EFFECT")
        baseline = self.observation(
            oracle,
            profile="FULL_DOCTRINE",
            controls=self.universe,
            context_chars=170_807,
            tool_round_trips=12,
            owner_interventions=1,
        )
        missing = set(compile_control_slice(oracle))
        missing.remove("SOVARA.EFFECT.GATE")
        candidate = self.observation(
            oracle,
            profile="COMPILED_BAD",
            controls=missing,
            context_chars=12_000,
            tool_round_trips=4,
            owner_interventions=0,
        )
        result = compare_pair(oracle, baseline, candidate)
        self.assertFalse(result.structural_pass)
        self.assertIn("SOVARA.EFFECT.GATE", result.candidate_missing_controls)
        self.assertEqual(result.truth_state, "PAIR_HOLD")

    def test_behavioral_guard_failure_holds_pair(self):
        oracle = next(item for item in self.oracles if item.mission_id == "CURRENT_STATE_READ")
        baseline = self.observation(
            oracle,
            profile="FULL_DOCTRINE",
            controls=self.universe,
            context_chars=170_807,
            tool_round_trips=12,
            owner_interventions=1,
        )
        candidate = self.observation(
            oracle,
            profile="COMPILED_BAD",
            controls=compile_control_slice(oracle),
            context_chars=12_000,
            tool_round_trips=4,
            owner_interventions=0,
            stale_state_rejected=False,
        )
        result = compare_pair(oracle, baseline, candidate)
        self.assertFalse(result.structural_pass)
        self.assertIn("STALE_STATE_REJECTION", result.candidate_behavior_failures)

    def test_observed_profiles_require_proof_refs(self):
        oracle = self.oracles[0]
        with self.assertRaises(ValueError):
            self.observation(
                oracle,
                profile="OBSERVED_WITHOUT_PROOF",
                mode=ObservationMode.OBSERVED,
                proof_refs=(),
            )

    def test_synthetic_campaign_can_reach_structural_not_empirical_candidate(self):
        pairs = [self.pair(oracle) for oracle in self.oracles]
        campaign = aggregate_campaign(pairs)
        self.assertTrue(campaign.structural_candidate)
        self.assertFalse(campaign.empirical_value_candidate)
        self.assertFalse(campaign.stable_promotion_allowed)
        self.assertEqual(campaign.truth_state, "STRUCTURAL_CANDIDATE")
        self.assertGreater(campaign.median_context_reduction, 0.9)

    def test_thirty_observed_pairs_can_reach_empirical_value_candidate_only(self):
        pairs = []
        for index in range(30):
            oracle = self.oracles[index % len(self.oracles)]
            pairs.append(self.pair(oracle, mode=ObservationMode.OBSERVED, suffix=str(index)))
        campaign = aggregate_campaign(pairs)
        self.assertTrue(campaign.structural_candidate)
        self.assertTrue(campaign.empirical_value_candidate)
        self.assertFalse(campaign.stable_promotion_allowed)
        self.assertEqual(campaign.observed_pair_count, 30)
        self.assertEqual(campaign.truth_state, "EMPIRICAL_VALUE_CANDIDATE")

    def test_insufficient_context_reduction_holds_pair(self):
        oracle = self.oracles[0]
        baseline = self.observation(
            oracle,
            profile="FULL_DOCTRINE",
            controls=self.universe,
            context_chars=170_807,
            tool_round_trips=12,
            owner_interventions=1,
        )
        candidate = self.observation(
            oracle,
            profile="COMPILED_TOO_LARGE",
            controls=compile_control_slice(oracle),
            context_chars=60_000,
            tool_round_trips=5,
            owner_interventions=0,
        )
        result = compare_pair(oracle, baseline, candidate)
        self.assertFalse(result.structural_pass)

    def test_current_state_lease_fixture_rejects_stale_projection(self):
        lease = CurrentStateLease(
            entity_id="SLOS",
            field_id="stable_version",
            value="0.7.0",
            authority_source="release:SLOS:stable",
            observed_at="2026-08-30T19:00:00+02:00",
            fresh_until="2026-08-30T19:30:00+02:00",
            proof_refs=("proof:stable",),
            source_event_id="evt-stable",
        )
        with self.assertRaises(CurrentStateLeaseError):
            lease.require_fresh(now="2026-08-30T20:00:00+02:00")

    def test_idempotency_fixture_suppresses_duplicate_effect(self):
        ledger = IdempotencyLedger()
        envelope = IdempotencyEnvelope(
            operation_id="op-1",
            command_sha256="a" * 64,
            target_alias="TARGET",
            action_scope="WRITE_ONE",
            effect_class="A1_INTERNAL",
            expires_at="2026-08-30T22:00:00+02:00",
        )
        first = ledger.admit(envelope, now="2026-08-30T21:00:00+02:00")
        self.assertTrue(first.execute)
        ledger.record_result("op-1", "receipt:1")
        replay = ledger.admit(envelope, now="2026-08-30T21:01:00+02:00")
        self.assertFalse(replay.execute)
        self.assertEqual(replay.state, "REPLAY_SAME_RESULT")

    def test_trace_fixture_preserves_lineage_without_payload(self):
        trace = TraceSpine()
        first = trace.append(
            TraceEvent(
                trace_id="trace-1",
                span_id="span-1",
                mission_id="mission-1",
                stage="MISSION_LOCK",
                state="PASS",
                occurred_at="2026-08-30T21:00:00+02:00",
                proof_refs=("proof:mission",),
            )
        )
        second = trace.append(
            TraceEvent(
                trace_id="trace-1",
                span_id="span-2",
                parent_span_id="span-1",
                mission_id="mission-1",
                stage="READBACK",
                state="PASS",
                occurred_at="2026-08-30T21:01:00+02:00",
                proof_refs=("proof:readback",),
            )
        )
        self.assertEqual(first.event_count, 1)
        self.assertEqual(second.event_count, 2)
        self.assertEqual(len(trace.snapshot()), 2)

    def test_payload_firewall_fixture_rejects_oversize_raw_log(self):
        decision = ToolPayloadFirewall().evaluate(
            ToolPayloadObservation(
                tool_name="github.workflow.logs",
                payload_chars=50_000,
                line_count=900,
                content_kind="workflow_log",
            )
        )
        self.assertFalse(decision.admit_raw)
        self.assertTrue(decision.diagnostic_required)

    def test_truth_boundary_never_promotes_measurement_into_stable_or_provider_claim(self):
        boundary = truth_boundary()
        self.assertTrue(boundary)
        self.assertTrue(all(value is False for value in boundary.values()))

    def test_oracle_rejects_critical_control_outside_requirements(self):
        with self.assertRaises(ValueError):
            MissionOracle(
                mission_id="BAD",
                required_controls=frozenset({"A"}),
                critical_controls=frozenset({"B"}),
            )


if __name__ == "__main__":
    unittest.main()
