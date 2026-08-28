from __future__ import annotations

"""Ω-CIVITAS cognitive institution.

CIVITAS compiles temporary, least-privilege cognitive organizations around a
mission and subjects material decisions to an independent constitutional court.
It organizes intelligence; it does not inherit or create provider authority.
"""

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from .contracts import (
    AssuranceVote,
    CapabilityDescriptor,
    CivitasError,
    DecisionDisposition,
    DecisionReceipt,
    ProofLevel,
    VoteState,
    digest,
    proof_at_least,
    safe_id,
)


REQUIRED_COURT_ROLES = ("JARVIS", "CFBE", "SENTINEL", "REALITYGUARD")


@dataclass(frozen=True)
class InstitutionalConstitution:
    constitution_id: str
    owner_root: str
    objective: str
    authority_ceiling: str = "A1_INTERNAL"
    truth_floor: float = 0.70
    proof_floor: ProofLevel = ProofLevel.SOURCE_READBACK
    privacy_floor: str = "PUBLIC_SAFE"
    executor_self_certification_allowed: bool = False
    external_effects: int = 0

    def validate(self) -> "InstitutionalConstitution":
        safe_id(self.constitution_id, "constitution_id")
        if not self.owner_root.strip() or not self.objective.strip():
            raise ValueError("owner_root and objective required")
        if self.authority_ceiling != "A1_INTERNAL":
            raise CivitasError("CIVITAS constitution cannot expand effect authority")
        if not 0 <= self.truth_floor <= 1:
            raise ValueError("truth_floor must be in [0,1]")
        if self.executor_self_certification_allowed or self.external_effects:
            raise CivitasError("self-certification/effects prohibited")
        return self


@dataclass(frozen=True)
class MissionRole:
    role_id: str
    purpose: str
    required_tags: tuple[str, ...]
    minimum_proof: ProofLevel = ProofLevel.SOURCE_READBACK
    privacy_ceiling: str = "PUBLIC_SAFE"
    independent_from: tuple[str, ...] = ()
    required: bool = True

    def validate(self) -> "MissionRole":
        safe_id(self.role_id, "role_id")
        if not self.purpose.strip() or not self.required_tags:
            raise ValueError("role purpose and tags required")
        return self


@dataclass(frozen=True)
class OrganizationAssignment:
    role_id: str
    capability_id: str
    proof_ref: str
    failure_domains: tuple[str, ...]
    disposition: str = "ASSIGNED_INTERNAL"
    external_effects: int = 0


@dataclass(frozen=True)
class CognitiveOrganization:
    organization_id: str
    mission_id: str
    assignments: tuple[OrganizationAssignment, ...]
    unfilled_required_roles: tuple[str, ...]
    shared_failure_domains: tuple[str, ...]
    authority_ceiling: str = "A1_INTERNAL"
    temporary: bool = True
    external_effects: int = 0

    @property
    def ready(self) -> bool:
        return not self.unfilled_required_roles and self.authority_ceiling == "A1_INTERNAL" and self.external_effects == 0

    @property
    def receipt_sha256(self) -> str:
        return digest(asdict(self))


@dataclass(frozen=True)
class CourtDecision:
    decision_id: str
    disposition: str
    passed_roles: tuple[str, ...]
    held_roles: tuple[str, ...]
    veto_roles: tuple[str, ...]
    missing_roles: tuple[str, ...]
    proof_refs: tuple[str, ...]
    executor_self_certified: bool
    explanation: str
    external_effects: int = 0

    @property
    def receipt_sha256(self) -> str:
        return digest(asdict(self))


class CognitiveOrganizationCompiler:
    """Forms temporary teams from current proof-bearing capabilities."""

    @staticmethod
    def _eligible(role: MissionRole, capability: CapabilityDescriptor) -> bool:
        capability.validate()
        wanted = {item.lower() for item in role.required_tags}
        actual = {item.lower() for item in capability.tags}
        privacy_ok = role.privacy_ceiling == capability.privacy_ceiling or role.privacy_ceiling == "PUBLIC_SAFE"
        return wanted.issubset(actual) and proof_at_least(capability.proof.level, role.minimum_proof) and privacy_ok

    def compile(
        self,
        *,
        organization_id: str,
        mission_id: str,
        roles: Sequence[MissionRole],
        capabilities: Sequence[CapabilityDescriptor],
    ) -> CognitiveOrganization:
        safe_id(organization_id, "organization_id")
        safe_id(mission_id, "mission_id")
        if not roles:
            raise ValueError("organization requires roles")
        assignments: list[OrganizationAssignment] = []
        missing: list[str] = []
        used: set[str] = set()
        for role in roles:
            role.validate()
            candidates = [item for item in capabilities if item.capability_id not in used and self._eligible(role, item)]
            candidates.sort(
                key=lambda item: (
                    item.proof.rank,
                    item.reliability,
                    -item.estimated_cost,
                    -item.estimated_latency,
                    item.capability_id,
                ),
                reverse=True,
            )
            if not candidates:
                if role.required:
                    missing.append(role.role_id)
                continue
            selected = candidates[0]
            used.add(selected.capability_id)
            assignments.append(OrganizationAssignment(
                role.role_id,
                selected.capability_id,
                selected.proof.proof_ref,
                selected.failure_domains,
            ))
        domains: dict[str, int] = {}
        for assignment in assignments:
            for domain in assignment.failure_domains:
                domains[domain] = domains.get(domain, 0) + 1
        shared = tuple(sorted(domain for domain, count in domains.items() if count >= 2))
        return CognitiveOrganization(
            organization_id,
            mission_id,
            tuple(assignments),
            tuple(sorted(missing)),
            shared,
        )


