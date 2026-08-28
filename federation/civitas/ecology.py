from __future__ import annotations

"""Ω-ECOLOGY inter-institution market and sanitized capability exchange."""

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from .contracts import (
    AuthorityClass,
    CivitasError,
    ProofLevel,
    ProofRef,
    digest,
    in_unit_interval,
    proof_at_least,
    safe_id,
)


@dataclass(frozen=True)
class CognitiveInstitution:
    institution_id: str
    role: str
    proof: ProofRef
    authority_ceiling: AuthorityClass = AuthorityClass.A1_INTERNAL
    privacy_domains: tuple[str, ...] = ("PUBLIC_SAFE",)
    failure_domains: tuple[str, ...] = ()
    health: float = 0.5
    external_effects: int = 0

    def validate(self) -> "CognitiveInstitution":
        safe_id(self.institution_id, "institution_id")
        if not self.role.strip() or not self.privacy_domains:
            raise ValueError("institution role and privacy domains required")
        self.proof.validate()
        in_unit_interval(self.health, "health")
        if self.authority_ceiling not in {AuthorityClass.A0_READ, AuthorityClass.A1_INTERNAL}:
            raise CivitasError("institution exceeds internal authority ceiling")
        if self.external_effects:
            raise CivitasError("institution registry cannot execute effects")
        return self


@dataclass(frozen=True)
class RouteBid:
    bid_id: str
    institution_id: str
    mission_id: str
    capability_fit: float
    proof_freshness: float
    proof_strength: float
    reliability: float
    information_gain: float
    failure_domain_diversity: float
    reversibility: float
    cost: float
    latency: float
    risk: float
    owner_burden: float
    proof_ref: str
    eligible: bool
    failure_domains: tuple[str, ...] = ()
    required_authority: AuthorityClass = AuthorityClass.A1_INTERNAL
    external_effect: bool = False

    def validate(self) -> "RouteBid":
        safe_id(self.bid_id, "bid_id")
        safe_id(self.institution_id, "institution_id")
        safe_id(self.mission_id, "mission_id")
        if not self.proof_ref.strip():
            raise ValueError("bid proof_ref required")
        for name in (
            "capability_fit", "proof_freshness", "proof_strength", "reliability",
            "information_gain", "failure_domain_diversity", "reversibility",
            "cost", "latency", "risk", "owner_burden",
        ):
            in_unit_interval(getattr(self, name), name)
        if self.required_authority not in {AuthorityClass.A0_READ, AuthorityClass.A1_INTERNAL}:
            raise CivitasError("bid requires external authority")
        if self.external_effect:
            raise CivitasError("ecology bids are internal/shadow only")
        return self

    @property
    def score(self) -> float:
        self.validate()
        return round(
            0.19 * self.capability_fit
            + 0.14 * self.proof_freshness
            + 0.15 * self.proof_strength
            + 0.15 * self.reliability
            + 0.12 * self.information_gain
            + 0.10 * self.failure_domain_diversity
            + 0.08 * self.reversibility
            - 0.025 * self.cost
            - 0.02 * self.latency
            - 0.035 * self.risk
            - 0.03 * self.owner_burden,
            8,
        )


@dataclass(frozen=True)
class MarketAward:
    mission_id: str
    champion_bid_id: str
    shadow_bid_ids: tuple[str, ...]
    reserve_bid_ids: tuple[str, ...]
    rejected_bid_ids: tuple[str, ...]
    hidden_spofs: tuple[str, ...]
    explanation: str
    external_effects: int = 0

    @property
    def receipt_sha256(self) -> str:
        return digest(asdict(self))


@dataclass(frozen=True)
class CapabilityGenePacket:
    packet_id: str
    source_institution_id: str
    problem_class: str
    pattern: str
    prerequisites: tuple[str, ...]
    exclusions: tuple[str, ...]
    measured_benefits: tuple[str, ...]
    tradeoffs: tuple[str, ...]
    failure_modes: tuple[str, ...]
    rollback_pattern: str
    proof_refs: tuple[str, ...]
    confidence: float
    authority_ceiling: AuthorityClass = AuthorityClass.A1_INTERNAL
    privacy_ceiling: str = "PUBLIC_SAFE"
    private_payload_included: bool = False
    provider_credentials_included: bool = False
    maturity_transferred: bool = False
    external_effects: int = 0

    def validate(self) -> "CapabilityGenePacket":
        safe_id(self.packet_id, "packet_id")
        safe_id(self.source_institution_id, "source_institution_id")
        if not self.problem_class.strip() or not self.pattern.strip() or not self.rollback_pattern.strip():
            raise ValueError("gene packet requires problem, pattern and rollback")
        if not self.proof_refs:
            raise ValueError("gene packet requires proof")
        in_unit_interval(self.confidence, "confidence")
        if self.authority_ceiling not in {AuthorityClass.A0_READ, AuthorityClass.A1_INTERNAL}:
            raise CivitasError("gene packet cannot transfer effect authority")
        if self.private_payload_included or self.provider_credentials_included or self.maturity_transferred:
            raise CivitasError("private payload, credentials and maturity transfer blocked")
        return self


