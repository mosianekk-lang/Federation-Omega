"""Formation-Omega deterministic convergence and release-gate primitives.

This module is intentionally provider-agnostic and A1_INTERNAL. It encodes
public-safe semantics only. It does not grant credentials, provider authority,
legal filing authority, or external-effect permission.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable, Mapping, Sequence


class ProofState(IntEnum):
    """Ordered claim ceiling. Higher values require stronger proof."""

    UNVERIFIED = 0
    INFERENCE = 1
    CONTESTED = 2
    SUPPORTED = 3
    VERIFIED = 4
    DISPROVED = 5


@dataclass(frozen=True)
class ClaimDecision:
    requested: ProofState
    evidence_ceiling: ProofState
    permitted: ProofState
    downgraded: bool
    reason: str


@dataclass(frozen=True)
class SurfaceReadback:
    surface: str
    expected_semantics: str
    observed_semantics: str | None
    authority_verified: bool
    target_verified: bool
    version_verified: bool
    rollback_ready: bool = False

    @property
    def semantically_verified(self) -> bool:
        return (
            self.observed_semantics is not None
            and self.observed_semantics == self.expected_semantics
            and self.authority_verified
            and self.target_verified
            and self.version_verified
        )


@dataclass(frozen=True)
class ReleaseGate:
    proof_ok: bool
    legal_accuracy_ok: bool
    privacy_ok: bool
    target_authority_ok: bool
    version_ok: bool
    semantic_readback_ok: bool
    rollback_ok: bool
    owner_approval_required: bool = False
    owner_approved: bool = False

    @property
    def passed(self) -> bool:
        owner_ok = (not self.owner_approval_required) or self.owner_approved
        return all(
            (
                self.proof_ok,
                self.legal_accuracy_ok,
                self.privacy_ok,
                self.target_authority_ok,
                self.version_ok,
                self.semantic_readback_ok,
                self.rollback_ok,
                owner_ok,
            )
        )


class FormationOmega:
    """Public-safe convergence policy implementation.

    The class enforces the lowest-proven-state rule and cross-surface readback
    boundaries. It never infers effect authority from documentation or from a
    different surface.
    """

    PRECEDENCE: Sequence[str] = (
        "NATIVE_AUTHENTICATED_SOURCE",
        "EVIDENCEOPS_PROOF_STATE",
        "CURRENT_FORMATION_MASTER",
        "LEXAZANIA_LEGAL_ADVERSARIAL_COUNSEL",
        "SUPERIOR_LOGIC_REASONING",
        "SOVARA_ORCHESTRATION",
        "CFBE_BENCHMARK",
        "JARVIS_ASSURANCE",
        "SENTINEL_OBSERVABILITY",
        "REGISTERED_SPECIALIST_NODES",
    )

    LEGACY_COUNSEL_STATES = frozenset(
        {"LEGAL_VULNERABILITY", "ADVERSARIAL_HYPOTHESIS", "HISTORICAL_WORK_PRODUCT"}
    )

    @classmethod
    def claim_decision(
        cls, requested: ProofState, evidence_ceiling: ProofState
    ) -> ClaimDecision:
        """Return the strongest permitted non-disproof claim state.

        DISPROVED is special: it may only be requested when the evidence ceiling
        itself is DISPROVED. Otherwise the claim is capped at the evidence state.
        """

        if requested == ProofState.DISPROVED and evidence_ceiling != ProofState.DISPROVED:
            permitted = min(evidence_ceiling, ProofState.VERIFIED)
            return ClaimDecision(
                requested=requested,
                evidence_ceiling=evidence_ceiling,
                permitted=ProofState(permitted),
                downgraded=True,
                reason="DISPROVED requires direct stronger contradiction evidence.",
            )

        permitted = ProofState(min(int(requested), int(evidence_ceiling)))
        return ClaimDecision(
            requested=requested,
            evidence_ceiling=evidence_ceiling,
            permitted=permitted,
            downgraded=permitted != requested,
            reason=(
                "Requested state is within the EvidenceOps proof ceiling."
                if permitted == requested
                else "Claim downgraded to the EvidenceOps proof ceiling."
            ),
        )

    @staticmethod
    def negative_evidence_guard(record_found: bool) -> str:
        """Never convert an unsuccessful search into proof of non-existence."""

        return "RECORD_FOUND" if record_found else "NOT_FOUND_IN_SEARCHED_SCOPE"

    @classmethod
    def legacy_counsel_classification(
        cls, categorical_claim_state: ProofState, current_evidence_ceiling: ProofState
    ) -> str:
        """Classify a legacy counsel conclusion under the current proof ceiling."""

        decision = cls.claim_decision(categorical_claim_state, current_evidence_ceiling)
        if decision.downgraded:
            return "LEGAL_VULNERABILITY"
        return "CURRENTLY_PROOF_COMPATIBLE_COUNSEL_ANALYSIS"

    @staticmethod
    def surface_harmonized(readback: SurfaceReadback) -> bool:
        """Operational harmonisation requires exact surface-local semantics."""

        return readback.semantically_verified

    @classmethod
    def all_surfaces_harmonized(cls, readbacks: Iterable[SurfaceReadback]) -> bool:
        readbacks = tuple(readbacks)
        return bool(readbacks) and all(cls.surface_harmonized(item) for item in readbacks)

    @staticmethod
    def research_state_is_effect_authority(
        research_available: bool, effect_authority_verified: bool
    ) -> bool:
        """Research availability alone never promotes effect authority."""

        return bool(research_available and effect_authority_verified)

    @staticmethod
    def temporal_sequence_proves_causation(
        sequence_exists: bool, causal_evidence_exists: bool
    ) -> bool:
        """Timing is relevant context but cannot alone establish causation."""

        return bool(sequence_exists and causal_evidence_exists)

    @staticmethod
    def electronic_work_proves_physical_attendance(
        electronic_work_exists: bool, physical_attendance_evidence_exists: bool
    ) -> bool:
        """Electronic work and physical attendance are separate propositions."""

        return bool(electronic_work_exists and physical_attendance_evidence_exists)

    @staticmethod
    def smallest_sufficient_decision(
        objective: str, candidate_actions: Sequence[Mapping[str, object]]
    ) -> Mapping[str, object]:
        """Choose the lowest-burden complete action among eligible candidates.

        Each candidate must provide: `complete`, `authorised`, `reversible`,
        `burden`, and `proof_quality`. Lower burden wins after eligibility; higher
        proof quality breaks ties.
        """

        eligible = [
            item
            for item in candidate_actions
            if bool(item.get("complete"))
            and bool(item.get("authorised"))
            and bool(item.get("reversible", True))
        ]
        if not eligible:
            raise ValueError(f"No complete authorised reversible route for: {objective}")
        return min(
            eligible,
            key=lambda item: (
                float(item.get("burden", float("inf"))),
                -float(item.get("proof_quality", 0.0)),
            ),
        )

    @staticmethod
    def release_allowed(gate: ReleaseGate) -> bool:
        return gate.passed

    @classmethod
    def release_readiness_score(cls, gate: ReleaseGate) -> float:
        checks = (
            gate.proof_ok,
            gate.legal_accuracy_ok,
            gate.privacy_ok,
            gate.target_authority_ok,
            gate.version_ok,
            gate.semantic_readback_ok,
            gate.rollback_ok,
            (not gate.owner_approval_required) or gate.owner_approved,
        )
        return sum(bool(item) for item in checks) / len(checks)


def precedence_rank(layer: str) -> int:
    """Return lower-is-stronger precedence rank."""

    try:
        return FormationOmega.PRECEDENCE.index(layer)
    except ValueError as exc:
        raise ValueError(f"Unknown Formation-Omega precedence layer: {layer}") from exc
