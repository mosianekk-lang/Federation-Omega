from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from evidenceops.caseforge.capability_decision import (
    CapabilityDecision,
    CapabilityDecisionRequest,
    CapabilityResolutionGate,
    GateDecision,
)
from evidenceops.caseforge.scientia import Hypothesis, ScientificObservation, ScientiaKernel
from evidenceops.truthgrid.vnext import CompletionVector, DecisionReadiness

from .lex_omega import MaturityLevel, ReleaseState


class MainlineMaturityStage(str, Enum):
    """Current EvidenceOps/CASEFORGE-compatible maturity vocabulary.

    This does not silently promote legacy LEX-OMEGA maturity. It provides a
    common vocabulary for current-mainline alignment and preserves the extra
    adversarial/cross-domain stages introduced by CASEFORGE.
    """

    DESIGNED = "DESIGNED"
    DETERMINISTIC_TESTED = "DETERMINISTIC_TESTED"
    SHADOW_VALIDATED = "SHADOW_VALIDATED"
    ADVERSARIALLY_VALIDATED = "ADVERSARIALLY_VALIDATED"
    CANARY_VALIDATED = "CANARY_VALIDATED"
    LIMITED_WORKFLOW_VERIFIED = "LIMITED_WORKFLOW_VERIFIED"
    CROSS_DOMAIN_VERIFIED = "CROSS_DOMAIN_VERIFIED"
    OPERATIONAL_VERIFIED = "OPERATIONAL_VERIFIED"


LEGACY_MATURITY_MAP = {
    MaturityLevel.DESIGN_ONLY: MainlineMaturityStage.DESIGNED,
    MaturityLevel.DETERMINISTIC_TESTED: MainlineMaturityStage.DETERMINISTIC_TESTED,
    MaturityLevel.SHADOW_VALIDATED: MainlineMaturityStage.SHADOW_VALIDATED,
    MaturityLevel.CANARY_VALIDATED: MainlineMaturityStage.CANARY_VALIDATED,
    MaturityLevel.WORKFLOW_VERIFIED: MainlineMaturityStage.LIMITED_WORKFLOW_VERIFIED,
    MaturityLevel.OPERATIONAL_VERIFIED: MainlineMaturityStage.OPERATIONAL_VERIFIED,
}


@dataclass(frozen=True)
class EvidenceOpsLegalAlignmentResult:
    legal_release_state: ReleaseState
    truthgrid_readiness: str
    scientia_status: str
    terminal_claim_allowed: bool
    capability_decision: CapabilityDecision | None
    evolution_promotion_allowed: bool
    blind_validation_state: str
    reason_codes: tuple[str, ...]
    mainline_alignment: str = "EVIDENCEOPS_CURRENT_MAINLINE_2026_08_11"


