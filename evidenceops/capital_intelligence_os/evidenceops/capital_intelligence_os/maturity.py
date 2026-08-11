from __future__ import annotations

from dataclasses import dataclass
from .models import MaturityState

@dataclass
class MaturityEvidence:
    implementation_exists: bool = False
    tests_passed: bool = False
    acceptance_passed: bool = False
    independent_readback: bool = False
    runtime_receipt: bool = False
    health_verified: bool = False
    persistence_verified: bool = False
    rollback_verified: bool = False
    security_review_passed: bool = False

class MaturityGovernor:
    ORDER = list(MaturityState)
    def highest_proven(self, evidence: MaturityEvidence) -> MaturityState:
        state = MaturityState.DESIGNED
        if evidence.implementation_exists:
            state = MaturityState.IMPLEMENTED
        if evidence.implementation_exists and evidence.tests_passed:
            state = MaturityState.TESTED
        if evidence.implementation_exists and evidence.tests_passed and evidence.acceptance_passed and evidence.independent_readback:
            state = MaturityState.VERIFIED
        if state == MaturityState.VERIFIED and evidence.runtime_receipt and evidence.health_verified and evidence.persistence_verified and evidence.rollback_verified:
            state = MaturityState.DEPLOYED
        if state == MaturityState.DEPLOYED and evidence.security_review_passed:
            state = MaturityState.PRODUCTION_VERIFIED
        return state
    def assert_promotion(self, desired: MaturityState, evidence: MaturityEvidence) -> None:
        proven = self.highest_proven(evidence)
        if self.ORDER.index(desired) > self.ORDER.index(proven):
            raise ValueError(f"promotion blocked: desired={desired.value}, proven={proven.value}")
