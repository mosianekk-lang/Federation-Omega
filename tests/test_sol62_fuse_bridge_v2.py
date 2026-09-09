from __future__ import annotations

import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from benchmarking.cfbe_omega.mission_execution_kernel_vnext.core import (
    ActionProposal,
    CFBEKernelError,
    FruitCriterion,
    MissionConstraints,
    MissionContract,
    MissionExecutionKernel,
    Requirement,
)
from federation.fuse_mission_runtime_interlock_v1 import (
    MissionRuntimeSnapshot,
    ProofBinding,
    RuntimeTask,
    RuntimeTaskState,
)
from federation.sol62_fuse_bridge_v2 import (
    BridgeError,
    EffectClass,
    ProviderObservation,
    Sol62BridgeBinding,
    Sol62FuseBridgeV2,
    classify_effect,
)
from sol_61_runtime.sol_62 import (
    GatewayPolicy,
    MissionSpec,
    Sol62Runtime,
    TransitionSpec,
    WorkloadIdentityPolicy,
)


class Sol62FuseBridgeV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.formation = MissionExecutionKernel(root / "formation.sqlite3")
        contract = MissionContract.create(
            mission_id="FUSEV2-M1",
            mission_version=1,
            owner_outcome="Complete one verified read only FUSE bridge mission",
            terminal_fruit=(FruitCriterion("FRUIT1", "Read only owner outcome is independently verified"),),
            requirements=(Requirement("R1", "Execute one bounded read only bridge action"),),
            constraints=MissionConstraints(
                authorized_classes=("A0", "A1"),
                maximum_cost=0,
                zero_new_recurring_cost=True,
                maximum_user_burden=0,
                external_effects_allowed=False,
            ),
            critical_path=("R1",),
        )
        self.formation.open_mission(contract)
        self.runtime = Sol62Runtime(
            root / "sol62",
            gateway_policy=GatewayPolicy("sol-gateway", "sol-6.2"),
            identity_policy=WorkloadIdentityPolicy(
                allowed_issuers={"https://token.actions.githubusercontent.com"},
                audience="sol-runtime",
                subject_prefix="repo:mosianekk-lang/Federation-Omega:",
                max_ttl_seconds=600,
            ),
        )
        self.bridge = Sol62FuseBridgeV2(formation=self.formation, runtime=self.runtime)
        self.now = int(time.time())
        self.action = ActionProposal(
            action_id="READ1",
            mission_id="FUSEV2-M1",
            mission_version=1,
            requirement_ids=("R1",),
            authority_class="A1",
            expected_outcome_delta=1.0,
            effectful=False,
            resource_key="local/status",
            operation_key="read",
        )
        self.proof_id = "FUSEV2-effect-1"
        requirement = {
            "proof_id": self.proof_id,
            "subject": "transition:TX1",
            "target": "local/status",
            "operation": "read",
            "source_version": "source-v1",
            "accepted_evidence_classes": ["DETERMINISTIC"],
        }
        self.runtime.register_mission(
            MissionSpec(
                "FUSEV2-M1",
                "Complete one verified read only FUSE bridge mission",
                {"state": "READY"},
                {"state": "DONE"},
                success_proofs=(requirement,),
            )
        )
        self.runtime.register_transition(
            TransitionSpec(
                "TX1",
                "FUSEV2-M1",
                "read",
                "local/status",
                {"state": "READY"},
                {"state": "DONE"},
                required_proofs=(requirement,),
                source_version="source-v1",
            )
        )
        self.binding = Sol62BridgeBinding(
            transition_id="TX1",
            effect_id="effect-1",
            provider="local-read-adapter",
            payload={"query": "status"},
            semantics="IDEMPOTENT",
            idempotency_key="fusev2-idem-1",
            actor="fuse-v2-worker",
            worker="fuse-v2-worker",
            source_version="source-v1",
            expected_readback={"status": "ok"},
        )

    def tearDown(self) -> None:
        self.runtime.close()
        self.tmp.cleanup()

    def snapshot(self, **overrides) -> MissionRuntimeSnapshot:
        body = dict(
            mission_id="FUSEV2-M1",
            current_mission_id="FUSEV2-M1",
            objective="Complete one verified read only FUSE bridge mission",
            contract_epoch=1,
            ledger_tail=1,
            tasks=(RuntimeTask("READ1", RuntimeTaskState.READY, priority=100),),
        )
        body.update(overrides)
        return MissionRuntimeSnapshot(**body)

    def claims(self) -> dict:
        return {
            "iss": "https://token.actions.githubusercontent.com",
            "aud": "sol-runtime",
            "sub": "repo:mosianekk-lang/Federation-Omega:ref:refs/heads/main",
            "iat": self.now - 10,
            "exp": self.now + 300,
            "credential_type": "oidc",
        }

    @staticmethod
    def gateway() -> dict:
        return {
            "runtime_id": "sol-6.2",
            "via_gateway": "sol-gateway",
            "authenticated_principal": "spiffe://fuse/v2-worker",
            "policy_version": "6.2",
        }

    def permit(self, action: ActionProposal | None = None) -> str:
        return self.formation.issue_permit(action or self.action)

    def execute(self, *, observation=None, action=None, binding=None, permit=None):
        return self.bridge.execute_read_only(
            snapshot=self.snapshot(),
            action=action or self.action,
            permit=permit or self.permit(action),
            binding=binding or self.binding,
            gateway_request=self.gateway(),
            identity_claims=self.claims(),
            now_epoch=self.now,
            handler=lambda: observation
            or ProviderObservation("local-provider-ref", {"status": "ok"}),
        )

    def test_real_formation_f130_sol62_read_only_transition_verifies(self) -> None:
        receipt = self.execute()
        self.assertEqual("VERIFIED_REALITY", receipt.state)
        self.assertEqual(EffectClass.READ_ONLY.value, receipt.effect_class)
        self.assertEqual(self.action.action_sha256, receipt.formation_action_sha256)
        self.assertTrue(receipt.sol_event_hash)
        self.assertEqual(self.proof_id, receipt.proof_id)
        self.assertTrue(self.runtime.verify_integrity()["event_chain_valid"])

    def test_f130_terminal_prepare_and_commit_closes_only_after_proof(self) -> None:
        receipt = self.execute()
        done = self.snapshot(
            ledger_tail=2,
            tasks=(RuntimeTask("READ1", RuntimeTaskState.DONE, required_proof_ids=(receipt.proof_id,)),),
            proofs=(ProofBinding(
                proof_id=receipt.proof_id,
                task_id="READ1",
                dependency="SOL62_EVENT",
                bound_epoch=receipt.sol_event_hash,
                current_epoch=receipt.sol_event_hash,
            ),),
            objective_satisfied=True,
        )
        terminal = self.bridge.finalize(done, now_epoch=float(self.now))
        self.assertTrue(terminal.completion_verified)
        self.assertTrue(terminal.final_response_allowed)

    def test_effect_spoof_is_blocked_even_when_action_says_not_effectful(self) -> None:
        action = ActionProposal(
            action_id="READ1",
            mission_id="FUSEV2-M1",
            mission_version=1,
            requirement_ids=("R1",),
            authority_class="A1",
            expected_outcome_delta=1.0,
            effectful=False,
            resource_key="mailbox/outbound",
            operation_key="send_email",
        )
        called = []
        permit = self.permit(action)
        with self.assertRaisesRegex(BridgeError, "EFFECT_CLASS_HELD"):
            self.bridge.execute_read_only(
                snapshot=self.snapshot(),
                action=action,
                permit=permit,
                binding=self.binding,
                gateway_request=self.gateway(),
                identity_claims=self.claims(),
                now_epoch=self.now,
                handler=lambda: called.append(True),
            )
        self.assertEqual([], called)

    def test_unknown_operation_defaults_to_consequential(self) -> None:
        action = ActionProposal(
            action_id="READ1",
            mission_id="FUSEV2-M1",
            mission_version=1,
            requirement_ids=("R1",),
            authority_class="A1",
            expected_outcome_delta=1.0,
            effectful=False,
            resource_key="local/status",
            operation_key="mystery",
        )
        self.assertEqual(EffectClass.CONSEQUENTIAL_EFFECT, classify_effect(action))

    def test_forged_permit_is_rejected_before_handler(self) -> None:
        with self.assertRaises(CFBEKernelError):
            self.bridge.execute_read_only(
                snapshot=self.snapshot(),
                action=self.action,
                permit="forged-permit",
                binding=self.binding,
                gateway_request=self.gateway(),
                identity_claims=self.claims(),
                now_epoch=self.now,
                handler=lambda: ProviderObservation("should-not-run", {"status": "ok"}),
            )

    def test_consumed_formation_permit_cannot_be_reused(self) -> None:
        permit = self.permit()
        self.execute(permit=permit)
        with self.assertRaisesRegex(CFBEKernelError, "PERMIT_ALREADY_CONSUMED"):
            self.formation.consume_permit(permit, self.action)

    def test_formation_cancellation_invalidates_outstanding_permit(self) -> None:
        permit = self.permit()
        self.formation.cancel_mission("FUSEV2-M1", "owner mission cancelled")
        with self.assertRaisesRegex(BridgeError, "FORMATION_ACTION_NOT_AUTHORIZED"):
            self.bridge.execute_read_only(
                snapshot=self.snapshot(),
                action=self.action,
                permit=permit,
                binding=self.binding,
                gateway_request=self.gateway(),
                identity_claims=self.claims(),
                now_epoch=self.now,
                handler=lambda: ProviderObservation("should-not-run", {"status": "ok"}),
            )

    def test_source_drift_is_rejected_before_permit_consumption(self) -> None:
        binding = replace(self.binding, source_version="drifted")
        permit = self.permit()
        with self.assertRaisesRegex(BridgeError, "SOURCE_VERSION_MISMATCH"):
            self.bridge.execute_read_only(
                snapshot=self.snapshot(),
                action=self.action,
                permit=permit,
                binding=binding,
                gateway_request=self.gateway(),
                identity_claims=self.claims(),
                now_epoch=self.now,
                handler=lambda: ProviderObservation("should-not-run", {"status": "ok"}),
            )
        self.formation.consume_permit(permit, self.action)

    def test_provider_readback_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(BridgeError, "PROVIDER_READBACK_MISMATCH"):
            self.execute(observation=ProviderObservation("provider-ref", {"status": "wrong"}))
        state = self.runtime.control.db.execute(
            "SELECT state FROM effects WHERE effect_id='effect-1'"
        ).fetchone()["state"]
        self.assertEqual("FAILED_UNCERTAIN", state)

    def test_handler_exception_marks_effect_uncertain(self) -> None:
        permit = self.permit()
        with self.assertRaisesRegex(ValueError, "boom"):
            self.bridge.execute_read_only(
                snapshot=self.snapshot(),
                action=self.action,
                permit=permit,
                binding=self.binding,
                gateway_request=self.gateway(),
                identity_claims=self.claims(),
                now_epoch=self.now,
                handler=lambda: (_ for _ in ()).throw(ValueError("boom")),
            )
        state = self.runtime.control.db.execute(
            "SELECT state FROM effects WHERE effect_id='effect-1'"
        ).fetchone()["state"]
        self.assertEqual("FAILED_UNCERTAIN", state)

    def test_f130_cannot_be_bypassed_when_another_task_has_priority(self) -> None:
        snapshot = self.snapshot(
            tasks=(
                RuntimeTask("OTHER", RuntimeTaskState.READY, priority=200),
                RuntimeTask("READ1", RuntimeTaskState.READY, priority=100),
            )
        )
        with self.assertRaisesRegex(BridgeError, "F130_SELECTED_DIFFERENT_TASK"):
            self.bridge.preflight(
                snapshot=snapshot,
                action=self.action,
                binding=self.binding,
                now_epoch=float(self.now),
            )

    def test_stale_f130_proof_blocks_terminal_commit(self) -> None:
        receipt = self.execute()
        stale = self.snapshot(
            ledger_tail=2,
            tasks=(RuntimeTask("READ1", RuntimeTaskState.DONE, required_proof_ids=(receipt.proof_id,)),),
            proofs=(ProofBinding(
                proof_id=receipt.proof_id,
                task_id="READ1",
                dependency="SOL62_EVENT",
                bound_epoch=receipt.sol_event_hash,
                current_epoch="changed",
            ),),
            objective_satisfied=True,
        )
        with self.assertRaisesRegex(BridgeError, "TERMINAL_PREPARE_REQUIRED"):
            self.bridge.finalize(stale, now_epoch=float(self.now))

    def test_mission_epoch_mismatch_blocks_preflight(self) -> None:
        with self.assertRaisesRegex(BridgeError, "MISSION_EPOCH_MISMATCH"):
            self.bridge.preflight(
                snapshot=self.snapshot(contract_epoch=2),
                action=self.action,
                binding=self.binding,
                now_epoch=float(self.now),
            )


if __name__ == "__main__":
    unittest.main()
