"""CFBE Omega Input Compiler v2.

Thin adapter between ordinary owner language and Federation MissionIR/Bubbles.
It compiles intent; it does not schedule work, execute provider effects, grant
authority, or claim autonomous model retraining.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import re
from typing import Mapping

from federation.mission_ir import MissionIR


class IntentKind(str, Enum):
    CONTINUE = "CONTINUE"
    FIX = "FIX"
    IMPROVE = "IMPROVE"
    INVESTIGATE = "INVESTIGATE"
    BUILD = "BUILD"
    EXECUTE_ALL = "EXECUTE_ALL"
    CHALLENGE = "CHALLENGE"
    GENERAL = "GENERAL"


class ConfidenceBand(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True, slots=True)
class InputContext:
    """Verified context supplied by the caller; no hidden authority inference."""
    active_mission_id: str | None = None
    active_objective: str | None = None
    domain: str = "GENERAL"
    source_frontier: str = "CURRENT_VERIFIED_STATE"
    privacy_class: str = "INTERNAL"
    rights_state: str = "OWNER_CONTROLLED"
    current_blockers: tuple[str, ...] = ()
    known_constraints: tuple[str, ...] = ()
    preferred_behaviours: tuple[str, ...] = ()
    rejected_behaviours: tuple[str, ...] = ()
    available_capabilities: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IntentModel:
    raw_input: str
    normalized_input: str
    kind: IntentKind
    confidence: ConfidenceBand
    root_intent: str
    desired_result: str
    success_criteria: tuple[str, ...]
    assumptions: tuple[str, ...]
    owner_clarification_required: bool = False
    clarification_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CompiledMission:
    schema: str
    intent: IntentModel
    mission_ir: MissionIR
    capability_hints: tuple[str, ...]
    workstream_hints: tuple[str, ...]
    continuation_policy: str
    owner_burden_policy: str
    truth_boundary: tuple[str, ...]

    def digest(self) -> str:
        payload = "|".join((
            self.schema,
            self.intent.normalized_input,
            self.intent.kind.value,
            self.mission_ir.digest(),
            *self.capability_hints,
            *self.workstream_hints,
        ))
        return sha256(payload.encode("utf-8")).hexdigest()


_SHORTHAND = {
    "n": IntentKind.CONTINUE,
    "continue": IntentKind.CONTINUE,
    "fix": IntentKind.FIX,
    "better": IntentKind.IMPROVE,
    "improve": IntentKind.IMPROVE,
    "investigate": IntentKind.INVESTIGATE,
    "build": IntentKind.BUILD,
    "do all": IntentKind.EXECUTE_ALL,
    "is this the best": IntentKind.CHALLENGE,
    "is this best": IntentKind.CHALLENGE,
}

_HIGH_CONSEQUENCE_PATTERNS = (
    r"\bsend\b.*\b(email|mail|message)\b",
    r"\bpublish\b",
    r"\bfile\b.*\b(court|ccma|tribunal|regulator)\b",
    r"\bdelete\b",
    r"\bmerge\b.*\b(main|production|prod)\b",
    r"\bdeploy\b.*\b(production|prod|live)\b",
    r"\b(purchase|buy|pay|trade)\b",
    r"\b(iam|permission|credential|secret|billing)\b",
)

_BOUNDED_EFFECT_PATTERNS = (
    r"\bcreate\b.*\b(branch|draft|fixture|artifact)\b",
    r"\bupdate\b.*\b(internal|branch|draft)\b",
    r"\bcommit\b.*\b(branch)\b",
)

_CAPABILITY_KEYWORDS = (
    (("investigate", "evidence", "forensic", "search"), ("retrieval", "evidence", "contradiction-detection")),
    (("build", "code", "app", "system", "software"), ("architecture", "software", "testing")),
    (("fix", "bug", "broken", "error", "stall"), ("diagnostics", "recovery", "testing")),
    (("better", "improve", "optimize", "optimise", "best"), ("cfbe-benchmark", "challenger", "value-measurement")),
    (("document", "report", "submission", "letter"), ("document-analysis", "writing", "proof-review")),
    (("design", "visual", "brand", "creative"), ("creative", "design", "presentation")),
    (("deploy", "provider", "runtime", "cloud"), ("deployment", "provider-routing", "readback")),
)

_WORKSTREAMS = {
    IntentKind.CONTINUE: ("recover-current-state", "choose-highest-value-safe-path", "execute-and-verify"),
    IntentKind.FIX: ("preserve-evidence", "diagnose-root-cause", "minimum-safe-repair", "regression-test", "prevent-recurrence"),
    IntentKind.IMPROVE: ("baseline-incumbent", "benchmark-challengers", "implement-material-improvement", "measure-regression-and-value"),
    IntentKind.INVESTIGATE: ("define-evidence-frontier", "retrieve-sources", "build-timeline-or-model", "challenge-alternatives", "report-confidence-and-gaps"),
    IntentKind.BUILD: ("compile-requirements", "reuse-before-build", "implement", "test", "verify-deliverable"),
    IntentKind.EXECUTE_ALL: ("recover-current-state", "dependency-order-safe-work", "parallelize-independent-lanes", "verify-terminal-state"),
    IntentKind.CHALLENGE: ("baseline-incumbent", "generate-alternatives", "cfbe-challenge", "select-proof-adjusted-route"),
    IntentKind.GENERAL: ("model-intent", "discover-capabilities", "compile-best-route", "execute-and-verify"),
}


def _norm(text: str) -> str:
    return " ".join(str(text).strip().split())


def _classify(text: str) -> tuple[IntentKind, ConfidenceBand]:
    lowered = text.casefold().strip(" ?.!:")
    if lowered in _SHORTHAND:
        return _SHORTHAND[lowered], ConfidenceBand.HIGH
    if lowered.startswith(("fix ", "repair ", "resolve ")):
        return IntentKind.FIX, ConfidenceBand.HIGH
    if lowered.startswith(("improve ", "optimize ", "optimise ", "make this better", "make it better")):
        return IntentKind.IMPROVE, ConfidenceBand.HIGH
    if lowered.startswith(("investigate ", "research ", "look into ", "find out ")):
        return IntentKind.INVESTIGATE, ConfidenceBand.HIGH
    if lowered.startswith(("build ", "create ", "develop ", "implement ")):
        return IntentKind.BUILD, ConfidenceBand.MEDIUM
    if "is this the best" in lowered or "best and most powerful" in lowered:
        return IntentKind.CHALLENGE, ConfidenceBand.HIGH
    if lowered.startswith("do all"):
        return IntentKind.EXECUTE_ALL, ConfidenceBand.HIGH
    return IntentKind.GENERAL, ConfidenceBand.MEDIUM


def _target_after_command(text: str) -> str:
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) == 2 else ""


def _intent_text(kind: IntentKind, text: str, context: InputContext):
    target = _target_after_command(text)
    active = _norm(context.active_objective or "")
    assumptions: list[str] = []
    if kind == IntentKind.CONTINUE:
        root = active or "Continue the active mission from its latest verified state."
        desired = "Advance the highest-value safe executable pathway without restating unchanged status."
        criteria = ("current state recovered", "highest-value executable path advanced", "claims match proof")
        if not active:
            assumptions.append("No active objective was supplied; continuation is bounded to verified caller context.")
        return root, desired, criteria, tuple(assumptions)
    if kind == IntentKind.FIX:
        subject = target or active or "the identified problem"
        return (f"Restore {subject} to a correct, stable state.", f"Diagnose the root cause, apply the minimum safe repair, verify it, and reduce recurrence risk for {subject}.", ("root cause identified", "minimum safe repair applied or specified", "regression proof obtained", "recurrence control considered"), tuple(assumptions))
    if kind == IntentKind.IMPROVE:
        subject = target or active or "the current solution"
        return (f"Materially improve {subject}.", f"Challenge the incumbent, benchmark stronger routes, and retain only improvements that increase proof-adjusted value for {subject}.", ("incumbent baselined", "credible challengers considered", "material improvement demonstrated", "critical regressions absent"), tuple(assumptions))
    if kind == IntentKind.INVESTIGATE:
        subject = target or active or "the stated matter"
        return (f"Establish the best-supported truth about {subject}.", f"Run an evidence-first investigation of {subject}, test alternative explanations, and report findings with provenance and confidence.", ("source frontier identified", "material evidence reviewed", "alternatives challenged", "gaps and confidence explicit"), tuple(assumptions))
    if kind == IntentKind.BUILD:
        subject = target or active or "the requested capability"
        return (f"Turn the owner's desired outcome into a usable implementation for {subject}.", f"Supply missing expert design work, reuse existing Federation capabilities first, build the smallest sufficient solution, test it, and verify the deliverable for {subject}.", ("requirements inferred safely", "reuse checked", "implementation produced", "tests or validation completed", "maturity honestly classified"), tuple(assumptions))
    if kind == IntentKind.EXECUTE_ALL:
        root = active or "Complete all currently known work needed for the stated objective."
        return (root, "Execute all safe, authorized, materially useful work in dependency-optimal order while isolating genuine blockers.", ("safe work exhausted", "dependencies respected", "blocked lanes isolated", "terminal state and remaining gates explicit"), tuple(assumptions))
    if kind == IntentKind.CHALLENGE:
        subject = active or text
        return (f"Determine whether the current approach for {subject} is actually the strongest available.", "Benchmark the incumbent against materially different alternatives and choose the highest proof-adjusted value route.", ("incumbent weaknesses explicit", "alternatives compared", "proof/value gates applied", "best current route identified without overclaim"), tuple(assumptions))
    return (text, f"Achieve the practical result implied by: {text}", ("desired outcome preserved", "missing technical expertise supplied", "best safe route selected", "result verified where possible"), tuple(assumptions))


def _effect_policy(text: str) -> tuple[str, bool, tuple[str, ...]]:
    lowered = text.casefold()
    if any(re.search(pattern, lowered) for pattern in _HIGH_CONSEQUENCE_PATTERNS):
        return "CONSEQUENTIAL_EFFECT", True, ("explicit_owner_authority_for_exact_effect", "provider_or_receiver_readback")
    if any(re.search(pattern, lowered) for pattern in _BOUNDED_EFFECT_PATTERNS):
        return "BOUNDED_EFFECT", False, ("existing_bounded_route_authority",)
    return "NO_EFFECT", False, ()


def _capability_hints(text: str, context: InputContext, kind: IntentKind) -> tuple[str, ...]:
    lowered = text.casefold()
    hints = {"bubbles-orchestration", "mission-ir", "proofos"}
    if kind in {IntentKind.IMPROVE, IntentKind.CHALLENGE}:
        hints.add("cfbe-omega")
    if kind in {IntentKind.FIX, IntentKind.CONTINUE, IntentKind.EXECUTE_ALL}:
        hints.add("recovery-and-state")
    for keywords, capabilities in _CAPABILITY_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            hints.update(capabilities)
    hints.update(item.strip() for item in context.available_capabilities if item.strip())
    return tuple(sorted(hints))


def compile_owner_input(raw_input: str, context: InputContext | None = None) -> CompiledMission:
    """Compile ordinary owner language into a validated Federation MissionIR."""
    context = context or InputContext()
    text = _norm(raw_input)
    if not text:
        raise ValueError("CFBE_INPUT_REQUIRED")
    kind, confidence = _classify(text)
    root, desired, criteria, assumptions = _intent_text(kind, text, context)
    effect_class, owner_approval, authority_requirements = _effect_policy(text)
    clarification_required = kind == IntentKind.CONTINUE and not context.active_objective and not context.active_mission_id
    clarification_reason = "CONTINUATION_HAS_NO_VERIFIED_ACTIVE_MISSION" if clarification_required else None
    mission_id = context.active_mission_id
    if not mission_id:
        mission_id = f"CFBE-INPUT-{sha256(text.casefold().encode('utf-8')).hexdigest()[:12]}"
    intent = IntentModel(raw_input=raw_input, normalized_input=text, kind=kind, confidence=confidence, root_intent=root, desired_result=desired, success_criteria=criteria, assumptions=assumptions, owner_clarification_required=clarification_required, clarification_reason=clarification_reason)
    proof_requirements = ("claim_state_matches_observed_maturity", "source_or_artifact_provenance", "terminal_result_or_blocker_explicit")
    if effect_class != "NO_EFFECT":
        proof_requirements += ("receiver_specific_readback",)
    mission_ir = MissionIR(
        mission_id=mission_id,
        objective=root,
        domain=context.domain,
        outcome_contract=desired,
        source_frontier=context.source_frontier,
        privacy_class=context.privacy_class,
        rights_state=context.rights_state,
        effect_class=effect_class,
        owner_approval_required=owner_approval,
        rollback_required=effect_class != "NO_EFFECT",
        authority_requirements=authority_requirements,
        proof_requirements=proof_requirements,
        value_metrics=("accepted_outcome_quality", "owner_burden", "cycle_time", "proof_completeness"),
        metadata={
            **{str(k): str(v) for k, v in context.metadata.items()},
            "compiler": "CFBE-OMEGA-INPUT-COMPILER-V2",
            "intent_kind": kind.value,
            "intent_confidence": confidence.value,
            "owner_clarification_required": str(clarification_required).lower(),
            "known_constraints": "; ".join(context.known_constraints),
            "current_blockers": "; ".join(context.current_blockers),
            "preferred_behaviours": "; ".join(context.preferred_behaviours),
            "rejected_behaviours": "; ".join(context.rejected_behaviours),
        },
    ).normalized()
    mission_ir.validate()
    return CompiledMission(
        schema="CFBE-OMEGA-INPUT-COMPILER-V2",
        intent=intent,
        mission_ir=mission_ir,
        capability_hints=_capability_hints(text, context, kind),
        workstream_hints=_WORKSTREAMS[kind],
        continuation_policy="INFER_SAFELY_COMPILE_EXECUTE; ASK_ONLY_FOR_MATERIAL_AMBIGUITY_OR_AUTHORITY",
        owner_burden_policy="NO_AVOIDABLE_OWNER_WORK",
        truth_boundary=(
            "compiler_does_not_grant_provider_authority",
            "compiler_does_not_execute_or_schedule_work",
            "compiler_does_not_claim_autonomous_model_retraining",
            "downstream_effects_remain_route_and_receiver_gated",
        ),
    )