class EvidenceOpsLegalAlignmentGate:
    """Bind LEX-OMEGA/JFRIE to the current EvidenceOps assurance stack.

    Responsibilities stay separated:
      * TruthGrid vNext controls evidentiary finality / decision readiness.
      * LEX-OMEGA supplies specialist legal and forensic reasoning.
      * JFRIE remains the fail-closed jurisdiction/evidence/release gate.
      * CASEFORGE/SCIENTIA supplies falsification and evolution assurance.
      * CapabilityResolutionGate controls terminal CAN/CANNOT/DONE claims.

    The adapter does not duplicate those engines and does not expand authority.
    """

    PASSING_JFRIE_STATES = {"PASS", "PASS_WITH_LIMITATIONS"}

    def __init__(self) -> None:
        self.scientia = ScientiaKernel()
        self.capability_gate = CapabilityResolutionGate()

    @staticmethod
    def map_legacy_maturity(level: MaturityLevel) -> MainlineMaturityStage:
        return LEGACY_MATURITY_MAP[level]

    def evaluate(
        self,
        *,
        jfrie_status: str,
        truthgrid_completion: CompletionVector | None = None,
        require_truthgrid: bool = False,
        observations: Sequence[ScientificObservation] = (),
        hypotheses: Sequence[Hypothesis] = (),
        require_scientia: bool = False,
        capability_request: CapabilityDecisionRequest | None = None,
        require_provider_blind: bool = False,
        blind_execution_state: str = "",
        blind_provider_readback_ref: str = "",
    ) -> EvidenceOpsLegalAlignmentResult:
        reasons: list[str] = []

        capability_decision: CapabilityDecision | None = None
        terminal_claim_allowed = True
        if capability_request is not None:
            capability_decision = self.capability_gate.evaluate(capability_request)
            terminal_claim_allowed = capability_decision.decision is GateDecision.ALLOW_BOUNDED
            if not terminal_claim_allowed:
                reasons.extend(capability_decision.reason_codes)

        truthgrid_readiness = "NOT_REQUIRED"
        if truthgrid_completion is not None:
            truthgrid_readiness = truthgrid_completion.decision_readiness().value
        elif require_truthgrid:
            truthgrid_readiness = "MISSING"
            reasons.append("TRUTHGRID_COMPLETION_VECTOR_REQUIRED")

        scientia_status = "NOT_REQUIRED"
        scientia_valid = True
        if require_scientia:
            try:
                design = self.scientia.validate_case_design(
                    observations=observations,
                    hypotheses=hypotheses,
                    require_competing_hypothesis=True,
                )
                scientia_status = str(design["status"])
            except ValueError as exc:
                scientia_valid = False
                scientia_status = "SCIENTIFIC_DESIGN_INVALID"
                reasons.append(f"SCIENTIA:{exc}")

        blind_validation_state = "NOT_REQUIRED"
        blind_valid = True
        if require_provider_blind:
            if blind_execution_state == "PROVIDER_VERIFIED" and blind_provider_readback_ref.strip():
                blind_validation_state = "PROVIDER_VERIFIED"
            else:
                blind_valid = False
                blind_validation_state = "PROVIDER_BLIND_READBACK_REQUIRED"
                reasons.append("BLIND_PROVIDER_READBACK_REQUIRED")

        if jfrie_status not in self.PASSING_JFRIE_STATES:
            legal_release = ReleaseState.DO_NOT_FILE
            reasons.append("JFRIE_FAIL_CLOSED")
        elif require_scientia and not scientia_valid:
            legal_release = ReleaseState.LEGAL_RESEARCH_REQUIRED
        elif require_truthgrid and truthgrid_completion is None:
            legal_release = ReleaseState.HOLD_FOR_SOURCE
        elif truthgrid_completion is not None and truthgrid_completion.decision_readiness() is DecisionReadiness.NOT_READY:
            legal_release = ReleaseState.HOLD_FOR_SOURCE
            reasons.append("TRUTHGRID_NOT_READY")
        elif (
            jfrie_status == "PASS_WITH_LIMITATIONS"
            or (
                truthgrid_completion is not None
                and truthgrid_completion.decision_readiness() is DecisionReadiness.CONDITIONAL
            )
        ):
            legal_release = ReleaseState.PASS_WITH_LIMITATIONS
        else:
            legal_release = ReleaseState.PASS

        evolution_promotion_allowed = (
            jfrie_status in self.PASSING_JFRIE_STATES
            and (not require_truthgrid or truthgrid_readiness == DecisionReadiness.READY.value)
            and (not require_scientia or scientia_valid)
            and (not require_provider_blind or blind_valid)
        )
        if not evolution_promotion_allowed:
            reasons.append("EVOLUTION_PROMOTION_NOT_PROVEN")

        return EvidenceOpsLegalAlignmentResult(
            legal_release_state=legal_release,
            truthgrid_readiness=truthgrid_readiness,
            scientia_status=scientia_status,
            terminal_claim_allowed=terminal_claim_allowed,
            capability_decision=capability_decision,
            evolution_promotion_allowed=evolution_promotion_allowed,
            blind_validation_state=blind_validation_state,
            reason_codes=tuple(dict.fromkeys(reasons)),
        )


__all__ = [
    "EvidenceOpsLegalAlignmentGate",
    "EvidenceOpsLegalAlignmentResult",
    "LEGACY_MATURITY_MAP",
    "MainlineMaturityStage",
]
