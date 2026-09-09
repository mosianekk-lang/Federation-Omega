from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping

from benchmarking.cfbe_omega.mission_execution_kernel_vnext.core import (
    ActionDecision,
    ActionProposal,
    MissionExecutionKernel,
)
from federation.fuse_mission_runtime_interlock_v1 import (
    MissionRuntimeDecision,
    MissionRuntimeInterlock,
    MissionRuntimeSnapshot,
    RuntimeAction,
)
from sol_61_runtime.sol_62 import ExecutionIntent, ProofEnvelope, Sol62Runtime, digest


SCHEMA = "SOL62-FUSE-BRIDGE-V2"
VERSION = "2.0.0"


class BridgeError(RuntimeError):
    pass


class EffectClass(str, Enum):
    READ_ONLY = "READ_ONLY"
    CONSEQUENTIAL_EFFECT = "CONSEQUENTIAL_EFFECT"


_READ_ONLY_OPERATIONS = frozenset(
    {
        "read",
        "get",
        "list",
        "describe",
        "status",
        "verify",
        "validate",
        "inspect",
        "query",
        "search",
        "check",
        "probe",
        "simulate",
        "plan",
    }
)
_EFFECT_TOKENS = (
    "write",
    "create",
    "update",
    "delete",
    "send",
    "publish",
    "merge",
    "deploy",
    "grant",
    "revoke",
    "mutate",
    "execute",
    "invoke",
    "upload",
    "post",
    "put",
    "patch",
)


def classify_effect(action: ActionProposal) -> EffectClass:
    """Independent, default-deny effect classification.

    Caller-supplied ``effectful=False`` is never enough to classify a route as
    read-only. Unknown or effect-shaped operations are consequential.
    """
    action.validate()
    if action.effectful:
        return EffectClass.CONSEQUENTIAL_EFFECT
    operation = action.operation_key.strip().casefold()
    resource = action.resource_key.strip().casefold()
    if any(token in operation or token in resource for token in _EFFECT_TOKENS):
        return EffectClass.CONSEQUENTIAL_EFFECT
    if operation in _READ_ONLY_OPERATIONS:
        return EffectClass.READ_ONLY
    return EffectClass.CONSEQUENTIAL_EFFECT


@dataclass(frozen=True, slots=True)
class Sol62BridgeBinding:
    transition_id: str
    effect_id: str
    provider: str
    payload: Mapping[str, Any]
    semantics: str
    idempotency_key: str
    actor: str
    worker: str
    source_version: str
    expected_readback: Mapping[str, Any]
    satisfied_constraints: tuple[str, ...] = ()
    fence_ttl_seconds: int = 120

    def validate(self) -> None:
        required = (
            self.transition_id,
            self.effect_id,
            self.provider,
            self.semantics,
            self.idempotency_key,
            self.actor,
            self.worker,
            self.source_version,
        )
        if not all(str(value).strip() for value in required):
            raise BridgeError("BRIDGE_BINDING_REQUIRED_FIELD_MISSING")
        if not self.expected_readback:
            raise BridgeError("BRIDGE_EXPECTED_READBACK_REQUIRED")
        if self.fence_ttl_seconds <= 0:
            raise BridgeError("BRIDGE_FENCE_TTL_INVALID")


@dataclass(frozen=True, slots=True)
class ProviderObservation:
    provider_ref: str
    readback: Mapping[str, Any]

    @classmethod
    def from_value(cls, value: Any) -> "ProviderObservation":
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise BridgeError("BRIDGE_PROVIDER_OBSERVATION_REQUIRED")
        return cls(
            provider_ref=str(value.get("provider_ref", "")).strip(),
            readback=dict(value.get("readback", {}) or {}),
        )


@dataclass(frozen=True, slots=True)
class BridgeReceipt:
    schema: str
    version: str
    mission_id: str
    action_id: str
    transition_id: str
    effect_id: str
    effect_class: str
    formation_action_sha256: str
    interlock_receipt_digest: str
    sol_event_hash: str
    proof_id: str
    provider_ref: str
    state: str
    receipt_sha256: str


