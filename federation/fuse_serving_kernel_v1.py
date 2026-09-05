from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Protocol, Sequence

from bubbles.chat_governor_omega3.dag import DAGExecutor, Lane, LaneState
from bubbles.chat_governor_omega3.state import DurableState
from federation.mission_ir import MissionIR
from federation.uas_runtime_v1 import EvaluationEvidence, UASRuntimeEvaluator


_SCHEMA = "FUSE-SERVING-KERNEL-V1"
_EFFECTFUL = {"BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"}
_META_KEY = "__fuse_meta__"
_VALUE_KEY = "value"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _clean(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(item).strip() for item in values if str(item).strip()}))


def _logical_sequence(value: Any, fallback: str) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        raw = value.get("tool_sequence", ())
        sequence = tuple(str(item).strip() for item in raw if str(item).strip())
        if sequence:
            return sequence
    return (fallback,)


@dataclass(frozen=True, slots=True)
class ContextContract:
    """Explicit canonical-context requirements for one mission.

    Source IDs refer to Bubbles evidence pointers. The kernel never guesses that a
    historical source is current merely because a title or memory exists.
    """

    required_source_ids: tuple[str, ...] = ()
    source_versions: Mapping[str, str] = field(default_factory=dict)
    minimum_verified_sources: int = 0


@dataclass(frozen=True, slots=True)
class ContextPreflightReceipt:
    state: str
    verified_source_ids: tuple[str, ...]
    missing_source_ids: tuple[str, ...]
    stale_source_ids: tuple[str, ...]
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class ServingLaneSpec:
    lane_id: str
    action: str
    dependencies: tuple[str, ...] = ()
    effect_class: str = "NO_EFFECT"
    expected_target_state: Mapping[str, Any] = field(default_factory=dict)
    required_proof_axes: tuple[str, ...] = ()
    expected_tool_sequence: tuple[str, ...] = ()
    required: bool = True

    def validate(self) -> None:
        if not self.lane_id.strip() or not self.action.strip():
            raise ValueError("FUSE_LANE_ID_AND_ACTION_REQUIRED")
        effect = self.effect_class.strip().upper()
        if effect not in {"NO_EFFECT", "READ_ONLY", "BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"}:
            raise ValueError("FUSE_LANE_EFFECT_CLASS_INVALID")
        if effect in _EFFECTFUL and not self.expected_target_state:
            raise ValueError("FUSE_EFFECT_LANE_TARGET_STATE_REQUIRED")


@dataclass(frozen=True, slots=True)
class EffectReceipt:
    state: str
    observed_state: Mapping[str, Any]
    proof_axes: tuple[str, ...]
    proof_refs: tuple[str, ...] = ()
    provider_ref: str = ""
    receipt_sha256: str = ""

    @classmethod
    def verified(
        cls,
        *,
        observed_state: Mapping[str, Any],
        proof_axes: Sequence[str],
        proof_refs: Sequence[str] = (),
        provider_ref: str = "",
    ) -> "EffectReceipt":
        body = {
            "state": "VERIFIED",
            "observed_state": dict(observed_state),
            "proof_axes": sorted(set(proof_axes)),
            "proof_refs": sorted(set(proof_refs)),
            "provider_ref": provider_ref,
        }
        return cls(
            state="VERIFIED",
            observed_state=dict(observed_state),
            proof_axes=tuple(body["proof_axes"]),
            proof_refs=tuple(body["proof_refs"]),
            provider_ref=provider_ref,
            receipt_sha256=_digest(body),
        )


class TransactionalEffectExecutor(Protocol):
    """Adapter boundary for SOL 6.2/FDOF or another verified effect runtime."""

    def execute(
        self,
        *,
        mission: MissionIR,
        lane: ServingLaneSpec,
        handler: Callable[[], Any],
    ) -> EffectReceipt: ...


@dataclass(frozen=True, slots=True)
class FUSEServingReceipt:
    mission_id: str
    state: str
    mission_ir_sha256: str
    context_preflight_sha256: str
    dag_receipt_sha256: str
    uas_evaluation_sha256: str
    lane_states: Mapping[str, str]
    proof_axes: tuple[str, ...]
    proof_refs: tuple[str, ...]
    checkpoint_id: str
    receipt_sha256: str


