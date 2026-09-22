import unittest

from formation_omega.autonomic_fabric import ActionCandidate, AuthorityCeiling
from sol_61_runtime.repair import AutonomousRepairFabric
from federation.sentinel_omega.market_leader_convergence import (
    EventOrchestrationEngine,
    EventOrchestrationRule,
    IncidentContext,
    MarketLeaderRepairConvergence,
    OrchestrationAction,
    RepairWorkStage,
)
from federation.sentinel_omega.repair_binding import (
    ProviderAuthorityEvidence,
    RepairBindingState,
    RepairRunbook,
    RepairRunbookRegistry,
    SentinelRepairBinder,
)


def incident(**overrides):
    values = dict(
        incident_id="inc-db-regression",
        incident_class="PRODUCER_STALE",
        severity=4,
        confidence=0.88,
        probable_origin_ref="change:db-17",
        affected_entities=("api", "db"),
        customer_impact=0.7,
        business_impact=0.6,
        blast_radius=5,
        recent_change_refs=("change:db-17",),
        trace_refs=("trace:123",),
        proof_refs=("proof:incident", "proof:topology"),
    )
    values.update(overrides)
    return IncidentContext(**values)


def action(*, authority=AuthorityCeiling.A1_INTERNAL, external=False, caps=("heartbeat",)):
    return ActionCandidate(
        action_id="repair-heartbeat",
        objective="Restore stale producer heartbeat",
        closure_leverage=0.9,
        information_gain=0.8,
        success_probability=0.9,
        reversibility=1.0,
        cost=0.0,
        risk=0.1,
        latency=0.1,
        authority_ceiling=authority,
        external_effect=external,
        required_capabilities=caps,
        evidence_refs=("snapshot:stale", "source:heartbeat"),
    )


def internal_runbook():
    return RepairRunbook(
        runbook_id="refresh-control-heartbeat",
        incident_class="PRODUCER_STALE",
        change_set=("append-current-control-heartbeat",),
        rollback_steps=("preserve-prior-row-and-stop-new-projection",),
        expected_effects={"freshness": 1.0},
        max_authority=AuthorityCeiling.A1_INTERNAL,
        required_capabilities=("heartbeat", "sheets"),
        proof_refs=("runbook:refresh",),
    )


def provider_runbook():
    return RepairRunbook(
        runbook_id="restart-existing-worker",
        incident_class="WORKER_STALE",
        change_set=("restart-existing-worker",),
        rollback_steps=("restore-previous-worker-revision",),
        expected_effects={"availability": 0.5},
        max_authority=AuthorityCeiling.A2_BOUNDED_EFFECT,
        external_effect=True,
        required_capabilities=("worker",),
        proof_refs=("runbook:worker",),
        provider_executor_ref="executor:worker",
        semantic_readback_ref="readback:health",
        rollback_ref="rollback:revision",
    )


def provider_evidence(**overrides):
    values = dict(
        authority_ref="authority:a2",
        executor_ref="executor:worker",
        target_ref="worker:exact",
        semantic_readback_ref="readback:health",
        rollback_ref="rollback:revision",
        current=True,
        action_authorized=True,
        exact_target=True,
        reversible=True,
        no_new_spend=True,
        no_iam_change=True,
        no_credential_change=True,
        proof_refs=("provider:authority", "provider:target"),
    )
    values.update(overrides)
    return ProviderAuthorityEvidence(**values)


def repair_rule(**overrides):
    values = dict(
        rule_id="repair-high-impact",
        priority=100,
        action=OrchestrationAction.BIND_REPAIR,
        incident_classes=("PRODUCER_STALE",),
        minimum_severity=3,
        minimum_confidence=0.7,
        minimum_impact_priority=0.4,
        require_probable_origin=True,
        require_change_or_trace_anchor=True,
    )
    values.update(overrides)
    return EventOrchestrationRule(**values)


class EventOrchestrationTests(unittest.TestCase):
    def test_impact_priority_increases_with_user_and_business_impact(self):
        low = incident(customer_impact=0.0, business_impact=0.0, blast_radius=0)
        high = incident(customer_impact=1.0, business_impact=1.0, blast_radius=20)
        self.assertGreater(high.impact_priority, low.impact_priority)

    def test_rules_are_priority_ordered_and_first_match_is_deterministic(self):
        engine = EventOrchestrationEngine((
            repair_rule(rule_id="lower", priority=50, action=OrchestrationAction.PREWARM_DIAGNOSTICS),
            repair_rule(rule_id="higher", priority=100),
        ))
        decision = engine.decide(incident())
        self.assertEqual(decision.rule_id, "higher")
        self.assertEqual(decision.action, OrchestrationAction.BIND_REPAIR)

    def test_duplicate_rule_identity_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            EventOrchestrationEngine((repair_rule(), repair_rule()))

    def test_missing_anchor_does_not_trigger_repair(self):
        engine = EventOrchestrationEngine((repair_rule(),))
        decision = engine.decide(incident(probable_origin_ref=None, recent_change_refs=(), trace_refs=()))
        self.assertEqual(decision.action, OrchestrationAction.OBSERVE)