class ConstitutionalCourt:
    """Independent assurance court; executor cannot certify its own decision."""

    def decide(
        self,
        *,
        decision_id: str,
        votes: Sequence[AssuranceVote],
        required_roles: Sequence[str] = REQUIRED_COURT_ROLES,
    ) -> CourtDecision:
        safe_id(decision_id, "decision_id")
        if not votes:
            raise ValueError("court requires votes")
        role_votes: dict[str, AssuranceVote] = {}
        executor_self_certified = False
        proof_refs: set[str] = set()
        for vote in votes:
            vote.validate()
            role = vote.institutional_role.upper()
            if role in role_votes:
                raise CivitasError("duplicate institutional court role")
            role_votes[role] = vote
            executor_self_certified = executor_self_certified or vote.executor_identity
            proof_refs.update(vote.proof_refs)
        required = {role.upper() for role in required_roles}
        missing = tuple(sorted(required.difference(role_votes)))
        passed = tuple(sorted(role for role, vote in role_votes.items() if vote.state == VoteState.PASS and vote.independent and not vote.executor_identity))
        held = tuple(sorted(role for role, vote in role_votes.items() if vote.state == VoteState.HOLD))
        veto = tuple(sorted(role for role, vote in role_votes.items() if vote.state == VoteState.VETO))
        if executor_self_certified:
            disposition = "HOLD_EXECUTOR_SELF_CERTIFICATION"
            explanation = "executor identity attempted to certify the same decision"
        elif veto:
            disposition = "VETO"
            explanation = "one or more independent constitutional functions vetoed the decision"
        elif missing:
            disposition = "HOLD_MISSING_INDEPENDENT_COURT_ROLES"
            explanation = "required independent court roles are absent"
        elif held:
            disposition = "HOLD"
            explanation = "one or more independent court roles require additional proof"
        elif required.issubset(set(passed)):
            disposition = "PASS_INTERNAL_DECISION"
            explanation = "all required independent court roles passed with proof"
        else:
            disposition = "HOLD_INSUFFICIENT_INDEPENDENT_PASS"
            explanation = "abstentions or non-independent votes prevent passage"
        return CourtDecision(
            decision_id,
            disposition,
            passed,
            held,
            veto,
            missing,
            tuple(sorted(proof_refs)),
            executor_self_certified,
            explanation,
        )


class CivitasInstitution:
    """Coordinates constitution, organization and court into one internal receipt."""

    def __init__(self, constitution: InstitutionalConstitution) -> None:
        self.constitution = constitution.validate()
        self.compiler = CognitiveOrganizationCompiler()
        self.court = ConstitutionalCourt()

    def prepare_mission(
        self,
        *,
        mission_id: str,
        organization_id: str,
        roles: Sequence[MissionRole],
        capabilities: Sequence[CapabilityDescriptor],
        votes: Sequence[AssuranceVote],
    ) -> DecisionReceipt:
        organization = self.compiler.compile(
            organization_id=organization_id,
            mission_id=mission_id,
            roles=roles,
            capabilities=capabilities,
        )
        court = self.court.decide(decision_id=f"COURT:{mission_id}", votes=votes)
        selected = tuple(assignment.capability_id for assignment in organization.assignments)
        rejected = organization.unfilled_required_roles
        if not organization.ready:
            disposition = DecisionDisposition.HOLD
            reason = "organization has unfilled required roles"
        elif court.disposition != "PASS_INTERNAL_DECISION":
            disposition = DecisionDisposition.HOLD
            reason = court.explanation
        else:
            disposition = DecisionDisposition.SELECT
            reason = "temporary organization compiled and independent constitutional court passed"
        proof_refs = tuple(sorted({assignment.proof_ref for assignment in organization.assignments}.union(court.proof_refs)))
        receipt = DecisionReceipt(
            decision_id=f"CIVITAS:{mission_id}",
            disposition=disposition,
            selected_ids=selected,
            rejected_ids=rejected,
            proof_refs=proof_refs,
            explanation={
                "reason": reason,
                "organization": asdict(organization),
                "court": asdict(court),
                "separate_sovara_effect_admission_required": True,
            },
        )
        return receipt.validate()


__all__ = [
    "REQUIRED_COURT_ROLES", "InstitutionalConstitution", "MissionRole",
    "OrganizationAssignment", "CognitiveOrganization", "CourtDecision",
    "CognitiveOrganizationCompiler", "ConstitutionalCourt", "CivitasInstitution",
]
