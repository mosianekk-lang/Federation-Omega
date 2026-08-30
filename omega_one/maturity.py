"""Omega-One capability maturity compiler.

A non-effect governance utility that converts heterogeneous capability evidence into a
single lowest-proven maturity state.  It intentionally distinguishes architecture,
source, tests, deployment, provider execution, semantic readback, repeated success,
soak and owner-value proof.

This module creates no provider authority and performs no external effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
import hashlib
import json
from typing import Iterable, Mapping, Sequence


class MaturityStage(IntEnum):
    DESIGNED = 10
    SOURCE_IMPLEMENTED = 20
    DETERMINISTIC_TESTED = 30
    CI_ADMITTED = 40
    DEPLOYED = 50
    PROVIDER_EXECUTED = 60
    SEMANTIC_READBACK_VERIFIED = 70
    REPEATED_SUCCESS = 80
    SOAKED = 90
    VALUE_VERIFIED = 100


_STAGE_ORDER = tuple(MaturityStage)


@dataclass(frozen=True)
class ProofClaim:
    stage: MaturityStage
    proven: bool
    evidence_refs: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class CapabilityRecord:
    capability_id: str
    name: str
    domain: str
    claims: tuple[ProofClaim, ...] = ()
    declared_status: str = ""
    owner_value_required: bool = False
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> "CapabilityRecord":
        if not self.capability_id.strip() or not self.name.strip() or not self.domain.strip():
            raise ValueError("capability_id, name and domain are required")
        return self


@dataclass(frozen=True)
class MaturityVerdict:
    capability_id: str
    lowest_proven_stage: MaturityStage | None
    highest_claimed_stage: MaturityStage | None
    next_required_stage: MaturityStage | None
    missing_predecessors: tuple[MaturityStage, ...]
    overclaim: bool
    evidence_refs: tuple[str, ...]
    verdict_sha256: str


class CapabilityMaturityCompiler:
    """Fail-closed compiler for proof maturity.

    A later stage can never be promoted unless every predecessor is independently
    proven.  Therefore a CI result cannot imply deployment, and deployment cannot
    imply provider execution or owner value.
    """

    @staticmethod
    def _canonical_json(value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def compile(cls, record: CapabilityRecord) -> MaturityVerdict:
        record.validate()
        by_stage = {claim.stage: claim for claim in record.claims}
        claimed = [stage for stage, claim in by_stage.items() if claim.proven]
        highest_claimed = max(claimed) if claimed else None

        lowest_proven: MaturityStage | None = None
        missing: list[MaturityStage] = []
        for stage in _STAGE_ORDER:
            claim = by_stage.get(stage)
            if claim and claim.proven and not missing:
                lowest_proven = stage
            else:
                missing.append(stage)
                # Once a predecessor is missing, later stages cannot promote the
                # canonical maturity even if a detached receipt exists.
                if highest_claimed is None or stage > highest_claimed:
                    break

        if lowest_proven is None:
            next_required = MaturityStage.DESIGNED
        elif lowest_proven == MaturityStage.VALUE_VERIFIED:
            next_required = None
        else:
            next_required = _STAGE_ORDER[_STAGE_ORDER.index(lowest_proven) + 1]

        overclaim = bool(highest_claimed and lowest_proven != highest_claimed)
        refs = tuple(sorted({ref for claim in record.claims for ref in claim.evidence_refs if ref}))
        body = {
            "capability_id": record.capability_id,
            "lowest_proven_stage": lowest_proven.name if lowest_proven else None,
            "highest_claimed_stage": highest_claimed.name if highest_claimed else None,
            "next_required_stage": next_required.name if next_required else None,
            "missing_predecessors": [stage.name for stage in missing],
            "overclaim": overclaim,
            "evidence_refs": refs,
        }
        digest = hashlib.sha256(cls._canonical_json(body).encode("utf-8")).hexdigest()
        return MaturityVerdict(
            capability_id=record.capability_id,
            lowest_proven_stage=lowest_proven,
            highest_claimed_stage=highest_claimed,
            next_required_stage=next_required,
            missing_predecessors=tuple(missing),
            overclaim=overclaim,
            evidence_refs=refs,
            verdict_sha256=digest,
        )

    @classmethod
    def compile_portfolio(cls, records: Iterable[CapabilityRecord]) -> tuple[MaturityVerdict, ...]:
        verdicts = [cls.compile(record) for record in records]
        verdicts.sort(key=lambda item: item.capability_id)
        return tuple(verdicts)

    @staticmethod
    def stage_distribution(verdicts: Sequence[MaturityVerdict]) -> Mapping[str, int]:
        counts = {stage.name: 0 for stage in _STAGE_ORDER}
        counts["UNPROVEN"] = 0
        for verdict in verdicts:
            if verdict.lowest_proven_stage is None:
                counts["UNPROVEN"] += 1
            else:
                counts[verdict.lowest_proven_stage.name] += 1
        return counts
