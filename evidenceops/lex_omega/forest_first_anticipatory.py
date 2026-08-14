from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Sequence, Tuple


class NeedClass(str, Enum):
    RISK = "RISK"
    DEADLINE = "DEADLINE"
    EVIDENCE = "EVIDENCE"
    CONTINUITY = "CONTINUITY"
    UNDERSTANDING = "UNDERSTANDING"
    QUALITY = "QUALITY"
    AUTOMATION = "AUTOMATION"
    LEARNING = "LEARNING"
    OPPORTUNITY = "OPPORTUNITY"


class ActionClass(str, Enum):
    AUTO_SAFE_INTERNAL = "AUTO_SAFE_INTERNAL"
    PREPARE_AND_HOLD = "PREPARE_AND_HOLD"
    OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"
    OBSERVE = "OBSERVE"


@dataclass(frozen=True)
class AnticipatoryCue:
    need_class: NeedClass
    description: str
    recommended_action: str
    action_class: ActionClass
    priority: int
    reversible: bool = True
    trigger_refs: Tuple[str, ...] = ()
    user_interrupt_required: bool = False

    @property
    def cue_id(self) -> str:
        payload = "|".join(
            (
                self.need_class.value,
                self.description.strip().casefold(),
                self.recommended_action.strip().casefold(),
                self.action_class.value,
            )
        )
        return f"FF-CUE-{sha256(payload.encode('utf-8')).hexdigest()[:16]}"


@dataclass(frozen=True)
class AnticipatoryContext:
    high_stakes: bool = False
    credible_risk_signal_present: bool = False
    consequential_action_planned: bool = False
    legal_route_complete: bool = True
    teach_back_complete: bool = True
    jfrie_bound: bool = True
    deadline_state_verified: bool = True
    evidence_preservation_current: bool = True
    continuity_checkpoint_current: bool = True
    best_current_version_gate_passed: bool = True
    repeated_failure_detected: bool = False
    material_user_correction_received: bool = False
    avoidable_manual_user_work_detected: bool = False
    reusable_lesson_candidate_present: bool = False
    provider_readback_required_but_missing: bool = False
    trigger_refs: Tuple[str, ...] = ()


@dataclass(frozen=True)
class AnticipatoryReport:
    cues: Tuple[AnticipatoryCue, ...]
    automatic_actions: Tuple[str, ...]
    owner_decisions: Tuple[str, ...]
    quiet_when_healthy: bool
    user_interrupt_required: bool

    @property
    def highest_priority(self) -> int:
        return max((cue.priority for cue in self.cues), default=0)


