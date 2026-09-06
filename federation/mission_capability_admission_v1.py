"""FUSE Mission Capability Admission v1.

Binds MissionIR to Capability Truth. A mission is admitted only when every mandatory
capability requirement is satisfied by fresh, proof-bounded CapabilityTruth evidence,
or by an explicitly FULL-equivalent substitute that independently satisfies the same
required maturity contract.

This module grants no provider/effect authority and executes no external action.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Sequence

from federation.capability_truth_v1 import (
    CapabilityEligibilityCourt,
    CapabilityRequirement,
    CapabilityTruthRecord,
    EligibilityDecision,
    Maturity,
)
from federation.mission_ir import MissionIR

SCHEMA = "FUSE-MISSION-CAPABILITY-ADMISSION-V1"
VERSION = "1.0.0"


class Equivalence(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class SubstituteCapability:
    capability_id: str
    equivalence: Equivalence
    required_maturity: Maturity | None = None
    proof_ref: str = ""

    def validate(self) -> "SubstituteCapability":
        if not self.capability_id.strip():
            raise ValueError("SUBSTITUTE_CAPABILITY_ID_REQUIRED")
        if self.equivalence is Equivalence.FULL and not self.proof_ref.strip():
            raise ValueError("FULL_EQUIVALENCE_REQUIRES_PROOF_REF")
        return self


@dataclass(frozen=True, slots=True)
class MissionCapabilityRequirement:
    capability_id: str
    required_maturity: Maturity
    mandatory: bool = True
    require_fresh: bool = True
    require_independent_verification: bool = False
    substitutes: tuple[SubstituteCapability, ...] = ()

    def validate(self) -> "MissionCapabilityRequirement":
        if not self.capability_id.strip():
            raise ValueError("MISSION_CAPABILITY_ID_REQUIRED")
        seen: set[str] = set()
        for substitute in self.substitutes:
            substitute.validate()
            if substitute.capability_id == self.capability_id:
                raise ValueError("SUBSTITUTE_CANNOT_EQUAL_PRIMARY")
            if substitute.capability_id in seen:
                raise ValueError("DUPLICATE_SUBSTITUTE_CAPABILITY")
            seen.add(substitute.capability_id)
        return self

    def truth_requirement(self, capability_id: str | None = None, maturity: Maturity | None = None) -> CapabilityRequirement:
        return CapabilityRequirement(
            capability_id=capability_id or self.capability_id,
            required_maturity=maturity or self.required_maturity,
            require_fresh=self.require_fresh,
            require_independent_verification=self.require_independent_verification,
        )


@dataclass(frozen=True, slots=True)
class MissionCapabilityDecision:
    capability_id: str
    required_maturity: Maturity
    state: str
    selected_capability_id: str = ""
    selected_maturity: Maturity = Maturity.SPECIFIED
    equivalence: Equivalence = Equivalence.NONE
    reasons: tuple[str, ...] = ()

    @property
    def satisfied(self) -> bool:
        return self.state in {"SATISFIED_DIRECT", "SATISFIED_EQUIVALENT", "OPTIONAL_UNSATISFIED"}


@dataclass(frozen=True, slots=True)
class MissionAdmissionReceipt:
    mission_id: str
    mission_digest: str
    state: str
    decisions: tuple[MissionCapabilityDecision, ...]
    blocking_capabilities: tuple[str, ...]
    truth_index_digest: str
    receipt_digest: str

    @property
    def admitted(self) -> bool:
        return self.state == "MISSION_ADMITTED"


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class MissionCapabilityCompiler:
    """Fail-closed mission admission over Capability Truth."""

    def __init__(self, court: CapabilityEligibilityCourt | None = None) -> None:
        self.court = court or CapabilityEligibilityCourt()

    def _decide_direct(
        self,
        requirement: MissionCapabilityRequirement,
        records: Mapping[str, CapabilityTruthRecord],
    ) -> EligibilityDecision:
        return self.court.decide(
            requirement.truth_requirement(),
            records.get(requirement.capability_id),
        )

    def _decide_requirement(
        self,
        requirement: MissionCapabilityRequirement,
        records: Mapping[str, CapabilityTruthRecord],
    ) -> MissionCapabilityDecision:
        requirement.validate()
        direct = self._decide_direct(requirement, records)
        if direct.eligible:
            return MissionCapabilityDecision(
                capability_id=requirement.capability_id,
                required_maturity=requirement.required_maturity,
                state="SATISFIED_DIRECT",
                selected_capability_id=requirement.capability_id,
                selected_maturity=direct.proven_maturity,
                equivalence=Equivalence.FULL,
                reasons=direct.reasons,
            )

        rejected_substitutes: list[str] = []
        for substitute in requirement.substitutes:
            substitute.validate()
            if substitute.equivalence is not Equivalence.FULL:
                rejected_substitutes.append(f"{substitute.capability_id}:EQUIVALENCE_{substitute.equivalence.value}")
                continue
            required = substitute.required_maturity or requirement.required_maturity
            decision = self.court.decide(
                requirement.truth_requirement(substitute.capability_id, required),
                records.get(substitute.capability_id),
            )
            if decision.eligible:
                return MissionCapabilityDecision(
                    capability_id=requirement.capability_id,
                    required_maturity=requirement.required_maturity,
                    state="SATISFIED_EQUIVALENT",
                    selected_capability_id=substitute.capability_id,
                    selected_maturity=decision.proven_maturity,
                    equivalence=Equivalence.FULL,
                    reasons=("FULL_EQUIVALENCE_PROVEN", substitute.proof_ref) + decision.reasons,
                )
            rejected_substitutes.append(f"{substitute.capability_id}:MATURITY_NOT_PROVEN")

        if not requirement.mandatory:
            return MissionCapabilityDecision(
                capability_id=requirement.capability_id,
                required_maturity=requirement.required_maturity,
                state="OPTIONAL_UNSATISFIED",
                selected_maturity=direct.proven_maturity,
                reasons=direct.reasons + tuple(rejected_substitutes),
            )
        return MissionCapabilityDecision(
            capability_id=requirement.capability_id,
            required_maturity=requirement.required_maturity,
            state="BLOCKING_CAPABILITY_GAP",
            selected_maturity=direct.proven_maturity,
            reasons=direct.reasons + tuple(rejected_substitutes),
        )

    def admit(
        self,
        mission: MissionIR,
        requirements: Sequence[MissionCapabilityRequirement],
        records: Mapping[str, CapabilityTruthRecord],
    ) -> MissionAdmissionReceipt:
        mission.validate()
        seen: set[str] = set()
        for requirement in requirements:
            requirement.validate()
            if requirement.capability_id in seen:
                raise ValueError("DUPLICATE_MISSION_CAPABILITY_REQUIREMENT")
            seen.add(requirement.capability_id)

        decisions = tuple(self._decide_requirement(req, records) for req in requirements)
        blocking = tuple(sorted(d.capability_id for d in decisions if d.state == "BLOCKING_CAPABILITY_GAP"))
        state = "MISSION_ADMITTED" if not blocking else "MISSION_HELD_CAPABILITY_GAP"
        truth_material = {
            key: int(record.max_proven_maturity)
            for key, record in sorted(records.items())
        }
        truth_digest = _digest(truth_material)
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": mission.mission_id,
            "mission_digest": mission.digest(),
            "state": state,
            "blocking": blocking,
            "truth_index_digest": truth_digest,
            "decisions": [
                {
                    "capability_id": d.capability_id,
                    "required_maturity": int(d.required_maturity),
                    "state": d.state,
                    "selected_capability_id": d.selected_capability_id,
                    "selected_maturity": int(d.selected_maturity),
                    "equivalence": d.equivalence.value,
                    "reasons": d.reasons,
                }
                for d in decisions
            ],
        }
        return MissionAdmissionReceipt(
            mission_id=mission.mission_id,
            mission_digest=mission.digest(),
            state=state,
            decisions=decisions,
            blocking_capabilities=blocking,
            truth_index_digest=truth_digest,
            receipt_digest=_digest(material),
        )


__all__ = [
    "SCHEMA",
    "VERSION",
    "Equivalence",
    "MissionAdmissionReceipt",
    "MissionCapabilityCompiler",
    "MissionCapabilityDecision",
    "MissionCapabilityRequirement",
    "SubstituteCapability",
]
