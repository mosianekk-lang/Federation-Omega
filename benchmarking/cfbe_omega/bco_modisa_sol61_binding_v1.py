from __future__ import annotations

"""BCO-Prime -> Modisa -> SOL 6.1 cognitive binding v1.

Dependency is intentionally asymmetric and fail-closed:

1. BCO-Prime may observe, challenge and propose a bounded shadow decision.
2. Modisa validates mission identity, doctrine invariants, authority, proof and hold state.
3. SOL 6.1 records the admitted no-effect decision as durable state and verifies completion
   only when BCO, Modisa and SOL receipts are all present.

This module never grants provider authority, never dispatches an external effect, never
promotes BCO-Prime policy, and never makes SOL depend on BCO-Prime or Modisa.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarking.cfbe_omega.bco_prime_meta_executive_v1 import (
    PrimeDecisionIR,
    PrimeObservation,
    StrategyCandidate,
    compile_prime_decision,
)
from sol_61_runtime.runtime import CompletionContract, Mission, SolRuntime, Workstream


SCHEMA = "BCO_MODISA_SOL61_COGNITIVE_BINDING_V1"
CONTRACT_VERSION = "1.0.0"
MODISA_KERNEL_RELATIVE_PATH = Path("federation_consolidation/data/modisa_compact_kernel.json")
MODISA_KERNEL_ID = "MODISA-COMPACT-KERNEL-v1"

REQUIRED_MODISA_INVARIANTS = frozenset(
    {
        "owner message supremacy",
        "proof before claim",
        "history before limitation",
        "no external action from prepare/approve language",
        "lowest proven maturity controls",
        "all writes require readback",
        "large jobs use bounded checkpoints",
    }
)

REQUIRED_MODISA_STAGES = (
    "MISSION_CLASSIFY",
    "SOURCE_GATE",
    "AUTHORITY_GATE",
    "DEPENDENCY_GRAPH",
    "PROOF_CONTRACT",
    "PREVENTION_GATES",
    "EXECUTE_OR_HOLD",
    "READBACK",
    "LESSON",
    "ROLLBACK_CHECKPOINT",
)

REQUIRED_SOL_RECEIPTS = (
    "BCO_PRIME_DECISION",
    "MODISA_GATE",
    "SOL61_INTERNAL_COMMIT",
)


class ModisaGateState(str, Enum):
    ADMITTED_INTERNAL = "ADMITTED_INTERNAL"
    HOLD_OWNER = "HOLD_OWNER"
    HOLD_PROVIDER = "HOLD_PROVIDER"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class ModisaGateReceipt:
    schema: str
    kernel_id: str
    state: ModisaGateState
    mission_id: str
    objective_sha256: str
    bco_decision_sha256: str
    invariant_count: int
    stage_count: int
    blockers: tuple[str, ...]
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def canonical_mapping(self, *, include_receipt: bool = True) -> dict[str, Any]:
        body = asdict(self)
        if not include_receipt:
            body.pop("receipt_sha256", None)
        return body


@dataclass(frozen=True, slots=True)
class TriadBindingReceipt:
    schema: str
    version: str
    mission_id: str
    workstream_id: str
    bco_decision_sha256: str
    modisa_gate_sha256: str
    modisa_gate_state: ModisaGateState
    sol61_completion_state: str
    present_receipt_types: tuple[str, ...]
    missing_receipt_types: tuple[str, ...]
    checkpoint_id: str | None
    event_chain_verified: bool
    reused_existing: bool
    dispatch_authorized: bool
    external_effect_authorized: bool
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def canonical_mapping(self, *, include_receipt: bool = True) -> dict[str, Any]:
        body = asdict(self)
        if not include_receipt:
            body.pop("receipt_sha256", None)
        return body


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _receipt(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _objective_sha256(objective: str) -> str:
    return sha256(objective.encode("utf-8")).hexdigest()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_modisa_kernel(*, repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else _repo_root()
    path = root / MODISA_KERNEL_RELATIVE_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("MODISA_KERNEL_NOT_OBJECT")
    return raw


def validate_modisa_kernel(kernel: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if str(kernel.get("kernel_id", "")).strip() != MODISA_KERNEL_ID:
        raise ValueError("MODISA_KERNEL_ID_MISMATCH")
    invariants = tuple(str(item).strip() for item in kernel.get("invariants", ()))
    stages = tuple(str(item).strip() for item in kernel.get("stages", ()))
    missing_invariants = tuple(sorted(REQUIRED_MODISA_INVARIANTS - set(invariants)))
    missing_stages = tuple(stage for stage in REQUIRED_MODISA_STAGES if stage not in stages)
    if missing_invariants:
        raise ValueError("MODISA_KERNEL_INVARIANT_DRIFT:" + ",".join(missing_invariants))
    if missing_stages:
        raise ValueError("MODISA_KERNEL_STAGE_DRIFT:" + ",".join(missing_stages))
    return invariants, stages


def evaluate_modisa_gate(
    *,
    decision: PrimeDecisionIR,
    mission_objective: str,
    kernel: Mapping[str, Any] | None = None,
) -> ModisaGateReceipt:
    current_kernel = dict(kernel) if kernel is not None else load_modisa_kernel()
    invariants, stages = validate_modisa_kernel(current_kernel)
    expected_objective = _objective_sha256(mission_objective)
    blockers: list[str] = []

    if decision.objective_sha256.lower() != expected_objective:
        blockers.append("MISSION_OBJECTIVE_HASH_MISMATCH")
    if decision.dispatch_authorized:
        blockers.append("BCO_PRIME_DISPATCH_AUTHORITY_FORBIDDEN")
    if decision.external_effect_authorized:
        blockers.append("BCO_PRIME_EXTERNAL_EFFECT_AUTHORITY_FORBIDDEN")
    if not decision.receipt_sha256 or len(decision.receipt_sha256) != 64:
        blockers.append("BCO_PRIME_DECISION_RECEIPT_INVALID")

    if blockers:
        state = ModisaGateState.REJECTED
    elif decision.owner_interrupt_required:
        state = ModisaGateState.HOLD_OWNER
    elif decision.provider_runtime_hold:
        state = ModisaGateState.HOLD_PROVIDER
    else:
        state = ModisaGateState.ADMITTED_INTERNAL

    body = {
        "schema": SCHEMA,
        "kernel_id": MODISA_KERNEL_ID,
        "state": state.value,
        "mission_id": decision.mission_id,
        "objective_sha256": decision.objective_sha256.lower(),
        "bco_decision_sha256": decision.receipt_sha256,
        "invariant_count": len(invariants),
        "stage_count": len(stages),
        "blockers": tuple(blockers),
        "truth_boundary": (
            "BCO_PRIME_IS_NON_SOVEREIGN",
            "MODISA_GATE_DOES_NOT_GRANT_PROVIDER_AUTHORITY",
            "SOL61_PROVIDER_EFFECTS_REQUIRE_SEPARATE_CAPABILITY_AND_READBACK",
            "NO_EXTERNAL_EFFECT_IS_EXECUTED_BY_THIS_BINDING",
        ),
    }
    return ModisaGateReceipt(
        schema=SCHEMA,
        kernel_id=MODISA_KERNEL_ID,
        state=state,
        mission_id=decision.mission_id,
        objective_sha256=decision.objective_sha256.lower(),
        bco_decision_sha256=decision.receipt_sha256,
        invariant_count=len(invariants),
        stage_count=len(stages),
        blockers=tuple(blockers),
        truth_boundary=tuple(body["truth_boundary"]),
        receipt_sha256=_receipt(body),
    )


def _matching_receipts(runtime: SolRuntime, workstream_id: str) -> dict[str, dict[str, Any]]:
    matching: dict[str, dict[str, Any]] = {}
    for receipt in runtime.state.receipts.values():
        if receipt.get("workstream_id") != workstream_id:
            continue
        receipt_type = str(receipt.get("receipt_type", ""))
        if receipt_type and receipt_type not in matching:
            matching[receipt_type] = receipt
    return matching


def _build_binding_receipt(
    *,
    runtime: SolRuntime,
    decision: PrimeDecisionIR,
    gate: ModisaGateReceipt,
    workstream_id: str,
    completion_state: str,
    checkpoint_id: str | None,
    reused_existing: bool,
) -> TriadBindingReceipt:
    receipts = _matching_receipts(runtime, workstream_id)
    present = tuple(item for item in REQUIRED_SOL_RECEIPTS if item in receipts)
    missing = tuple(item for item in REQUIRED_SOL_RECEIPTS if item not in receipts)
    body = {
        "schema": SCHEMA,
        "version": CONTRACT_VERSION,
        "mission_id": decision.mission_id,
        "workstream_id": workstream_id,
        "bco_decision_sha256": decision.receipt_sha256,
        "modisa_gate_sha256": gate.receipt_sha256,
        "modisa_gate_state": gate.state.value,
        "sol61_completion_state": completion_state,
        "present_receipt_types": present,
        "missing_receipt_types": missing,
        "checkpoint_id": checkpoint_id,
        "event_chain_verified": runtime.verify_event_chain(),
        "reused_existing": reused_existing,
        "dispatch_authorized": False,
        "external_effect_authorized": False,
        "truth_boundary": (
            "BCO_PRIME_PROPOSES_AND_CHALLENGES_ONLY",
            "MODISA_VALIDATES_MISSION_AUTHORITY_PROOF_AND_CONTINUITY",
            "SOL61_IS_THE_DURABLE_COMMIT_AND_COMPLETION_AUTHORITY_FOR_THIS_BINDING",
            "PROVIDER_EFFECT_AUTHORITY_REMAINS_OUTSIDE_THIS_BINDING",
            "STABLE_SELF_PROMOTION_IS_NOT_AUTHORIZED",
        ),
    }
    return TriadBindingReceipt(
        schema=SCHEMA,
        version=CONTRACT_VERSION,
        mission_id=decision.mission_id,
        workstream_id=workstream_id,
        bco_decision_sha256=decision.receipt_sha256,
        modisa_gate_sha256=gate.receipt_sha256,
        modisa_gate_state=gate.state,
        sol61_completion_state=completion_state,
        present_receipt_types=present,
        missing_receipt_types=missing,
        checkpoint_id=checkpoint_id,
        event_chain_verified=bool(body["event_chain_verified"]),
        reused_existing=reused_existing,
        dispatch_authorized=False,
        external_effect_authorized=False,
        truth_boundary=tuple(body["truth_boundary"]),
        receipt_sha256=_receipt(body),
    )


def bind_bco_modisa_sol61(
    *,
    runtime: SolRuntime,
    mission_objective: str,
    success_definition: Sequence[str],
    observation: PrimeObservation,
    strategies: Sequence[StrategyCandidate],
    mission_version: int = 1,
    kernel: Mapping[str, Any] | None = None,
) -> TriadBindingReceipt:
    """Compile BCO-Prime, apply Modisa gate, then durably commit through SOL 6.1.

    The binding itself is always no-effect. Any later provider action must go through
    SOL 6.1's normal provider capability/admission path and obtain provider-native
    receipts independently.
    """

    expected_objective = _objective_sha256(mission_objective)
    if observation.objective_sha256.lower() != expected_objective:
        raise ValueError("TRIAD_OBSERVATION_OBJECTIVE_HASH_MISMATCH")

    decision = compile_prime_decision(observation, strategies)
    gate = evaluate_modisa_gate(
        decision=decision,
        mission_objective=mission_objective,
        kernel=kernel,
    )

    existing_mission = runtime.state.missions.get(decision.mission_id)
    if existing_mission is None:
        runtime.register_mission(
            Mission(
                mission_id=decision.mission_id,
                objective=mission_objective,
                success_definition=tuple(success_definition),
                constraints=(
                    "BCO_PRIME_NON_SOVEREIGN",
                    "MODISA_PROOF_BEFORE_CLAIM",
                    "SOL61_PROVIDER_NATIVE_READBACK_REQUIRED",
                ),
                version=mission_version,
            )
        )
    else:
        if str(existing_mission.get("objective", "")) != mission_objective:
            raise ValueError("TRIAD_SOL61_MISSION_OBJECTIVE_CONFLICT")
        if tuple(existing_mission.get("success_definition", ())) != tuple(success_definition):
            raise ValueError("TRIAD_SOL61_SUCCESS_DEFINITION_CONFLICT")

    workstream_id = f"triad-{decision.mission_id}-{decision.receipt_sha256[:16]}"
    existing_workstream = runtime.state.workstreams.get(workstream_id)
    if existing_workstream and existing_workstream.get("status") == "VERIFIED":
        checkpoints = [
            item for item in runtime.state.checkpoints.values()
            if item.get("mission_id") == decision.mission_id
        ]
        checkpoint_id = checkpoints[-1]["checkpoint_id"] if checkpoints else None
        return _build_binding_receipt(
            runtime=runtime,
            decision=decision,
            gate=gate,
            workstream_id=workstream_id,
            completion_state="VERIFIED",
            checkpoint_id=checkpoint_id,
            reused_existing=True,
        )

    if existing_workstream is None:
        runtime.register_workstream(
            Workstream(
                workstream_id=workstream_id,
                mission_id=decision.mission_id,
                objective="Bind BCO-Prime decision through Modisa into SOL 6.1 durable state",
                dependencies=(),
                priority=95,
                reversible=True,
            )
        )

    existing_receipts = _matching_receipts(runtime, workstream_id)
    if "BCO_PRIME_DECISION" not in existing_receipts:
        runtime.record_receipt(
            workstream_id,
            "BCO_PRIME_DECISION",
            "BCO_PRIME",
            {
                "schema": decision.schema,
                "mode": decision.mode.value,
                "decision_sha256": decision.receipt_sha256,
                "meta_action": decision.meta_action.value,
                "topology_mode": decision.topology_mode.value,
                "champion_strategy_id": decision.champion_strategy_id,
                "dispatch_authorized": decision.dispatch_authorized,
                "external_effect_authorized": decision.external_effect_authorized,
                "proof_requirements": tuple(decision.proof_requirements),
            },
        )
    if "MODISA_GATE" not in existing_receipts:
        runtime.record_receipt(
            workstream_id,
            "MODISA_GATE",
            "MODISA",
            gate.canonical_mapping(),
        )

    if gate.state == ModisaGateState.ADMITTED_INTERNAL:
        current_receipts = _matching_receipts(runtime, workstream_id)
        if "SOL61_INTERNAL_COMMIT" not in current_receipts:
            event = runtime.append_event(
                "BCO_MODISA_SOL61_INTERNAL_BINDING_ADMITTED",
                {
                    "schema": SCHEMA,
                    "mission_id": decision.mission_id,
                    "workstream_id": workstream_id,
                    "bco_decision_sha256": decision.receipt_sha256,
                    "modisa_gate_sha256": gate.receipt_sha256,
                    "effect_class": "NO_EFFECT",
                    "provider_dispatch": False,
                },
            )
            runtime.record_receipt(
                workstream_id,
                "SOL61_INTERNAL_COMMIT",
                "SOL_6_1",
                {
                    "event_id": event["event_id"],
                    "event_hash": event["event_hash"],
                    "effect_class": "NO_EFFECT",
                    "provider_dispatch": False,
                    "provider_native_readback_required_for_future_effects": True,
                },
            )

    completion = runtime.evaluate_completion(
        workstream_id,
        CompletionContract(REQUIRED_SOL_RECEIPTS),
    )
    checkpoint = runtime.checkpoint(decision.mission_id)

    return _build_binding_receipt(
        runtime=runtime,
        decision=decision,
        gate=gate,
        workstream_id=workstream_id,
        completion_state=str(completion["state"]),
        checkpoint_id=str(checkpoint["checkpoint_id"]),
        reused_existing=False,
    )


def triad_capability_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": CONTRACT_VERSION,
        "roles": {
            "BCO_PRIME": "PROPOSE_CHALLENGE_RANK_AND_PLAN",
            "MODISA": "MISSION_AUTHORITY_PROOF_CONTINUITY_GATE",
            "SOL_6_1": "DURABLE_COMMIT_COMPLETION_AND_PROVIDER_ADMISSION",
        },
        "authority": {
            "binding_effect_class": "NO_EFFECT",
            "dispatch_authorized": False,
            "external_effect_authorized": False,
            "stable_self_promotion_allowed": False,
            "provider_effects_require_separate_sol61_admission": True,
        },
        "modisa_kernel": {
            "kernel_id": MODISA_KERNEL_ID,
            "required_invariants": sorted(REQUIRED_MODISA_INVARIANTS),
            "required_stages": list(REQUIRED_MODISA_STAGES),
        },
        "sol61_receipts": list(REQUIRED_SOL_RECEIPTS),
    }
