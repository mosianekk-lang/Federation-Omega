import unittest

from formation_omega.autonomic_fabric import ActionCandidate, AuthorityCeiling
from sol_61_runtime.repair import AutonomousRepairFabric
from federation.sentinel_omega.repair_binding import (
    ProviderAuthorityEvidence,
    RepairBindingState,
    RepairRunbook,
    RepairRunbookRegistry,
    SentinelRepairBinder,
)


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


class RepairRunbookRegistryTests(unittest.TestCase):
    def test_conflicting_runbook_identity_fails_closed(self):
        registry = RepairRunbookRegistry((internal_runbook(),))
        changed = RepairRunbook(**{**internal_runbook().__dict__, "change_set": ("different",)})
        with self.assertRaisesRegex(ValueError, "conflicting"):
            registry.register(changed)

    def test_match_requires_capability_coverage(self):
        registry = RepairRunbookRegistry((internal_runbook(),))
        self.assertEqual(len(registry.match(incident_class="PRODUCER_STALE", required_capabilities=("heartbeat",))), 1)
        self.assertEqual(len(registry.match(incident_class="PRODUCER_STALE", required_capabilities=("unknown",))), 0)


class SentinelRepairBinderTests(unittest.TestCase):
    def setUp(self):
        self.binder = SentinelRepairBinder()

    def test_a1_action_binds_to_existing_sol61_repair_candidate(self):
        plan = self.binder.bind(action(), incident_class="PRODUCER_STALE", registry=RepairRunbookRegistry((internal_runbook(),)))
        self.assertEqual(plan.state, RepairBindingState.BOUND_INTERNAL_PROOF_REQUIRED)
        self.assertIsNotNone(plan.repair_candidate)
        self.assertFalse(plan.provider_execution_authorized)
        self.assertFalse(plan.provider_execution_performed)
        self.assertIn("runbook:refresh", plan.proof_refs)

    def test_bound_candidate_runs_through_existing_sol61_promotion_gates(self):
        plan = self.binder.bind(action(), incident_class="PRODUCER_STALE", registry=RepairRunbookRegistry((internal_runbook(),)))
        candidate = plan.repair_candidate
        self.assertIsNotNone(candidate)
        fabric = AutonomousRepairFabric()
        shadow = fabric.shadow_execute(candidate, lambda _: {"passed": True})
        differential = fabric.differential_validate({"freshness": 0.0}, {"freshness": 1.0}, {"freshness": 1.0})
        rollback = fabric.rehearse_rollback(candidate, lambda steps: bool(steps))
        canary = fabric.canary_validate({"freshness": 1.0}, {"freshness": ("GTE", 1.0)})
        receipt = fabric.evaluate_promotion(
            candidate,
            shadow=shadow,
            differential=differential,
            rollback=rollback,
            canary=canary,
            proposer="sentinel",
            executor="patch",
            certifier="jarvis",
        )
        self.assertEqual(receipt.state, "PROMOTION_ELIGIBLE")

    def test_no_matching_runbook_holds_without_invention(self):
        plan = self.binder.bind(action(caps=("unknown",)), incident_class="PRODUCER_STALE", registry=RepairRunbookRegistry((internal_runbook(),)))
        self.assertEqual(plan.state, RepairBindingState.HELD_NO_MATCHING_RUNBOOK)
        self.assertIsNone(plan.repair_candidate)

    def test_a3_action_is_owner_reserved(self):
        plan = self.binder.bind(action(authority=AuthorityCeiling.A3_CONSEQUENTIAL), incident_class="PRODUCER_STALE", registry=RepairRunbookRegistry((internal_runbook(),)))
        self.assertEqual(plan.state, RepairBindingState.HELD_OWNER_RESERVED)
        self.assertIsNone(plan.repair_candidate)

    def test_a2_external_repair_requires_complete_provider_authority(self):
        external_action = action(authority=AuthorityCeiling.A2_BOUNDED_EFFECT, external=True, caps=("worker",))
        registry = RepairRunbookRegistry((provider_runbook(),))
        held = self.binder.bind(external_action, incident_class="WORKER_STALE", registry=registry)
        self.assertEqual(held.state, RepairBindingState.HELD_AUTHORITY_EVIDENCE)
        self.assertFalse(held.provider_execution_authorized)

        plan = self.binder.bind(external_action, incident_class="WORKER_STALE", registry=registry, provider_authority=provider_evidence())
        self.assertEqual(plan.state, RepairBindingState.BOUND_PROVIDER_EXECUTION_REQUIRED)
        self.assertTrue(plan.provider_execution_authorized)
        self.assertFalse(plan.provider_execution_performed)
        self.assertTrue(plan.semantic_readback_required)

    def test_provider_executor_mismatch_fails_closed(self):
        plan = self.binder.bind(
            action(authority=AuthorityCeiling.A2_BOUNDED_EFFECT, external=True, caps=("worker",)),
            incident_class="WORKER_STALE",
            registry=RepairRunbookRegistry((provider_runbook(),)),
            provider_authority=provider_evidence(executor_ref="executor:wrong"),
        )
        self.assertEqual(plan.state, RepairBindingState.HELD_AUTHORITY_EVIDENCE)
        self.assertEqual(plan.hold_reason, "PROVIDER_EXECUTOR_MISMATCH")

    def test_external_effect_cannot_bind_to_internal_runbook(self):
        external = action(authority=AuthorityCeiling.A2_BOUNDED_EFFECT, external=True)
        plan = self.binder.bind(external, incident_class="PRODUCER_STALE", registry=RepairRunbookRegistry((internal_runbook(),)), provider_authority=provider_evidence())
        self.assertEqual(plan.state, RepairBindingState.HELD_AUTHORITY_EVIDENCE)

    def test_action_without_evidence_fails_closed(self):
        bad = ActionCandidate(
            action_id="bad", objective="bad", closure_leverage=0.5, information_gain=0.5,
            success_probability=0.5, reversibility=1.0, cost=0.0, risk=0.0, latency=0.0,
            required_capabilities=("heartbeat",), evidence_refs=(),
        )
        with self.assertRaisesRegex(ValueError, "evidence_refs"):
            self.binder.bind(bad, incident_class="PRODUCER_STALE", registry=RepairRunbookRegistry((internal_runbook(),)))


if __name__ == "__main__":
    unittest.main()