@dataclass(frozen=True)
class AdoptionDecision:
    packet_id: str
    receiver_institution_id: str
    disposition: str
    local_proof_required: bool
    shadow_required: bool
    rollback_required: bool
    proof_refs: tuple[str, ...]
    explanation: str
    external_effects: int = 0


class CognitiveEcologyMarket:
    """Eligibility-first internal market with champion/shadow diversity."""

    def __init__(self, institutions: Sequence[CognitiveInstitution]) -> None:
        self._institutions: dict[str, CognitiveInstitution] = {}
        for institution in institutions:
            institution.validate()
            if institution.institution_id in self._institutions:
                raise CivitasError("duplicate institution id")
            self._institutions[institution.institution_id] = institution

    def award(self, mission_id: str, bids: Sequence[RouteBid], *, max_shadows: int = 2) -> MarketAward:
        safe_id(mission_id, "mission_id")
        if max_shadows < 0:
            raise ValueError("max_shadows cannot be negative")
        if not bids:
            raise ValueError("market requires bids")
        eligible: list[RouteBid] = []
        rejected: list[str] = []
        seen: set[str] = set()
        for bid in bids:
            bid.validate()
            if bid.bid_id in seen:
                raise CivitasError("duplicate bid id")
            seen.add(bid.bid_id)
            if bid.mission_id != mission_id:
                raise CivitasError("bid mission mismatch")
            institution = self._institutions.get(bid.institution_id)
            if institution is None:
                raise CivitasError("bid references unknown institution")
            admissible = (
                bid.eligible
                and institution.health >= 0.4
                and proof_at_least(institution.proof.level, ProofLevel.SOURCE_READBACK)
                and bid.proof_strength >= 0.35
                and bid.proof_freshness >= 0.25
            )
            if admissible:
                eligible.append(bid)
            else:
                rejected.append(bid.bid_id)
        if not eligible:
            return MarketAward(mission_id, "", (), (), tuple(sorted(rejected)), (), "no eligible proof-bearing route; hold exact gate")
        ranked = sorted(eligible, key=lambda item: (item.score, item.bid_id), reverse=True)
        champion = ranked[0]
        champion_domains = set(champion.failure_domains)
        shadows: list[str] = []
        reserves: list[str] = []
        for bid in ranked[1:]:
            diverse = not champion_domains.intersection(bid.failure_domains)
            if len(shadows) < max_shadows and diverse:
                shadows.append(bid.bid_id)
            else:
                reserves.append(bid.bid_id)
        selected_domains: dict[str, int] = {}
        selected = [champion] + [next(item for item in ranked if item.bid_id == bid_id) for bid_id in shadows]
        for bid in selected:
            for domain in bid.failure_domains:
                selected_domains[domain] = selected_domains.get(domain, 0) + 1
        spofs = tuple(sorted(domain for domain, count in selected_domains.items() if count >= 2))
        return MarketAward(
            mission_id,
            champion.bid_id,
            tuple(shadows),
            tuple(reserves),
            tuple(sorted(rejected)),
            spofs,
            "highest admissible evidence-weighted bid selected; shadows require failure-domain diversity",
        )

    @staticmethod
    def sanitize_gene(packet: CapabilityGenePacket) -> CapabilityGenePacket:
        return packet.validate()

    def adoption_decision(
        self,
        packet: CapabilityGenePacket,
        receiver_institution_id: str,
        *,
        receiver_compatible: bool,
        receiver_current_proof: ProofRef,
    ) -> AdoptionDecision:
        packet.validate()
        safe_id(receiver_institution_id, "receiver_institution_id")
        receiver = self._institutions.get(receiver_institution_id)
        if receiver is None:
            raise CivitasError("unknown receiver institution")
        receiver_current_proof.validate()
        if not receiver_compatible:
            disposition = "NOT_APPLICABLE"
            explanation = "receiver compatibility test failed; no forced mutation"
        elif not proof_at_least(receiver_current_proof.level, ProofLevel.SOURCE_READBACK):
            disposition = "HOLD_RECEIVER_REPROBE"
            explanation = "receiver state is insufficiently proven for adaptation"
        else:
            disposition = "ADAPT_IN_LOCAL_SHADOW"
            explanation = "provider-neutral gene may be adapted, but receiver-local proof and value remain mandatory"
        refs = tuple(sorted(set(packet.proof_refs + (receiver_current_proof.proof_ref,))))
        return AdoptionDecision(
            packet.packet_id,
            receiver_institution_id,
            disposition,
            local_proof_required=True,
            shadow_required=disposition == "ADAPT_IN_LOCAL_SHADOW",
            rollback_required=disposition == "ADAPT_IN_LOCAL_SHADOW",
            proof_refs=refs,
            explanation=explanation,
        )


__all__ = [
    "CognitiveInstitution", "RouteBid", "MarketAward", "CapabilityGenePacket",
    "AdoptionDecision", "CognitiveEcologyMarket",
]