class CanonicalContextPreflight:
    def __init__(self, state: DurableState) -> None:
        self.state = state

    def evaluate(self, contract: ContextContract) -> ContextPreflightReceipt:
        required = tuple(sorted({item.strip() for item in contract.required_source_ids if item.strip()}))
        missing: list[str] = []
        stale: list[str] = []
        verified: list[str] = []

        for source_id in required:
            pointer = self.state.get_evidence(source_id)
            if pointer is None or not pointer.verified:
                missing.append(source_id)
                continue
            expected_version = str(contract.source_versions.get(source_id, "")).strip()
            if expected_version and self.state.needs_refresh(source_id, version=expected_version):
                stale.append(source_id)
                continue
            verified.append(source_id)

        if len(verified) < int(contract.minimum_verified_sources):
            missing.append("MINIMUM_VERIFIED_SOURCES_NOT_MET")

        state = "PASS" if not missing and not stale else "HOLD"
        body = {
            "schema": "FUSE-CANONICAL-CONTEXT-PREFLIGHT-V1",
            "state": state,
            "verified_source_ids": sorted(verified),
            "missing_source_ids": sorted(set(missing)),
            "stale_source_ids": sorted(set(stale)),
        }
        return ContextPreflightReceipt(
            state=state,
            verified_source_ids=tuple(body["verified_source_ids"]),
            missing_source_ids=tuple(body["missing_source_ids"]),
            stale_source_ids=tuple(body["stale_source_ids"]),
            receipt_sha256=_digest(body),
        )


