from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .federation_evolution_program import EvolutionStage


class StrictMaturity(str, Enum):
    DESIGNED = "DESIGNED"
    FOUNDATION_ACTIVE = "FOUNDATION_ACTIVE"
    DETERMINISTIC_TESTED = "DETERMINISTIC_TESTED"
    SHADOW_VALIDATED = "SHADOW_VALIDATED"
    ADVERSARIALLY_VALIDATED = "ADVERSARIALLY_VALIDATED"
    CANARY_VALIDATED = "CANARY_VALIDATED"
    LIMITED_WORKFLOW_VERIFIED = "LIMITED_WORKFLOW_VERIFIED"
    CROSS_DOMAIN_VERIFIED = "CROSS_DOMAIN_VERIFIED"
    OPERATIONAL_VERIFIED = "OPERATIONAL_VERIFIED"
    ADAPTIVE_DOMINANCE_CANDIDATE = "ADAPTIVE_DOMINANCE_CANDIDATE"


@dataclass(frozen=True)
class MaturityProofEnvelope:
    deterministic_test_ref: str = ""
    shadow_validation_ref: str = ""
    adversarial_validation_ref: str = ""
    canary_validation_ref: str = ""
    limited_workflow_ref: str = ""
    cross_domain_ref: str = ""
    operational_readback_ref: str = ""
    provider_readback_ref: str = ""
    regression_ref: str = ""
    rollback_ref: str = ""
    critical_failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class StrictMaturityDecision:
    maturity: StrictMaturity
    blocked_by: tuple[str, ...]
    dominance_candidate: bool


class StrictMaturityGate:
    """Controlling maturity gate: stage count alone never proves maturity."""

    def classify(
        self,
        *,
        completed_through: EvolutionStage | None,
        proof: MaturityProofEnvelope,
    ) -> StrictMaturityDecision:
        if completed_through is None:
            return StrictMaturityDecision(StrictMaturity.DESIGNED, (), False)
        if proof.critical_failures:
            return StrictMaturityDecision(
                StrictMaturity.FOUNDATION_ACTIVE,
                ("CRITICAL_FAILURE_PRESENT",) + tuple(proof.critical_failures),
                False,
            )

        maturity = StrictMaturity.FOUNDATION_ACTIVE
        blocked: list[str] = []

        if completed_through >= EvolutionStage.SUCCESS_ROUTE_MEMORY:
            if proof.deterministic_test_ref:
                maturity = StrictMaturity.DETERMINISTIC_TESTED
            else:
                blocked.append("DETERMINISTIC_TEST_PROOF_REQUIRED")
                return StrictMaturityDecision(maturity, tuple(blocked), False)

        if completed_through >= EvolutionStage.NEGATIVE_PROOF_ENGINE:
            if proof.shadow_validation_ref:
                maturity = StrictMaturity.SHADOW_VALIDATED
            else:
                blocked.append("SHADOW_VALIDATION_REQUIRED")
                return StrictMaturityDecision(maturity, tuple(blocked), False)

        if completed_through >= EvolutionStage.MISSION_CONTINUATION_KERNEL:
            if proof.adversarial_validation_ref:
                maturity = StrictMaturity.ADVERSARIALLY_VALIDATED
            else:
                blocked.append("ADVERSARIAL_VALIDATION_REQUIRED")
                return StrictMaturityDecision(maturity, tuple(blocked), False)

        if completed_through >= EvolutionStage.EXECUTABLE_WORK_ZERO_ENGINE:
            if proof.canary_validation_ref:
                maturity = StrictMaturity.CANARY_VALIDATED
            else:
                blocked.append("CANARY_VALIDATION_REQUIRED")
                return StrictMaturityDecision(maturity, tuple(blocked), False)

        if completed_through >= EvolutionStage.CROSS_CHAT_RUNTIME_ATTESTATION:
            if proof.limited_workflow_ref:
                maturity = StrictMaturity.LIMITED_WORKFLOW_VERIFIED
            else:
                blocked.append("LIMITED_WORKFLOW_RUNTIME_ATTESTATION_REQUIRED")
                return StrictMaturityDecision(maturity, tuple(blocked), False)

        if completed_through >= EvolutionStage.EVOLUTION_GOVERNOR:
            if proof.cross_domain_ref and proof.regression_ref:
                maturity = StrictMaturity.CROSS_DOMAIN_VERIFIED
            else:
                if not proof.cross_domain_ref:
                    blocked.append("CROSS_DOMAIN_PROOF_REQUIRED")
                if not proof.regression_ref:
                    blocked.append("REGRESSION_PROOF_REQUIRED")
                return StrictMaturityDecision(maturity, tuple(blocked), False)

        if completed_through >= EvolutionStage.CAPABILITY_FORMATION_ENGINE:
            if proof.operational_readback_ref and proof.rollback_ref:
                maturity = StrictMaturity.OPERATIONAL_VERIFIED
            else:
                if not proof.operational_readback_ref:
                    blocked.append("OPERATIONAL_READBACK_REQUIRED")
                if not proof.rollback_ref:
                    blocked.append("ROLLBACK_PROOF_REQUIRED")
                return StrictMaturityDecision(maturity, tuple(blocked), False)

        dominance = False
        if completed_through >= EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER:
            if proof.provider_readback_ref and proof.regression_ref and proof.rollback_ref:
                maturity = StrictMaturity.ADAPTIVE_DOMINANCE_CANDIDATE
                dominance = True
            else:
                if not proof.provider_readback_ref:
                    blocked.append("PROVIDER_READBACK_REQUIRED_FOR_DOMINANCE")
                if not proof.regression_ref:
                    blocked.append("REGRESSION_PROOF_REQUIRED")
                if not proof.rollback_ref:
                    blocked.append("ROLLBACK_PROOF_REQUIRED")

        return StrictMaturityDecision(maturity, tuple(blocked), dominance)


__all__ = [
    "MaturityProofEnvelope",
    "StrictMaturity",
    "StrictMaturityDecision",
    "StrictMaturityGate",
]