class RepairBindingTests(unittest.TestCase):
    def test_a1_action_binds_to_existing_sol_repair_candidate(self):
        plan = SentinelRepairBinder().bind(
            action(), incident_class="PRODUCER_STALE", registry=RepairRunbookRegistry((internal_runbook(),))
        )
        self.assertEqual(plan.state, RepairBindingState.BOUND_INTERNAL_PROOF_REQUIRED)
        self.assertIsNotNone(plan.repair_candidate)
        self.assertFalse(plan.provider_execution_performed)

    def test_bound_candidate_uses_existing_sol61_promotion_gates(self):
        plan = SentinelRepairBinder().bind(
            action(), incident_class="PRODUCER_STALE", registry=RepairRunbookRegistry((internal_runbook(),))
        )
        candidate = plan.repair_candidate
        self.assertIsNotNone(candidate)
        fabric = AutonomousRepairFabric()
        receipt = fabric.evaluate_promotion(
            candidate,
            shadow=fabric.shadow_execute(candidate, lambda _: {"passed": True}),
            differential=fabric.differential_validate({"freshness": 0.0}, {"freshness": 1.0}, {"freshness": 1.0}),
            rollback=fabric.rehearse_rollback(candidate, lambda steps: bool(steps)),
            canary=fabric.canary_validate({"freshness": 1.0}, {"freshness": ("GTE", 1.0)}),
            proposer="sentinel",
            executor="patch",
            certifier="jarvis",
        )
        self.assertEqual(receipt.state, "PROMOTION_ELIGIBLE")

    def test_no_matching_runbook_holds_instead_of_inventing_effect(self):
        plan = SentinelRepairBinder().bind(
            action(caps=("unknown",)), incident_class="PRODUCER_STALE", registry=RepairRunbookRegistry((internal_runbook(),))
        )
        self.assertEqual(plan.state, RepairBindingState.HELD_NO_MATCHING_RUNBOOK)
        self.assertIsNone(plan.repair_candidate)

    def test_a3_is_owner_reserved(self):
        plan = SentinelRepairBinder().bind(
            action(authority=AuthorityCeiling.A3_CONSEQUENTIAL),
            incident_class="PRODUCER_STALE",
            registry=RepairRunbookRegistry((internal_runbook(),)),
        )
        self.assertEqual(plan.state, RepairBindingState.HELD_OWNER_RESERVED)

    def test_a2_provider_execution_requires_exact_current_authority(self):
        external = action(authority=AuthorityCeiling.A2_BOUNDED_EFFECT, external=True, caps=("worker",))
        registry = RepairRunbookRegistry((provider_runbook(),))
        held = SentinelRepairBinder().bind(external, incident_class="WORKER_STALE", registry=registry)
        self.assertEqual(held.state, RepairBindingState.HELD_AUTHORITY_EVIDENCE)
        allowed = SentinelRepairBinder().bind(
            external, incident_class="WORKER_STALE", registry=registry, provider_authority=provider_evidence()
        )
        self.assertEqual(allowed.state, RepairBindingState.BOUND_PROVIDER_EXECUTION_REQUIRED)
        self.assertTrue(allowed.provider_execution_authorized)
        self.assertFalse(allowed.provider_execution_performed)

    def test_provider_mismatch_fails_closed(self):
        plan = SentinelRepairBinder().bind(
            action(authority=AuthorityCeiling.A2_BOUNDED_EFFECT, external=True, caps=("worker",)),
            incident_class="WORKER_STALE",
            registry=RepairRunbookRegistry((provider_runbook(),)),
            provider_authority=provider_evidence(executor_ref="executor:wrong"),
        )
        self.assertEqual(plan.hold_reason, "PROVIDER_EXECUTOR_MISMATCH")


class MarketLeaderConvergenceTests(unittest.TestCase):
    def test_high_impact_incident_compiles_repair_work_packet_without_execution(self):
        fabric = MarketLeaderRepairConvergence((repair_rule(),))
        packet = fabric.route(
            incident(), action_candidate=action(), registry=RepairRunbookRegistry((internal_runbook(),))
        )
        self.assertEqual(packet.stage, RepairWorkStage.REPAIR_PROOF_REQUIRED)
        self.assertIsNotNone(packet.repair_plan)
        self.assertFalse(packet.external_effect_performed)
        self.assertIn("change:db-17", packet.change_refs)
        self.assertIn("trace:123", packet.trace_refs)

    def test_observe_path_never_manufactures_repair(self):
        fabric = MarketLeaderRepairConvergence((repair_rule(),))
        packet = fabric.route(
            incident(severity=1), action_candidate=None, registry=RepairRunbookRegistry((internal_runbook(),))
        )
        self.assertEqual(packet.stage, RepairWorkStage.ROOT_CAUSE_CANDIDATE)
        self.assertIsNone(packet.repair_plan)
        self.assertFalse(packet.external_effect_performed)

    def test_external_packet_remains_execution_required(self):
        rule = repair_rule(incident_classes=("WORKER_STALE",))
        fabric = MarketLeaderRepairConvergence((rule,))
        packet = fabric.route(
            incident(incident_class="WORKER_STALE"),
            action_candidate=action(authority=AuthorityCeiling.A2_BOUNDED_EFFECT, external=True, caps=("worker",)),
            registry=RepairRunbookRegistry((provider_runbook(),)),
            provider_authority=provider_evidence(),
        )
        self.assertEqual(packet.stage, RepairWorkStage.PROVIDER_EXECUTION_REQUIRED)
        self.assertTrue(packet.repair_plan.provider_execution_authorized)
        self.assertFalse(packet.external_effect_performed)
        self.assertFalse(packet.repair_plan.provider_execution_performed)


if __name__ == "__main__":
    unittest.main()
