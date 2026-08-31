"""CFBE Omega Input Compiler v2.1 challenger.

This is a narrow intent-fidelity challenger over the admitted v2 compiler. It
adds natural-language intent families and expert capability hints only. It does
not add scheduling, execution, authority, provider access, or model retraining.
"""
from __future__ import annotations

from dataclasses import replace
import re

from federation.cfbe_input_compiler_v2 import (
    CompiledMission,
    ConfidenceBand,
    InputContext,
    IntentKind,
    _WORKSTREAMS,
    _capability_hints,
    _intent_text,
    _norm,
    compile_owner_input,
)


_IMPROVE_PATTERNS = (
    r"^make (this|it) (more )?(powerful|capable|efficient|effective|intelligent|robust)\b",
    r"^hyper[- ]?(optimize|optimise)\b",
    r"^(strengthen|upgrade|enhance)\b",
)
_INVESTIGATE_PATTERNS = (
    r"^audit\b",
    r"\bto audit\b",
    r"^what happened\b",
    r"^why (is|are|did|does|has|have)\b",
    r"^diagnose\b",
)
_BUILD_PATTERNS = (
    r"^(design|architect|scaffold)\b",
    r"^design and deploy\b",
)
_BOUNDED_DEPLOY_PATTERNS = (
    r"\bdeploy\b.*\b(internal|sandbox|staging|test|bounded)\b",
)


def _matches(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _challenger_kind(text: str, incumbent: IntentKind) -> tuple[IntentKind, ConfidenceBand]:
    if incumbent is not IntentKind.GENERAL:
        return incumbent, ConfidenceBand.HIGH
    lowered = text.casefold().strip(" ?.!:")
    if _matches(_IMPROVE_PATTERNS, lowered):
        return IntentKind.IMPROVE, ConfidenceBand.HIGH
    if _matches(_INVESTIGATE_PATTERNS, lowered):
        return IntentKind.INVESTIGATE, ConfidenceBand.HIGH
    if _matches(_BUILD_PATTERNS, lowered):
        return IntentKind.BUILD, ConfidenceBand.HIGH
    return incumbent, ConfidenceBand.MEDIUM


def _augment_hints(text: str, context: InputContext, kind: IntentKind) -> tuple[str, ...]:
    hints = set(_capability_hints(text, context, kind))
    if kind is IntentKind.INVESTIGATE:
        hints.update(("retrieval", "evidence", "contradiction-detection"))
    if kind is IntentKind.IMPROVE:
        hints.update(("cfbe-benchmark", "challenger", "value-measurement"))
    if kind is IntentKind.BUILD:
        hints.update(("architecture", "software", "testing"))
    if "deploy" in text.casefold():
        hints.update(("deployment", "provider-routing", "readback"))
    return tuple(sorted(hints))


def compile_owner_input_v21(raw_input: str, context: InputContext | None = None) -> CompiledMission:
    context = context or InputContext()
    text = _norm(raw_input)
    incumbent = compile_owner_input(raw_input, context)
    kind, confidence = _challenger_kind(text, incumbent.intent.kind)

    effect_class = incumbent.mission_ir.effect_class
    owner_approval = incumbent.mission_ir.owner_approval_required
    authority_requirements = incumbent.mission_ir.authority_requirements
    if effect_class == "NO_EFFECT" and _matches(_BOUNDED_DEPLOY_PATTERNS, text.casefold()):
        effect_class = "BOUNDED_EFFECT"
        owner_approval = False
        authority_requirements = ("existing_bounded_route_authority",)

    if kind is incumbent.intent.kind and effect_class == incumbent.mission_ir.effect_class:
        return replace(incumbent, capability_hints=_augment_hints(text, context, kind))

    root, desired, criteria, assumptions = _intent_text(kind, text, context)
    intent = replace(
        incumbent.intent,
        kind=kind,
        confidence=confidence,
        root_intent=root,
        desired_result=desired,
        success_criteria=criteria,
        assumptions=assumptions,
    )
    metadata = dict(incumbent.mission_ir.metadata)
    metadata.update({
        "compiler": "CFBE-OMEGA-INPUT-COMPILER-V2.1-CHALLENGER",
        "intent_kind": kind.value,
        "intent_confidence": confidence.value,
    })
    proof_requirements = tuple(incumbent.mission_ir.proof_requirements)
    if effect_class != "NO_EFFECT" and "receiver_specific_readback" not in proof_requirements:
        proof_requirements += ("receiver_specific_readback",)
    mission_ir = replace(
        incumbent.mission_ir,
        objective=root,
        outcome_contract=desired,
        effect_class=effect_class,
        owner_approval_required=owner_approval,
        rollback_required=effect_class != "NO_EFFECT",
        authority_requirements=authority_requirements,
        proof_requirements=proof_requirements,
        metadata=metadata,
    ).normalized()
    mission_ir.validate()
    return replace(
        incumbent,
        intent=intent,
        mission_ir=mission_ir,
        capability_hints=_augment_hints(text, context, kind),
        workstream_hints=_WORKSTREAMS[kind],
    )