class Sol62FuseBridgeV2:
    """Zero-dilution FUSE→Formation→SOL 6.2 bridge for no-effect/read-only work.

    This adapter creates no authority. Formation owns the action permit, SOL 6.2
    owns transactional execution/proof state, and the F130 interlock owns
    continuation/terminality. Provider-effect execution remains outside this
    bridge and requires its own provider authority/readback route.
    """

    def __init__(
        self,
        *,
        formation: MissionExecutionKernel,
        runtime: Sol62Runtime,
        interlock: MissionRuntimeInterlock | None = None,
    ) -> None:
        self.formation = formation
        self.runtime = runtime
        self.interlock = interlock or MissionRuntimeInterlock()

    def _transition(self, binding: Sol62BridgeBinding) -> Mapping[str, Any]:
        row = self.runtime.control.get_state("sol62.transition", binding.transition_id)
        if not row:
            raise BridgeError("BRIDGE_SOL62_TRANSITION_NOT_REGISTERED")
        return row["value"]

    def preflight(
        self,
        *,
        snapshot: MissionRuntimeSnapshot,
        action: ActionProposal,
        binding: Sol62BridgeBinding,
        now_epoch: float,
    ) -> MissionRuntimeDecision:
        action.validate()
        binding.validate()
        if snapshot.mission_id != snapshot.current_mission_id:
            raise BridgeError("BRIDGE_FUSE_CURRENT_MISSION_MISMATCH")
        if action.mission_id != snapshot.mission_id:
            raise BridgeError("BRIDGE_FORMATION_FUSE_MISSION_MISMATCH")
        if int(action.mission_version) != int(snapshot.contract_epoch):
            raise BridgeError("BRIDGE_MISSION_EPOCH_MISMATCH")
        if classify_effect(action) is not EffectClass.READ_ONLY:
            raise BridgeError("BRIDGE_EFFECT_CLASS_HELD")

        formation_decision = self.formation.decide_action(action)
        if formation_decision.decision is not ActionDecision.EXECUTE or not formation_decision.authorized:
            raise BridgeError("BRIDGE_FORMATION_ACTION_NOT_AUTHORIZED")

        interlock_decision = self.interlock.decide(snapshot, now_epoch=now_epoch)
        if interlock_decision.action is not RuntimeAction.DISPATCH_TASK:
            raise BridgeError("BRIDGE_F130_DID_NOT_AUTHORIZE_DISPATCH")
        if interlock_decision.next_task_id != action.action_id:
            raise BridgeError("BRIDGE_F130_SELECTED_DIFFERENT_TASK")

        transition = self._transition(binding)
        if str(transition.get("mission_id")) != action.mission_id:
            raise BridgeError("BRIDGE_SOL62_MISSION_MISMATCH")
        if str(transition.get("operation", "")).casefold() != action.operation_key.casefold():
            raise BridgeError("BRIDGE_SOL62_OPERATION_MISMATCH")
        if str(transition.get("target")) != action.resource_key:
            raise BridgeError("BRIDGE_SOL62_TARGET_MISMATCH")
        if bool(transition.get("consequential")):
            raise BridgeError("BRIDGE_SOL62_CONSEQUENTIAL_TRANSITION_HELD")
        if str(transition.get("source_version")) != binding.source_version:
            raise BridgeError("BRIDGE_SOL62_SOURCE_VERSION_MISMATCH")

        ready = self.runtime.ready_transitions(
            action.mission_id,
            satisfied_constraints=set(binding.satisfied_constraints),
        )
        if binding.transition_id not in ready:
            raise BridgeError("BRIDGE_SOL62_TRANSITION_NOT_READY")
        return interlock_decision

    def _mark_uncertain(self, effect_id: str, error: Exception) -> None:
        row = self.runtime.control.db.execute(
            "SELECT state FROM effects WHERE effect_id=?", (effect_id,)
        ).fetchone()
        if not row:
            return
        state = str(row["state"])
        if state not in {"DISPATCHING", "DISPATCHED"}:
            return
        try:
            self.runtime.control.transition_effect(
                effect_id,
                expected_state=state,
                next_state="FAILED_UNCERTAIN",
                result={"bridge_error": error.__class__.__name__},
            )
        except Exception:
            return

    def execute_read_only(
        self,
        *,
        snapshot: MissionRuntimeSnapshot,
        action: ActionProposal,
        permit: str,
        binding: Sol62BridgeBinding,
        gateway_request: Mapping[str, Any],
        identity_claims: Mapping[str, Any],
        now_epoch: int,
        handler: Callable[[], Any],
    ) -> BridgeReceipt:
        interlock_decision = self.preflight(
            snapshot=snapshot,
            action=action,
            binding=binding,
            now_epoch=float(now_epoch),
        )

        # The permit is consumed only after all non-mutating preflight gates pass.
        # A mission revision/cancellation makes this call fail closed.
        self.formation.consume_permit(permit, action)

        transition = self._transition(binding)
        proof_id = f"FUSEV2-{binding.effect_id}"
        intent = ExecutionIntent(
            effect_id=binding.effect_id,
            transition_id=binding.transition_id,
            provider=binding.provider,
            payload=dict(binding.payload),
            semantics=binding.semantics,
            idempotency_key=binding.idempotency_key,
            actor=binding.actor,
            source_version=binding.source_version,
            expected_readback=dict(binding.expected_readback),
            rollback_required=False,
        )
        self.runtime.prepare_execution(
            intent,
            gateway_request=dict(gateway_request),
            identity_claims=dict(identity_claims),
            now_epoch=now_epoch,
        )
        fence = self.runtime.acquire_execution_fence(
            binding.transition_id,
            binding.worker,
            ttl_seconds=binding.fence_ttl_seconds,
            now_epoch=now_epoch,
        )
        self.runtime.authorize_dispatch(
            binding.effect_id,
            authority_lease_id=None,
            actor=binding.actor,
            source_version=binding.source_version,
            now_epoch=now_epoch,
            worker=binding.worker,
            lease_epoch=int(fence["epoch"]),
            fencing_token=int(fence["fencing_token"]),
        )

        try:
            observation = ProviderObservation.from_value(handler())
        except Exception as exc:
            self._mark_uncertain(binding.effect_id, exc)
            raise
        if not observation.provider_ref:
            error = BridgeError("BRIDGE_PROVIDER_REFERENCE_REQUIRED")
            self._mark_uncertain(binding.effect_id, error)
            raise error

        self.runtime.mark_dispatched(binding.effect_id, provider_ref=observation.provider_ref)
        observed = self.runtime.observe_effect(binding.effect_id, readback=dict(observation.readback))
        if not observed.get("match"):
            raise BridgeError("BRIDGE_PROVIDER_READBACK_MISMATCH")

        evidence = {
            "provider_ref": observation.provider_ref,
            "readback": dict(observation.readback),
            "formation_action_sha256": action.action_sha256,
            "interlock_receipt_digest": interlock_decision.receipt_digest,
            "binding": {
                "transition_id": binding.transition_id,
                "effect_id": binding.effect_id,
                "source_version": binding.source_version,
            },
        }
        proof = ProofEnvelope.from_evidence(
            proof_id=proof_id,
            subject=f"transition:{binding.transition_id}",
            target=str(transition["target"]),
            operation=str(transition["operation"]),
            issuer="sol62-fuse-v2-bridge",
            source_version=binding.source_version,
            evidence=evidence,
            max_age_seconds=600,
            evidence_class="DETERMINISTIC",
        )
        expected = dict(binding.expected_readback)
        self.runtime.register_verified_proof(
            proof,
            evidence,
            semantic_verifier=lambda _p, value: (
                value.get("provider_ref") == observation.provider_ref
                and value.get("readback") == expected
                and value.get("formation_action_sha256") == action.action_sha256
                and value.get("interlock_receipt_digest") == interlock_decision.receipt_digest
            ),
            now_epoch=now_epoch,
        )
        committed = self.runtime.verify_effect_and_commit(
            binding.effect_id,
            proof_ids=(proof_id,),
            now_epoch=now_epoch,
            satisfied_constraints=set(binding.satisfied_constraints),
        )
        event_hash = str(committed.get("event_hash", ""))
        body = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": action.mission_id,
            "action_id": action.action_id,
            "transition_id": binding.transition_id,
            "effect_id": binding.effect_id,
            "effect_class": EffectClass.READ_ONLY.value,
            "formation_action_sha256": action.action_sha256,
            "interlock_receipt_digest": interlock_decision.receipt_digest,
            "sol_event_hash": event_hash,
            "proof_id": proof_id,
            "provider_ref": observation.provider_ref,
            "state": "VERIFIED_REALITY",
        }
        return BridgeReceipt(**body, receipt_sha256=digest(body))

    def finalize(
        self,
        snapshot: MissionRuntimeSnapshot,
        *,
        now_epoch: float,
    ) -> MissionRuntimeDecision:
        decision = self.interlock.decide(snapshot, now_epoch=now_epoch)
        if decision.action is not RuntimeAction.PREPARE_TERMINAL or decision.prepare is None:
            raise BridgeError("BRIDGE_F130_TERMINAL_PREPARE_REQUIRED")
        committed = self.interlock.commit_terminal(snapshot, decision.prepare, now_epoch=now_epoch)
        if committed.action is not RuntimeAction.COMPLETE_VERIFIED:
            raise BridgeError("BRIDGE_F130_TERMINAL_COMMIT_FAILED")
        return committed