class FUSEServingKernelV1:
    """Composition facade over admitted Federation primitives.

    V1 deliberately reuses canonical MissionIR, Bubbles durable state/DAG
    isolation and the executable UAS court. Effectful lanes require an injected
    transactional executor (intended for SOL 6.2/FDOF) and cannot self-authorize.

    Parallel lanes return lane-local proof metadata. The coordinator aggregates
    evidence only after DAG completion, eliminating shared mutable proof state
    across worker threads and making the proof projection deterministic.
    """

    version = "1.0.1"

    def __init__(
        self,
        state: DurableState,
        *,
        evaluator: UASRuntimeEvaluator | None = None,
        effect_executor: TransactionalEffectExecutor | None = None,
        max_workers: int = 4,
    ) -> None:
        self.state = state
        self.preflight = CanonicalContextPreflight(state)
        self.evaluator = evaluator or UASRuntimeEvaluator()
        self.effect_executor = effect_executor
        self.dag = DAGExecutor(state, max_workers=max_workers)

    @staticmethod
    def _lane(lane: ServingLaneSpec) -> Lane:
        lane.validate()
        return Lane(
            lane_id=lane.lane_id,
            action=lane.action,
            dependencies=list(lane.dependencies),
        )

    @staticmethod
    def _wrapped_result(
        *,
        value: Any,
        proof_axes: Sequence[str],
        proof_refs: Sequence[str],
        tool_sequence: Sequence[str],
    ) -> dict[str, Any]:
        return {
            _META_KEY: {
                "proof_axes": list(_clean(tuple(proof_axes))),
                "proof_refs": list(_clean(tuple(proof_refs))),
                "tool_sequence": [str(item).strip() for item in tool_sequence if str(item).strip()],
            },
            _VALUE_KEY: value,
        }

    @staticmethod
    def _aggregate_lane_evidence(
        lane_specs: Sequence[ServingLaneSpec],
        dag_result: Mapping[str, Any],
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        axes: set[str] = set()
        refs: set[str] = set()
        logical_sequence: list[str] = []
        lanes = dict(dag_result["lanes"])
        for spec in lane_specs:
            payload = lanes.get(spec.lane_id, {})
            if str(payload.get("state")) != LaneState.COMPLETE.value:
                continue
            result = payload.get("result")
            if not isinstance(result, Mapping):
                raise RuntimeError(f"FUSE_LANE_RESULT_ENVELOPE_MISSING:{spec.lane_id}")
            meta = result.get(_META_KEY)
            if not isinstance(meta, Mapping):
                raise RuntimeError(f"FUSE_LANE_META_MISSING:{spec.lane_id}")
            axes.update(str(x).strip() for x in meta.get("proof_axes", ()) if str(x).strip())
            refs.update(str(x).strip() for x in meta.get("proof_refs", ()) if str(x).strip())
            logical_sequence.extend(
                str(x).strip() for x in meta.get("tool_sequence", ()) if str(x).strip()
            )
        return tuple(sorted(axes)), tuple(sorted(refs)), tuple(logical_sequence)

    def run(
        self,
        mission: MissionIR,
        *,
        context: ContextContract,
        lanes: Sequence[ServingLaneSpec],
        handlers: Mapping[str, Callable[[], Any]],
        owner_interventions: int = 0,
        cost_microunits: int | None = None,
        latency_ms: int | None = None,
    ) -> FUSEServingReceipt:
        mission = mission.normalized()
        mission.validate()
        lane_specs = tuple(lanes)
        if not lane_specs:
            raise ValueError("FUSE_AT_LEAST_ONE_LANE_REQUIRED")
        if len({lane.lane_id for lane in lane_specs}) != len(lane_specs):
            raise ValueError("FUSE_LANE_ID_DUPLICATE")
        for lane in lane_specs:
            lane.validate()

        context_receipt = self.preflight.evaluate(context)
        self.state.save_plan(
            {
                "mission_id": mission.mission_id,
                "objective": mission.objective,
                "mission_type": "FUSE_SERVING_KERNEL",
                "mission_ir_sha256": mission.digest(),
                "context_preflight_sha256": context_receipt.receipt_sha256,
                "lane_ids": [lane.lane_id for lane in lane_specs],
                "kernel_version": self.version,
            },
            state="ACTIVE" if context_receipt.state == "PASS" else "HOLD_CONTEXT",
        )

        if context_receipt.state != "PASS":
            checkpoint_id = self.state.checkpoint(
                mission.mission_id,
                {
                    "schema": _SCHEMA,
                    "state": "HOLD_CONTEXT",
                    "mission_ir_sha256": mission.digest(),
                    "context_preflight": asdict(context_receipt),
                },
                proof_bearing=False,
            )
            empty_eval = self.evaluator.evaluate(
                mission,
                EvaluationEvidence(
                    outcome_ok=False,
                    proof_axes=(),
                    critical_failures=("CANONICAL_CONTEXT_PREFLIGHT_FAILED",),
                    owner_interventions=max(0, owner_interventions),
                    cost_microunits=cost_microunits,
                    latency_ms=latency_ms,
                ),
            )
            body = {
                "mission_id": mission.mission_id,
                "state": "HOLD_CONTEXT",
                "mission_ir_sha256": mission.digest(),
                "context_preflight_sha256": context_receipt.receipt_sha256,
                "dag_receipt_sha256": "",
                "uas_evaluation_sha256": empty_eval.evaluation_sha256,
                "lane_states": {},
                "proof_axes": (),
                "proof_refs": (),
                "checkpoint_id": checkpoint_id,
            }
            return FUSEServingReceipt(**body, receipt_sha256=_digest(body))

        dag_lanes = [self._lane(lane) for lane in lane_specs]
        spec_by_id = {lane.lane_id: lane for lane in lane_specs}
        dag_handlers: dict[str, Callable[[Lane], Any]] = {}

        for lane in lane_specs:
            raw_handler = handlers.get(lane.lane_id)
            if raw_handler is None:
                continue

            def make_handler(spec: ServingLaneSpec, fn: Callable[[], Any]) -> Callable[[Lane], Any]:
                def execute(_: Lane) -> Any:
                    effect = spec.effect_class.strip().upper()
                    if effect in _EFFECTFUL:
                        if self.effect_executor is None:
                            raise RuntimeError("FUSE_EFFECT_EXECUTOR_REQUIRED")
                        receipt = self.effect_executor.execute(mission=mission, lane=spec, handler=fn)
                        if receipt.state != "VERIFIED":
                            raise RuntimeError("FUSE_EFFECT_NOT_VERIFIED")
                        if dict(receipt.observed_state) != dict(spec.expected_target_state):
                            raise RuntimeError("FUSE_EFFECT_TARGET_STATE_MISMATCH")
                        observed_axes = {str(x).strip() for x in receipt.proof_axes if str(x).strip()}
                        missing_lane_axes = set(spec.required_proof_axes) - observed_axes
                        if missing_lane_axes:
                            raise RuntimeError(
                                "FUSE_EFFECT_REQUIRED_PROOF_MISSING:"
                                + ",".join(sorted(missing_lane_axes))
                            )
                        return self._wrapped_result(
                            value={
                                "effect_receipt_sha256": receipt.receipt_sha256,
                                "provider_ref": receipt.provider_ref,
                                "observed_state": dict(receipt.observed_state),
                            },
                            proof_axes=tuple(observed_axes),
                            proof_refs=receipt.proof_refs,
                            tool_sequence=(spec.action,),
                        )

                    result = fn()
                    lane_axes: set[str] = set()
                    lane_refs: set[str] = set()
                    if isinstance(result, Mapping):
                        lane_axes.update(
                            str(x).strip() for x in result.get("proof_axes", ()) if str(x).strip()
                        )
                        lane_refs.update(
                            str(x).strip() for x in result.get("proof_refs", ()) if str(x).strip()
                        )
                    missing_lane_axes = set(spec.required_proof_axes) - lane_axes
                    if missing_lane_axes:
                        raise RuntimeError(
                            "FUSE_LANE_REQUIRED_PROOF_MISSING:"
                            + ",".join(sorted(missing_lane_axes))
                        )
                    return self._wrapped_result(
                        value=result,
                        proof_axes=tuple(lane_axes),
                        proof_refs=tuple(lane_refs),
                        tool_sequence=_logical_sequence(result, spec.action),
                    )

                return execute

            dag_handlers[lane.lane_id] = make_handler(lane, raw_handler)

        dag_result = self.dag.run(mission.mission_id, dag_lanes, dag_handlers)
        lane_states = {
            lane_id: str(payload["state"])
            for lane_id, payload in dict(dag_result["lanes"]).items()
        }
        proof_axes, proof_refs, actual_tool_sequence = self._aggregate_lane_evidence(
            lane_specs,
            dag_result,
        )

        required_complete = all(
            lane_states.get(lane.lane_id) == LaneState.COMPLETE.value
            for lane in lane_specs
            if lane.required
        )
        critical_failures = tuple(
            sorted(
                lane_id
                for lane_id, state in lane_states.items()
                if state in {LaneState.FAILED.value, LaneState.BLOCKED.value}
                and spec_by_id[lane_id].required
            )
        )
        expected_tool_sequence = tuple(
            action
            for lane in lane_specs
            for action in lane.expected_tool_sequence
        )

        evaluation = self.evaluator.evaluate(
            mission,
            EvaluationEvidence(
                outcome_ok=required_complete,
                proof_axes=proof_axes,
                expected_tool_sequence=expected_tool_sequence,
                actual_tool_sequence=actual_tool_sequence,
                critical_failures=critical_failures,
                owner_interventions=max(0, owner_interventions),
                cost_microunits=cost_microunits,
                latency_ms=latency_ms,
            ),
        )

        terminal = "COMPLETE" if evaluation.state == "PASS" else "HOLD_UAS"
        checkpoint_payload = {
            "schema": _SCHEMA,
            "version": self.version,
            "state": terminal,
            "mission_ir_sha256": mission.digest(),
            "context_preflight_sha256": context_receipt.receipt_sha256,
            "dag_receipt_sha256": str(dag_result["receipt_sha256"]),
            "uas_evaluation_sha256": evaluation.evaluation_sha256,
            "lane_states": lane_states,
            "proof_axes": list(proof_axes),
            "proof_refs": list(proof_refs),
            "truth_boundary": {
                "provider_effect_inferred": False,
                "authority_inherited": False,
                "production_cutover": False,
                "market_superiority_proven": False,
            },
        }
        checkpoint_id = self.state.checkpoint(
            mission.mission_id,
            checkpoint_payload,
            proof_bearing=terminal == "COMPLETE",
        )
        body = {
            "mission_id": mission.mission_id,
            "state": terminal,
            "mission_ir_sha256": mission.digest(),
            "context_preflight_sha256": context_receipt.receipt_sha256,
            "dag_receipt_sha256": str(dag_result["receipt_sha256"]),
            "uas_evaluation_sha256": evaluation.evaluation_sha256,
            "lane_states": lane_states,
            "proof_axes": proof_axes,
            "proof_refs": proof_refs,
            "checkpoint_id": checkpoint_id,
        }
        receipt = FUSEServingReceipt(**body, receipt_sha256=_digest(body))
        self.state.save_receipt(
            key=f"fuse-serving:{mission.mission_id}:{mission.digest()}",
            mission_id=mission.mission_id,
            action="FUSE_SERVING_TERMINAL",
            target=mission.outcome_contract,
            success=terminal == "COMPLETE",
            semantic_ok=evaluation.state == "PASS",
            payload={**asdict(receipt), "uas": asdict(evaluation)},
        )
        return receipt
