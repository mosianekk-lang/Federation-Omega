from __future__ import annotations

import unittest

from federation.action_admission_gate_v1 import (
    ActionAdmissionGate,
    ActionAdmissionState,
    ActionRequest,
    AuthorityGrant,
)
from federation.cfbe_chat_hyperperformance_v1 import EffectClass
from federation.execution_topology_compiler_v1 import (
    ExecutionTopologyReceipt,
    TopologyMode,
    WorkerAssignment,
)
from federation.mission_ir import MissionIR

NOW = "2026-09-06T22:40:00+02:00"


def mission(
    effect: str,
    *,
    rollback: bool = True,
    owner_approval: bool = False,
    authority: tuple[str, ...] = (),
    allow: tuple[str, ...] = (),
    deny: tuple[str, ...] = (),
) -> MissionIR:
    return MissionIR(
        mission_id="mission-action-1",
        objective="admit exact action",
        domain="FEDERATION",
        outcome_contract="proof-bounded action admission",
        source_frontier="signed-main",
        privacy_class="P1_INTERNAL",
        rights_state="OWNER_AUTHORIZED",
        effect_class=effect,
        owner_approval_required=owner_approval,
        rollback_required=rollback,
        authority_requirements=authority,
        proof_requirements=("action_admission_receipt",),
        provider_allowlist=allow,
        provider_denylist=deny,
    )


def topology(m: MissionIR, *, executable: bool = True, domain: str = "repo:main") -> ExecutionTopologyReceipt:
    state = "TOPOLOGY_READY_SINGLE_WORKER" if executable else "TOPOLOGY_HELD_NO_LIVE_CAPACITY"
    return ExecutionTopologyReceipt(
        mission_id=m.mission_id,
        mission_digest=m.digest(),
        admission_receipt_digest="sha256:admission",
        state=state,
        mode=TopologyMode.SINGLE_WORKER if executable else TopologyMode.NONE,
        assignments=(
            WorkerAssignment(
                unit_id="u1",
                worker_id="w1",
                runtime_id="runtime-1",
                capability_id="CAP_A",
                mutation_domain=domain,
                cfbe_state="READY",
            ),
        ) if executable else (),
        waves=(),
        blocked_units=() if executable else ("u1",),
        live_worker_ids=("w1",) if executable else (),
        cfbe_plan_id="cfbe_plan_1" if executable else "",
        receipt_digest="sha256:topology",
    )


def request(effect: EffectClass, *, provider: str = "") -> ActionRequest:
    return ActionRequest(
        action_id="action-1",
        unit_id="u1",
        effect_class=effect,
        target_scope="repo:main",
        mutation_domain="" if effect is EffectClass.READ_ONLY else "repo:main",
        provider=provider,
    )


def grant(
    effect: EffectClass,
    *,
    expires_at: str = "2026-09-06T23:30:00+02:00",
    action_id: str = "action-1",
    target_scope: str = "repo:main",
    authority_refs: tuple[str, ...] = ("AUTH_WRITE",),
    provider_identity_ref: str = "",
    owner_approval_ref: str = "",
    current_state_ref: str = "provider:current-state",
    readback_contract_ref: str = "provider:readback-contract",
    rollback_plan_ref: str = "provider:rollback-plan",
    idempotency_key: str = "idem-1",
    revoked: bool = False,
) -> AuthorityGrant:
    return AuthorityGrant(
        grant_id="grant-1",
        mission_id="mission-action-1",
        action_id=action_id,
        effect_class=effect,
        target_scope=target_scope,
        source_ref="authority:grant-readback",
        observed_at="2026-09-06T22:30:00+02:00",
        expires_at=expires_at,
        authority_refs=authority_refs,
        provider_identity_ref=provider_identity_ref,
        owner_approval_ref=owner_approval_ref,
        current_state_ref=current_state_ref,
        readback_contract_ref=readback_contract_ref,
        rollback_plan_ref=rollback_plan_ref,
        idempotency_key=idempotency_key,
        revoked=revoked,
    )


class ActionAdmissionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = ActionAdmissionGate()

    def test_read_only_action_can_be_admitted_without_mutation_grant(self) -> None:
        m = mission("READ_ONLY", rollback=False)
        result = self.gate.admit(
            mission=m,
            topology=topology(m, domain=""),
            request=request(EffectClass.READ_ONLY),
            now=NOW,
        )
        self.assertTrue(result.admitted)
        self.assertEqual(ActionAdmissionState.ADMITTED, result.state)

    def test_ready_topology_does_not_authorize_internal_write(self) -> None:
        m = mission("BOUNDED_EFFECT", authority=("AUTH_WRITE",))
        result = self.gate.admit(
            mission=m,
            topology=topology(m),
            request=request(EffectClass.INTERNAL_WRITE),
            now=NOW,
        )
        self.assertFalse(result.admitted)
        self.assertIn("MUTATING_ACTION_AUTHORITY_REQUIRED", result.reasons)

    def test_internal_write_requires_current_exact_grant_and_contracts(self) -> None:
        m = mission("BOUNDED_EFFECT", authority=("AUTH_WRITE",))
        result = self.gate.admit(
            mission=m,
            topology=topology(m),
            request=request(EffectClass.INTERNAL_WRITE),
            grant=grant(EffectClass.INTERNAL_WRITE),
            now=NOW,
        )
        self.assertTrue(result.admitted)
        self.assertEqual("w1", result.worker_id)
        self.assertEqual("runtime-1", result.runtime_id)

    def test_stale_or_revoked_grant_fails_closed(self) -> None:
        m = mission("BOUNDED_EFFECT", authority=("AUTH_WRITE",))
        stale = grant(EffectClass.INTERNAL_WRITE, expires_at="2026-09-06T22:35:00+02:00")
        revoked = grant(EffectClass.INTERNAL_WRITE, revoked=True)
        for item in (stale, revoked):
            result = self.gate.admit(
                mission=m,
                topology=topology(m),
                request=request(EffectClass.INTERNAL_WRITE),
                grant=item,
                now=NOW,
            )
            self.assertFalse(result.admitted)
            self.assertIn("ACTION_AUTHORITY_NOT_CURRENT", result.reasons)

    def test_grant_is_action_and_target_specific(self) -> None:
        m = mission("BOUNDED_EFFECT", authority=("AUTH_WRITE",))
        for item, expected in (
            (grant(EffectClass.INTERNAL_WRITE, action_id="other"), "ACTION_AUTHORITY_ACTION_MISMATCH"),
            (grant(EffectClass.INTERNAL_WRITE, target_scope="repo:other"), "ACTION_AUTHORITY_TARGET_MISMATCH"),
        ):
            result = self.gate.admit(
                mission=m,
                topology=topology(m),
                request=request(EffectClass.INTERNAL_WRITE),
                grant=item,
                now=NOW,
            )
            self.assertFalse(result.admitted)
            self.assertIn(expected, result.reasons)

    def test_mutation_requires_currentness_readback_rollback_and_idempotency(self) -> None:
        m = mission("BOUNDED_EFFECT", authority=("AUTH_WRITE",))
        cases = (
            (grant(EffectClass.INTERNAL_WRITE, current_state_ref=""), "MUTATING_ACTION_CURRENT_STATE_PROOF_REQUIRED"),
            (grant(EffectClass.INTERNAL_WRITE, readback_contract_ref=""), "MUTATING_ACTION_READBACK_CONTRACT_REQUIRED"),
            (grant(EffectClass.INTERNAL_WRITE, rollback_plan_ref=""), "MISSION_REQUIRES_ROLLBACK_PLAN"),
            (grant(EffectClass.INTERNAL_WRITE, idempotency_key=""), "MUTATING_ACTION_IDEMPOTENCY_KEY_REQUIRED"),
        )
        for item, expected in cases:
            result = self.gate.admit(
                mission=m,
                topology=topology(m),
                request=request(EffectClass.INTERNAL_WRITE),
                grant=item,
                now=NOW,
            )
            self.assertFalse(result.admitted)
            self.assertIn(expected, result.reasons)

    def test_mission_effect_ceiling_blocks_external_effect_under_bounded_mission(self) -> None:
        m = mission("BOUNDED_EFFECT", authority=("AUTH_EXT",), allow=("github",))
        result = self.gate.admit(
            mission=m,
            topology=topology(m),
            request=request(EffectClass.EXTERNAL_EFFECT, provider="github"),
            grant=grant(
                EffectClass.EXTERNAL_EFFECT,
                authority_refs=("AUTH_EXT",),
                provider_identity_ref="provider:github-identity",
            ),
            provider_readiness={"github": True},
            now=NOW,
        )
        self.assertFalse(result.admitted)
        self.assertIn("MISSION_EFFECT_CEILING_EXCEEDED", result.reasons)

    def test_external_effect_requires_provider_identity_owner_approval_and_readiness(self) -> None:
        m = mission(
            "CONSEQUENTIAL_EFFECT",
            authority=("AUTH_EXT",),
            owner_approval=True,
            allow=("github",),
        )
        incomplete = grant(EffectClass.EXTERNAL_EFFECT, authority_refs=("AUTH_EXT",))
        result = self.gate.admit(
            mission=m,
            topology=topology(m),
            request=request(EffectClass.EXTERNAL_EFFECT, provider="github"),
            grant=incomplete,
            provider_readiness={"github": False},
            now=NOW,
        )
        self.assertFalse(result.admitted)
        self.assertIn("EXTERNAL_ACTION_PROVIDER_IDENTITY_REQUIRED", result.reasons)
        self.assertIn("MISSION_REQUIRES_OWNER_APPROVAL", result.reasons)
        self.assertIn("PROVIDER_READINESS_NOT_PROVEN", result.reasons)

    def test_fully_proven_external_effect_can_be_admitted_without_executing_it(self) -> None:
        m = mission(
            "CONSEQUENTIAL_EFFECT",
            authority=("AUTH_EXT",),
            owner_approval=True,
            allow=("github",),
        )
        result = self.gate.admit(
            mission=m,
            topology=topology(m),
            request=request(EffectClass.EXTERNAL_EFFECT, provider="github"),
            grant=grant(
                EffectClass.EXTERNAL_EFFECT,
                authority_refs=("AUTH_EXT",),
                provider_identity_ref="provider:github-identity",
                owner_approval_ref="owner:approval-receipt",
            ),
            provider_readiness={"github": True},
            now=NOW,
        )
        self.assertTrue(result.admitted)
        self.assertEqual("grant-1", result.authority_grant_id)

    def test_provider_allow_and_deny_policy_fail_closed(self) -> None:
        m = mission(
            "CONSEQUENTIAL_EFFECT",
            authority=("AUTH_EXT",),
            allow=("github",),
            deny=("blocked-provider",),
        )
        result = self.gate.admit(
            mission=m,
            topology=topology(m),
            request=request(EffectClass.EXTERNAL_EFFECT, provider="other"),
            grant=grant(
                EffectClass.EXTERNAL_EFFECT,
                authority_refs=("AUTH_EXT",),
                provider_identity_ref="provider:identity",
            ),
            provider_readiness={"other": True},
            now=NOW,
        )
        self.assertFalse(result.admitted)
        self.assertIn("PROVIDER_NOT_ALLOWLISTED", result.reasons)

    def test_missing_topology_assignment_blocks_any_action(self) -> None:
        m = mission("READ_ONLY", rollback=False)
        held = topology(m, executable=False)
        result = self.gate.admit(
            mission=m,
            topology=held,
            request=request(EffectClass.READ_ONLY),
            now=NOW,
        )
        self.assertFalse(result.admitted)
        self.assertIn("TOPOLOGY_NOT_EXECUTABLE", result.reasons)
        self.assertIn("TOPOLOGY_ASSIGNMENT_NOT_FOUND", result.reasons)


if __name__ == "__main__":
    unittest.main()