class ForestFirstAnticipatoryEngine:
    """Convert likely future needs into bounded proactive actions.

    The engine is intentionally rule-based and transparent. It does not claim
    to predict human behaviour or legal outcomes. It asks whether a known
    high-value protection, verification, continuity, quality or learning step
    should be initiated before the user has to discover the need manually.

    Safe/reversible internal actions can be prepared automatically. External or
    consequential effects remain separately authority-gated.
    """

    def evaluate(self, context: AnticipatoryContext) -> AnticipatoryReport:
        cues: list[AnticipatoryCue] = []
        refs = context.trigger_refs

        if context.credible_risk_signal_present:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.RISK,
                    description="A credible risk signal is present before full proof of the feared event.",
                    recommended_action=(
                        "Enter protective readiness: preserve relevant records, identify deadlines, "
                        "model competing explanations and prepare reversible safeguards."
                    ),
                    action_class=ActionClass.AUTO_SAFE_INTERNAL,
                    priority=5 if context.high_stakes else 4,
                    trigger_refs=refs,
                )
            )

        if context.high_stakes and not context.deadline_state_verified:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.DEADLINE,
                    description="A high-stakes matter has an unverified deadline state.",
                    recommended_action="Verify accrual/service/deadline dates and protect the earliest defensible deadline.",
                    action_class=ActionClass.AUTO_SAFE_INTERNAL,
                    priority=5,
                    trigger_refs=refs,
                )
            )

        if context.high_stakes and not context.evidence_preservation_current:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.EVIDENCE,
                    description="Evidence preservation is not current for a high-stakes matter.",
                    recommended_action="Identify material records at risk and prepare the minimum lawful preservation action.",
                    action_class=ActionClass.AUTO_SAFE_INTERNAL,
                    priority=5,
                    trigger_refs=refs,
                )
            )

        if context.consequential_action_planned and not context.legal_route_complete:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.QUALITY,
                    description="A consequential action is contemplated without a complete Legal Route Card.",
                    recommended_action="Build/repair the Legal Route Card before release.",
                    action_class=ActionClass.PREPARE_AND_HOLD,
                    priority=5,
                    trigger_refs=refs,
                )
            )

        if context.high_stakes and not context.jfrie_bound:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.QUALITY,
                    description="JFRIE is not bound to the high-stakes release path.",
                    recommended_action="Bind JFRIE and fail closed on filing/readiness until the gate passes.",
                    action_class=ActionClass.PREPARE_AND_HOLD,
                    priority=5,
                    trigger_refs=refs,
                )
            )

        if context.consequential_action_planned and not context.teach_back_complete:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.UNDERSTANDING,
                    description="The user cannot yet teach back the consequential position in plain language.",
                    recommended_action="Explain the material position, consequences and opposing use before release.",
                    action_class=ActionClass.OWNER_DECISION_REQUIRED,
                    priority=5,
                    trigger_refs=refs,
                    user_interrupt_required=True,
                )
            )

        if not context.continuity_checkpoint_current:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.CONTINUITY,
                    description="Material work has advanced beyond the latest durable continuity checkpoint.",
                    recommended_action="Refresh the canonical checkpoint and verify readback before context loss.",
                    action_class=ActionClass.AUTO_SAFE_INTERNAL,
                    priority=4,
                    trigger_refs=refs,
                )
            )

        if not context.best_current_version_gate_passed:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.QUALITY,
                    description="A substantive artefact has not passed the Best Current Verified Version gate.",
                    recommended_action=(
                        "Run objective-fidelity, reuse, architecture, adversarial, continuity, truth, automation, "
                        "simplicity, rollback and extensibility checks before calling it ready."
                    ),
                    action_class=ActionClass.AUTO_SAFE_INTERNAL,
                    priority=4,
                    trigger_refs=refs,
                )
            )

        if context.repeated_failure_detected:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.AUTOMATION,
                    description="A repeated failure fingerprint has been detected.",
                    recommended_action=(
                        "Stop unchanged retries, preserve failure evidence, open/update the engineering build, "
                        "select a materially different route and bind a regression after recovery."
                    ),
                    action_class=ActionClass.AUTO_SAFE_INTERNAL,
                    priority=4,
                    trigger_refs=refs,
                )
            )

        if context.material_user_correction_received:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.LEARNING,
                    description="A material user correction may represent a reusable failure mode.",
                    recommended_action=(
                        "Preserve the superseded position, verify the correction, create a regression candidate "
                        "and promote only after evidence/adversarial testing."
                    ),
                    action_class=ActionClass.AUTO_SAFE_INTERNAL,
                    priority=4,
                    trigger_refs=refs,
                )
            )

        if context.avoidable_manual_user_work_detected:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.AUTOMATION,
                    description="The user is being asked to perform work that may be safely automatable.",
                    recommended_action="Search authorised capabilities and automate the repeatable low-risk portion before handing work back.",
                    action_class=ActionClass.AUTO_SAFE_INTERNAL,
                    priority=3,
                    trigger_refs=refs,
                )
            )

        if context.reusable_lesson_candidate_present:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.OPPORTUNITY,
                    description="A case-specific lesson may have wider reusable value.",
                    recommended_action="Abstract a de-identified lesson candidate and route it through the governed learning/maturity pipeline.",
                    action_class=ActionClass.AUTO_SAFE_INTERNAL,
                    priority=2,
                    trigger_refs=refs,
                )
            )

        if context.provider_readback_required_but_missing:
            cues.append(
                AnticipatoryCue(
                    need_class=NeedClass.QUALITY,
                    description="A runtime/provider-effect claim lacks required provider readback.",
                    recommended_action="Hold the terminal claim and obtain exact target/provider readback before promotion.",
                    action_class=ActionClass.PREPARE_AND_HOLD,
                    priority=5,
                    trigger_refs=refs,
                )
            )

        cues.sort(key=lambda cue: (-cue.priority, cue.need_class.value, cue.cue_id))
        automatic_actions = tuple(
            cue.recommended_action
            for cue in cues
            if cue.action_class is ActionClass.AUTO_SAFE_INTERNAL
        )
        owner_decisions = tuple(
            cue.recommended_action
            for cue in cues
            if cue.action_class is ActionClass.OWNER_DECISION_REQUIRED
        )
        return AnticipatoryReport(
            cues=tuple(cues),
            automatic_actions=automatic_actions,
            owner_decisions=owner_decisions,
            quiet_when_healthy=not cues,
            user_interrupt_required=any(cue.user_interrupt_required for cue in cues),
        )


__all__ = [
    "ActionClass",
    "AnticipatoryContext",
    "AnticipatoryCue",
    "AnticipatoryReport",
    "ForestFirstAnticipatoryEngine",
    "NeedClass",
]
