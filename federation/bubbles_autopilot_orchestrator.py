"""Bubbles autopilot/specialist orchestration bridge.

The bridge composes two existing controls instead of adding another scheduler:

* ``BubblesOmega2`` keeps work ranking, duplicate/stale filtering, architecture
  anti-proliferation and minimum-viable specialist squad selection.
* ``decide_autopilot`` keeps the Creative Focus Shield and effect/owner gates.

This module selects the highest-ranked *safe executable* lane. Held external,
high-consequence or owner-choice lanes do not freeze lower-ranked safe work.
Only when no safe executable lane remains does the receipt require an owner
interrupt. The bridge plans work; it does not execute tools or create provider
authority/background runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from bubbles.adaptive_organisation import (
    BubblesOmega2,
    MissionManifest,
    SquadPlan,
    WorkCandidate,
)
from federation.bubbles_autopilot_policy import (
    AutopilotDecision,
    AutopilotStep,
    decide_autopilot,
)


@dataclass(frozen=True, slots=True)
class AutopilotWorkEnvelope:
    candidate: WorkCandidate
    effect_class: str
    blocked: bool = False
    alternate_route_available: bool = False
    authority_proven: bool = False
    provider_readback_available: bool = False
    owner_choice_required: bool = False
    proof_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HeldLane:
    work_id: str
    state: str
    owner_interrupt_if_terminal: bool
    reason: str


@dataclass(frozen=True, slots=True)
class AutopilotOrchestrationDecision:
    state: str
    mission_id: str
    selected_work_id: str
    selected_objective: str
    squad_members: tuple[str, ...]
    held_lanes: tuple[HeldLane, ...]
    continue_without_owner: bool
    owner_interrupt_required: bool
    autopilot_state: str
    reason: str
    truth_boundary: str


class BubblesAutopilotOrchestrator:
    """Choose safe next work while preserving existing CFBE/Bubbles ownership."""

    def __init__(self, omega2: BubblesOmega2 | None = None) -> None:
        self.omega2 = omega2 or BubblesOmega2()

    @staticmethod
    def _policy(envelope: AutopilotWorkEnvelope) -> AutopilotDecision:
        return decide_autopilot(
            AutopilotStep(
                step_id=envelope.candidate.work_id,
                effect_class=envelope.effect_class,
                blocked=envelope.blocked,
                alternate_route_available=envelope.alternate_route_available,
                authority_proven=envelope.authority_proven,
                provider_readback_available=envelope.provider_readback_available,
                owner_choice_required=envelope.owner_choice_required,
                proof_refs=envelope.proof_refs,
            )
        )

    def choose_safe_next(
        self,
        envelopes: Iterable[AutopilotWorkEnvelope],
        *,
        manifest: MissionManifest,
        capability_constraints: Iterable[str] = (),
    ) -> AutopilotOrchestrationDecision:
        records = tuple(envelopes)
        by_id = {item.candidate.work_id: item for item in records}
        if len(by_id) != len(records):
            raise ValueError("AUTOPILOT_WORK_IDS_MUST_BE_UNIQUE")

        ranked = self.omega2.rank_work(
            (item.candidate for item in records),
            manifest,
        )
        held: list[HeldLane] = []

        for candidate in ranked:
            envelope = by_id[candidate.work_id]
            policy = self._policy(envelope)

            if policy.state == "ISOLATE_BLOCKED_LANE_AND_REROUTE":
                held.append(
                    HeldLane(
                        work_id=candidate.work_id,
                        state=policy.state,
                        owner_interrupt_if_terminal=False,
                        reason=policy.reason,
                    )
                )
                continue

            if not policy.continue_without_owner:
                held.append(
                    HeldLane(
                        work_id=candidate.work_id,
                        state=policy.state,
                        owner_interrupt_if_terminal=policy.owner_interrupt_required,
                        reason=policy.reason,
                    )
                )
                continue

            squad: SquadPlan = self.omega2.select_squad(
                mission_id=manifest.mission_id,
                required_disciplines=candidate.required_disciplines,
                proof_gaps=(candidate.proof_gap,),
                capability_constraints=capability_constraints,
            )
            return AutopilotOrchestrationDecision(
                state="SAFE_WORK_SELECTED",
                mission_id=manifest.mission_id,
                selected_work_id=candidate.work_id,
                selected_objective=candidate.objective,
                squad_members=squad.members,
                held_lanes=tuple(held),
                continue_without_owner=True,
                owner_interrupt_required=False,
                autopilot_state=policy.state,
                reason=(
                    "Highest-ranked work that passes the existing BubblesOmega2 and Creative Focus Shield gates was selected; held lanes remain isolated."
                ),
                truth_boundary=(
                    "Selection is an internal orchestration receipt, not tool execution, provider effect, background runtime, completion proof or owner-value proof."
                ),
            )

        if held:
            first = held[0]
            return AutopilotOrchestrationDecision(
                state="OWNER_GATE_REQUIRED",
                mission_id=manifest.mission_id,
                selected_work_id="",
                selected_objective="",
                squad_members=(),
                held_lanes=tuple(held),
                continue_without_owner=False,
                owner_interrupt_required=any(
                    item.owner_interrupt_if_terminal for item in held
                ),
                autopilot_state=first.state,
                reason=(
                    "All currently ranked executable lanes are held by autonomy/authority constraints; owner input is requested only because no safe lane remains."
                ),
                truth_boundary=(
                    "Owner escalation does not imply failure of blocked lanes and does not authorize any held external or high-consequence action."
                ),
            )

        return AutopilotOrchestrationDecision(
            state="NO_EXECUTABLE_WORK",
            mission_id=manifest.mission_id,
            selected_work_id="",
            selected_objective="",
            squad_members=(),
            held_lanes=(),
            continue_without_owner=False,
            owner_interrupt_required=False,
            autopilot_state="NO_EXECUTABLE_WORK",
            reason=(
                "BubblesOmega2 found no admitted non-duplicate, non-stale executable work candidate."
            ),
            truth_boundary=(
                "No executable work is not a completion claim; mission closure/proof must be evaluated separately."
            ),
        )


__all__ = [
    "AutopilotOrchestrationDecision",
    "AutopilotWorkEnvelope",
    "BubblesAutopilotOrchestrator",
    "HeldLane",
]
