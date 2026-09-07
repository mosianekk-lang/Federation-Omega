"""FUSE MBMPC × PILF Production/Learning Closure Bridge v1.

Effect-free, provider-neutral adapter candidate. It does not create a truth store,
memory root, scheduler, authority plane, runtime, provider execution, or adoption.
It compiles supplied production and learning evidence into a deterministic closure
receipt so an existing FUSE host can prevent mission completion when required
production or learning/adoption debt remains.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from hashlib import sha256
import json
from typing import Iterable, Sequence

SCHEMA = "FUSE-MBMPC-PILF-CLOSURE-BRIDGE-V1"
VERSION = "1.0.0"


class PStage(IntEnum):
    P0_CANONICAL_DISCOVERED = 0
    P1_INTENT_BOUND = 1
    P2_REQUIREMENTS_COMPILED = 2
    P3_CURRENT_STATE_CENSUSED = 3
    P4_GAP_GRAPH_COMPILED = 4
    P5_ROUTE_SELECTED = 5
    P6_IMPLEMENTATION_PLAN_READY = 6
    P7_BUILT = 7
    P8_LOCAL_ASSURED = 8
    P9_SOURCE_ADMITTED = 9
    P10_HOST_BOUND = 10
    P11_PROVIDER_RUNNING = 11
    P12_SEMANTIC_READBACK_VERIFIED = 12
    P13_BEHAVIOUR_VERIFIED = 13
    P14_PRODUCTION_QUALIFIED = 14
    P15_PRODUCTION_PROMOTED = 15
    P16_VALUE_OBSERVED = 16
    P17_CONTINUOUS_IMPROVEMENT_ACTIVE = 17
    P18_FRONTIER_SUPERIOR_VERIFIED = 18


class LStage(IntEnum):
    L0_OBSERVED = 0
    L1_EVIDENCE_BOUND = 1
    L2_CAUSAL_HYPOTHESIS = 2
    L3_FALSIFIED_OR_VALIDATED = 3
    L4_GENERALIZED_RULE = 4
    L5_INNOVATION_CANDIDATE = 5
    L6_LOCALLY_TESTED = 6
    L7_SOURCE_OR_CONTROL_ADMITTED = 7
    L8_RECEIVER_BOUND = 8
    L9_BEHAVIOUR_ADOPTED = 9
    L10_VALUE_VERIFIED = 10
    L11_CRYSTALLIZED_REUSABLE_CAPABILITY = 11
    L12_SUPERSEDED_OR_RETIRED = 12


@dataclass(frozen=True, slots=True)
class MissionProductionContract:
    mission_id: str
    required_p_stage: PStage
    required_terminal_predicates: tuple[str, ...]
    continuous_learning_required: bool = False
    required_learning_stage: LStage = LStage.L9_BEHAVIOUR_ADOPTED
    authority_ceiling: str = "A1_INTERNAL"

    def validate(self) -> None:
        if not self.mission_id.strip():
            raise ValueError("MISSION_ID_REQUIRED")
        if not self.required_terminal_predicates:
            raise ValueError("TERMINAL_PREDICATES_REQUIRED")
        if self.continuous_learning_required and self.required_learning_stage < LStage.L8_RECEIVER_BOUND:
            raise ValueError("CONTINUOUS_LEARNING_REQUIRES_RECEIVER_BOUND_OR_STRONGER")


@dataclass(frozen=True, slots=True)
class LearningEvidence:
    learning_id: str
    stage: LStage
    evidence_refs: tuple[str, ...]
    fingerprint: str = ""
    generalized_rule: str = ""
    propagated: bool = False
    receiver_id: str = ""
    prevention_bound: bool = False
    owner_correction: bool = False
    machine_detectable: bool = False
    failure_event: bool = False
    recurrence_count: int = 0
    value_verified: bool = False

    def validate(self) -> None:
        if not self.learning_id.strip():
            raise ValueError("LEARNING_ID_REQUIRED")
        if self.stage >= LStage.L1_EVIDENCE_BOUND and not self.evidence_refs:
            raise ValueError("EVIDENCE_REFS_REQUIRED_AT_L1_PLUS")
        if self.failure_event and not self.fingerprint.strip():
            raise ValueError("FAILURE_WITHOUT_FINGERPRINT")
        if self.stage >= LStage.L9_BEHAVIOUR_ADOPTED and not self.receiver_id.strip():
            raise ValueError("RECEIVER_REQUIRED_FOR_ADOPTION")
        if self.stage >= LStage.L10_VALUE_VERIFIED and not self.value_verified:
            raise ValueError("VALUE_FLAG_REQUIRED_AT_L10_PLUS")


@dataclass(frozen=True, slots=True)
class ClosureReceipt:
    schema: str
    version: str
    mission_id: str
    current_p_stage: str
    required_p_stage: str
    production_debt: tuple[str, ...]
    learning_debt: tuple[str, ...]
    terminal_debt: tuple[str, ...]
    done_allowed: bool
    auto_continue_required: bool
    next_action: str
    deduplicated_learning_count: int
    receipt_digest: str


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


def _deduplicate(events: Iterable[LearningEvidence]) -> tuple[LearningEvidence, ...]:
    """Keep strongest evidence for a semantic learning key.

    Key is fingerprint+rule when present; otherwise learning_id. This prevents lesson
    spam while allowing later stronger evidence to supersede weaker observations.
    """
    strongest: dict[str, LearningEvidence] = {}
    for event in events:
        event.validate()
        semantic = (event.fingerprint.strip() + "|" + event.generalized_rule.strip()).strip("|")
        key = semantic or event.learning_id
        prior = strongest.get(key)
        if prior is None or event.stage > prior.stage or (
            event.stage == prior.stage and len(event.evidence_refs) > len(prior.evidence_refs)
        ):
            strongest[key] = event
    return tuple(strongest[key] for key in sorted(strongest))


class MissionEvolutionClosureBridge:
    """Compile MBMPC production state and PILF learning state into one closure receipt."""

    def evaluate(
        self,
        *,
        contract: MissionProductionContract,
        current_p_stage: PStage,
        satisfied_terminal_predicates: Sequence[str],
        learning_evidence: Sequence[LearningEvidence] = (),
    ) -> ClosureReceipt:
        contract.validate()
        events = _deduplicate(learning_evidence)

        terminal_debt = tuple(sorted(set(contract.required_terminal_predicates) - set(satisfied_terminal_predicates)))
        production_debt: list[str] = []
        if current_p_stage < contract.required_p_stage:
            production_debt.append(
                f"P_STAGE:{current_p_stage.name}->{contract.required_p_stage.name}"
            )

        learning_debt: list[str] = []
        if contract.continuous_learning_required:
            strongest_stage = max((event.stage for event in events), default=LStage.L0_OBSERVED)
            if strongest_stage < contract.required_learning_stage:
                learning_debt.append(
                    f"LEARNING_STAGE:{strongest_stage.name}->{contract.required_learning_stage.name}"
                )

            # Propagation never counts as adoption. L9+ requires a receiver and is checked by validate().
            if any(event.propagated and event.stage < LStage.L9_BEHAVIOUR_ADOPTED for event in events):
                learning_debt.append("PROPAGATION_NOT_ADOPTION")

        # Owner corrections exposing machine-detectable failures require prevention binding.
        for event in events:
            if event.owner_correction and event.machine_detectable and not event.prevention_bound:
                learning_debt.append(f"OWNER_CORRECTION_PREVENTION_REQUIRED:{event.learning_id}")
            if event.failure_event and event.recurrence_count >= 2 and not event.prevention_bound:
                learning_debt.append(f"RECURRING_FAILURE_PREVENTION_REQUIRED:{event.learning_id}")

        production_debt = sorted(set(production_debt))
        learning_debt = sorted(set(learning_debt))
        all_debt = production_debt or learning_debt or list(terminal_debt)
        done_allowed = not production_debt and not learning_debt and not terminal_debt

        if production_debt:
            next_action = "ADVANCE_PRODUCTION_STAGE"
        elif terminal_debt:
            next_action = "CLOSE_TERMINAL_PREDICATES"
        elif learning_debt:
            next_action = "CLOSE_LEARNING_ADOPTION_PREVENTION_DEBT"
        elif contract.continuous_learning_required:
            next_action = "CONTINUE_CLOSED_LEARNING_LOOP"
        else:
            next_action = "ALLOW_COMPLETE_VERIFIED"

        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": contract.mission_id,
            "current_p_stage": current_p_stage.name,
            "required_p_stage": contract.required_p_stage.name,
            "production_debt": production_debt,
            "learning_debt": learning_debt,
            "terminal_debt": terminal_debt,
            "done_allowed": done_allowed,
            "auto_continue_required": bool(all_debt),
            "next_action": next_action,
            "deduplicated_learning_count": len(events),
        }
        return ClosureReceipt(
            schema=SCHEMA,
            version=VERSION,
            mission_id=contract.mission_id,
            current_p_stage=current_p_stage.name,
            required_p_stage=contract.required_p_stage.name,
            production_debt=tuple(production_debt),
            learning_debt=tuple(learning_debt),
            terminal_debt=terminal_debt,
            done_allowed=done_allowed,
            auto_continue_required=bool(all_debt),
            next_action=next_action,
            deduplicated_learning_count=len(events),
            receipt_digest=_digest(material),
        )
