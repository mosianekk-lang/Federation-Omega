from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable, Mapping, Sequence

from federation.fuse_serving_kernel_v1 import EffectReceipt, ServingLaneSpec
from federation.mission_ir import MissionIR
from sol_61_runtime.sol_62_runtime import ExecutionIntent, Sol62Runtime


@dataclass(frozen=True, slots=True)
class Sol62LaneBinding:
    """Binds one FUSE lane to an already-registered SOL 6.2 transition.

    Registration remains outside this adapter so the domain owner controls the
    exact mission/transition contract. This adapter only executes a pre-existing
    SOL transition and cannot widen its authority, target or source version.
    """

    transition_id: str
    effect_id: str
    provider: str
    payload: Mapping[str, Any]
    semantics: str
    idempotency_key: str
    actor: str
    worker: str
    source_version: str
    authority_lease_id: str | None = None
    simulation_proof_id: str | None = None
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
        if not all(str(item).strip() for item in required):
            raise ValueError("FUSE_SOL62_BINDING_REQUIRED_FIELD_MISSING")
        if self.fence_ttl_seconds <= 0:
            raise ValueError("FUSE_SOL62_FENCE_TTL_INVALID")


@dataclass(frozen=True, slots=True)
class ProviderEffectObservation:
    provider_ref: str
    readback: Mapping[str, Any]
    proof_ids: tuple[str, ...] = ()
    proof_refs: tuple[str, ...] = ()
    proof_axes: tuple[str, ...] = ()

    @classmethod
    def from_value(cls, value: Any) -> "ProviderEffectObservation":
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("FUSE_SOL62_HANDLER_MUST_RETURN_PROVIDER_OBSERVATION")
        return cls(
            provider_ref=str(value.get("provider_ref", "")).strip(),
            readback=dict(value.get("readback", {}) or {}),
            proof_ids=tuple(str(x).strip() for x in value.get("proof_ids", ()) if str(x).strip()),
            proof_refs=tuple(str(x).strip() for x in value.get("proof_refs", ()) if str(x).strip()),
            proof_axes=tuple(str(x).strip() for x in value.get("proof_axes", ()) if str(x).strip()),
        )


class Sol62EffectExecutorV1:
    """Executes FUSE effect lanes through the admitted SOL 6.2 transaction spine.

    The adapter deliberately does not register missions/transitions or create
    authority leases. It requires those contracts to exist before execution.
    Provider calls occur only after gateway/identity admission, durable intent
    preparation, an execution fence and SOL dispatch authorization.
    """

    version = "1.0.0"

    def __init__(
        self,
        runtime: Sol62Runtime,
        *,
        bindings: Mapping[str, Sol62LaneBinding],
        gateway_request_factory: Callable[[MissionIR, ServingLaneSpec], Mapping[str, Any]],
        identity_claims_factory: Callable[[MissionIR, ServingLaneSpec], Mapping[str, Any]],
        now_epoch: Callable[[], int] | None = None,
    ) -> None:
        self.runtime = runtime
        self.bindings = dict(bindings)
        self.gateway_request_factory = gateway_request_factory
        self.identity_claims_factory = identity_claims_factory
        self.now_epoch = now_epoch or (lambda: int(time.time()))
        for binding in self.bindings.values():
            binding.validate()

    def _binding(self, lane: ServingLaneSpec) -> Sol62LaneBinding:
        try:
            return self.bindings[lane.lane_id]
        except KeyError as exc:
            raise RuntimeError(f"FUSE_SOL62_BINDING_MISSING:{lane.lane_id}") from exc

    def _validate_registered_contract(
        self,
        mission: MissionIR,
        lane: ServingLaneSpec,
        binding: Sol62LaneBinding,
    ) -> Mapping[str, Any]:
        transition_state = self.runtime.control.get_state("sol62.transition", binding.transition_id)
        if not transition_state:
            raise RuntimeError("FUSE_SOL62_TRANSITION_NOT_REGISTERED")
        transition = transition_state["value"]
        if str(transition.get("mission_id")) != mission.mission_id:
            raise RuntimeError("FUSE_SOL62_MISSION_IDENTITY_MISMATCH")
        if str(transition.get("operation")) != lane.action:
            raise RuntimeError("FUSE_SOL62_OPERATION_MISMATCH")
        if str(transition.get("source_version")) != binding.source_version:
            raise RuntimeError("FUSE_SOL62_SOURCE_VERSION_MISMATCH")
        if bool(transition.get("consequential")) != (mission.effect_class == "CONSEQUENTIAL_EFFECT"):
            raise RuntimeError("FUSE_SOL62_EFFECT_CLASS_MISMATCH")
        if mission.effect_class == "CONSEQUENTIAL_EFFECT" and not binding.authority_lease_id:
            raise RuntimeError("FUSE_SOL62_CONSEQUENTIAL_AUTHORITY_REQUIRED")
        return transition

    def _mark_uncertain(self, effect_id: str, error: BaseException) -> None:
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
                result={"handler_error": f"{type(error).__name__}: {error}"},
            )
        except Exception:
            # Preserve the original exception. SOL recovery/readback will still
            # encounter the non-terminal effect and must resolve it explicitly.
            return

    def execute(
        self,
        *,
        mission: MissionIR,
        lane: ServingLaneSpec,
        handler: Callable[[], Any],
    ) -> EffectReceipt:
        mission = mission.normalized()
        mission.validate()
        lane.validate()
        binding = self._binding(lane)
        binding.validate()
        self._validate_registered_contract(mission, lane, binding)

        now = int(self.now_epoch())
        ready = self.runtime.ready_transitions(
            mission.mission_id,
            satisfied_constraints=set(binding.satisfied_constraints),
        )
        if binding.transition_id not in ready:
            raise RuntimeError("FUSE_SOL62_TRANSITION_NOT_READY")

        intent = ExecutionIntent(
            effect_id=binding.effect_id,
            transition_id=binding.transition_id,
            provider=binding.provider,
            payload=dict(binding.payload),
            semantics=binding.semantics,
            idempotency_key=binding.idempotency_key,
            actor=binding.actor,
            source_version=binding.source_version,
            expected_readback=dict(lane.expected_target_state),
            rollback_required=mission.rollback_required,
        )
        self.runtime.prepare_execution(
            intent,
            gateway_request=dict(self.gateway_request_factory(mission, lane)),
            identity_claims=dict(self.identity_claims_factory(mission, lane)),
            now_epoch=now,
        )
        fence = self.runtime.acquire_execution_fence(
            binding.transition_id,
            binding.worker,
            ttl_seconds=binding.fence_ttl_seconds,
            now_epoch=now,
        )
        self.runtime.authorize_dispatch(
            binding.effect_id,
            authority_lease_id=binding.authority_lease_id,
            actor=binding.actor,
            source_version=binding.source_version,
            now_epoch=now,
            worker=binding.worker,
            lease_epoch=int(fence["epoch"]),
            fencing_token=int(fence["fencing_token"]),
            simulation_proof_id=binding.simulation_proof_id,
        )

        try:
            observation = ProviderEffectObservation.from_value(handler())
        except BaseException as exc:
            self._mark_uncertain(binding.effect_id, exc)
            raise

        if not observation.provider_ref:
            error = RuntimeError("FUSE_SOL62_PROVIDER_REFERENCE_REQUIRED")
            self._mark_uncertain(binding.effect_id, error)
            raise error

        self.runtime.mark_dispatched(
            binding.effect_id,
            provider_ref=observation.provider_ref,
        )
        observed = self.runtime.observe_effect(
            binding.effect_id,
            readback=dict(observation.readback),
        )
        if not bool(observed.get("match")):
            raise RuntimeError("FUSE_SOL62_PROVIDER_READBACK_MISMATCH")

        committed = self.runtime.verify_effect_and_commit(
            binding.effect_id,
            proof_ids=observation.proof_ids,
            now_epoch=now,
            satisfied_constraints=set(binding.satisfied_constraints),
        )
        if committed.get("state") != "VERIFIED":
            raise RuntimeError("FUSE_SOL62_TRANSITION_NOT_VERIFIED")

        proof_axes = {
            "PROVIDER_READBACK",
            "SOL62_VERIFIED_TRANSITION",
            *observation.proof_axes,
        }
        proof_refs = {
            observation.provider_ref,
            *observation.proof_refs,
            *(f"sol62:proof:{proof_id}" for proof_id in observation.proof_ids),
        }
        event_hash = str(committed.get("event_hash", "")).strip()
        if event_hash:
            proof_refs.add(f"sol62:event:{event_hash}")

        return EffectReceipt.verified(
            observed_state=dict(observation.readback),
            proof_axes=tuple(sorted(proof_axes)),
            proof_refs=tuple(sorted(proof_refs)),
            provider_ref=observation.provider_ref,
        )
