from __future__ import annotations

"""Deterministic proof-convertibility classification for Failure-Win v2.

This module prevents receiver-name-only trust transfer. A recovery decision is
convertible only when preserved failure evidence and successful readback resolve
to the same receiver *and* the same semantic surface. Workflow/admission noise,
test-harness defects, authority holds and unpaired successes are retained but
cannot promote receiver behaviour.

The classifier is deterministic decision support only. It performs no provider
mutation, grants no authority and does not self-promote receiver maturity.
"""

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from typing import Iterable


class EvidenceKind(str, Enum):
    FAILURE_FACT = "FAILURE_FACT"
    RECOVERY_EVIDENCE = "RECOVERY_EVIDENCE"
    SUCCESS_ONLY = "SUCCESS_ONLY"
    ADMISSION_NOISE = "ADMISSION_NOISE"
    TEST_HARNESS_NOISE = "TEST_HARNESS_NOISE"
    AUTHORITY_HOLD = "AUTHORITY_HOLD"


class ExecutionPhase(str, Enum):
    ADMISSION = "ADMISSION"
    SETUP = "SETUP"
    TEST_HARNESS = "TEST_HARNESS"
    RUNTIME = "RUNTIME"
    PROVIDER = "PROVIDER"
    READBACK = "READBACK"


class ConvertibilityReason(str, Enum):
    CONVERTIBLE = "CONVERTIBLE"
    RECEIVER_MISMATCH = "RECEIVER_MISMATCH"
    SURFACE_MISMATCH = "SURFACE_MISMATCH"
    ADMISSION_NOISE = "ADMISSION_NOISE"
    TEST_HARNESS_NOISE = "TEST_HARNESS_NOISE"
    AUTHORITY_HOLD = "AUTHORITY_HOLD"
    SUCCESS_ONLY = "SUCCESS_ONLY"
    FAILURE_NOT_EXECUTED = "FAILURE_NOT_EXECUTED"
    NO_INDEPENDENT_READBACK = "NO_INDEPENDENT_READBACK"
    NON_REVERSIBLE_ROUTE = "NON_REVERSIBLE_ROUTE"
    SYNTHETIC_ONLY = "SYNTHETIC_ONLY"
    AMBIGUOUS_SURFACE = "AMBIGUOUS_SURFACE"


def _normalise(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SemanticSurface:
    receiver_id: str
    operation: str
    runtime_or_provider: str
    interface: str
    contract_class: str

    def validate(self) -> "SemanticSurface":
        required = asdict(self)
        missing = tuple(key for key, value in required.items() if not str(value).strip())
        if missing:
            raise ValueError("semantic surface requires: " + ", ".join(sorted(missing)))
        return self

    @property
    def fingerprint(self) -> str:
        self.validate()
        identity = {
            "receiver_id": _normalise(self.receiver_id),
            "operation": _normalise(self.operation),
            "runtime_or_provider": _normalise(self.runtime_or_provider),
            "interface": _normalise(self.interface),
            "contract_class": _normalise(self.contract_class),
        }
        return "ssf-" + _canonical_hash(identity)[:24]


@dataclass(frozen=True)
class ProofEvidence:
    evidence_id: str
    surface: SemanticSurface
    phase: ExecutionPhase
    observed_success: bool
    material: bool = True
    actual_execution_started: bool = True
    independent_readback: bool = False
    reversible: bool = False
    authority_current: bool = True
    owner_secret_required: bool = False
    synthetic: bool = False
    harness_defect: bool = False
    admission_failure: bool = False
    proof_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClassifiedEvidence:
    evidence: ProofEvidence
    kind: EvidenceKind
    reason: ConvertibilityReason
    promotable: bool


@dataclass(frozen=True)
class ProofPairDecision:
    failure_id: str
    recovery_id: str
    convertible: bool
    reason: ConvertibilityReason
    surface_fingerprint: str
    proof_score: int


@dataclass(frozen=True)
class ReceiverLane:
    receiver_id: str
    surface_fingerprint: str
    failure_id: str
    recovery_id: str
    proof_score: int
    rank_key: tuple[int, int, int, int, str]


class ProofConvertibilityClassifier:
    """Fail-closed evidence classification and same-surface pairing."""

    @staticmethod
    def classify(evidence: ProofEvidence) -> ClassifiedEvidence:
        try:
            evidence.surface.validate()
        except ValueError:
            return ClassifiedEvidence(
                evidence,
                EvidenceKind.ADMISSION_NOISE,
                ConvertibilityReason.AMBIGUOUS_SURFACE,
                False,
            )

        if evidence.owner_secret_required or not evidence.authority_current:
            return ClassifiedEvidence(
                evidence,
                EvidenceKind.AUTHORITY_HOLD,
                ConvertibilityReason.AUTHORITY_HOLD,
                False,
            )
        if evidence.admission_failure or evidence.phase is ExecutionPhase.ADMISSION:
            return ClassifiedEvidence(
                evidence,
                EvidenceKind.ADMISSION_NOISE,
                ConvertibilityReason.ADMISSION_NOISE,
                False,
            )
        if evidence.harness_defect or evidence.phase is ExecutionPhase.TEST_HARNESS:
            return ClassifiedEvidence(
                evidence,
                EvidenceKind.TEST_HARNESS_NOISE,
                ConvertibilityReason.TEST_HARNESS_NOISE,
                False,
            )
        if not evidence.actual_execution_started:
            return ClassifiedEvidence(
                evidence,
                EvidenceKind.ADMISSION_NOISE,
                ConvertibilityReason.FAILURE_NOT_EXECUTED,
                False,
            )

        if evidence.observed_success:
            if not evidence.independent_readback:
                return ClassifiedEvidence(
                    evidence,
                    EvidenceKind.SUCCESS_ONLY,
                    ConvertibilityReason.NO_INDEPENDENT_READBACK,
                    False,
                )
            if evidence.synthetic:
                return ClassifiedEvidence(
                    evidence,
                    EvidenceKind.SUCCESS_ONLY,
                    ConvertibilityReason.SYNTHETIC_ONLY,
                    False,
                )
            # A successful observation is intentionally SUCCESS_ONLY here.
            # It becomes recovery evidence only after pair() proves a preserved,
            # executed failure on the exact same receiver + semantic surface.
            return ClassifiedEvidence(
                evidence,
                EvidenceKind.SUCCESS_ONLY,
                ConvertibilityReason.SUCCESS_ONLY,
                False,
            )

        return ClassifiedEvidence(
            evidence,
            EvidenceKind.FAILURE_FACT,
            ConvertibilityReason.CONVERTIBLE,
            False,
        )

    @classmethod
    def pair(cls, failure: ProofEvidence, recovery: ProofEvidence) -> ProofPairDecision:
        failure_class = cls.classify(failure)
        recovery_class = cls.classify(recovery)

        surface_fingerprint = ""
        try:
            surface_fingerprint = failure.surface.fingerprint
        except ValueError:
            pass

        if failure_class.kind is not EvidenceKind.FAILURE_FACT:
            return ProofPairDecision(
                failure.evidence_id,
                recovery.evidence_id,
                False,
                failure_class.reason,
                surface_fingerprint,
                0,
            )

        # Raw successes must remain SUCCESS_ONLY. Only the strongest success-only
        # class (real execution + independent readback + non-synthetic) may be
        # paired. Lower-quality success-only observations keep their specific
        # disqualifying reason and cannot become recovery evidence.
        if not (
            recovery_class.kind is EvidenceKind.SUCCESS_ONLY
            and recovery_class.reason is ConvertibilityReason.SUCCESS_ONLY
        ):
            return ProofPairDecision(
                failure.evidence_id,
                recovery.evidence_id,
                False,
                recovery_class.reason,
                surface_fingerprint,
                0,
            )
        if _normalise(failure.surface.receiver_id) != _normalise(recovery.surface.receiver_id):
            return ProofPairDecision(
                failure.evidence_id,
                recovery.evidence_id,
                False,
                ConvertibilityReason.RECEIVER_MISMATCH,
                surface_fingerprint,
                0,
            )
        if failure.surface.fingerprint != recovery.surface.fingerprint:
            return ProofPairDecision(
                failure.evidence_id,
                recovery.evidence_id,
                False,
                ConvertibilityReason.SURFACE_MISMATCH,
                surface_fingerprint,
                0,
            )
        if not recovery.reversible:
            return ProofPairDecision(
                failure.evidence_id,
                recovery.evidence_id,
                False,
                ConvertibilityReason.NON_REVERSIBLE_ROUTE,
                surface_fingerprint,
                0,
            )

        # Hard gates above dominate. The score only ranks already-convertible
        # evidence and cannot turn an ineligible pair into a promotable one.
        score = 0
        score += 3 if failure.material else 0
        score += 3 if recovery.independent_readback else 0
        score += 2 if recovery.reversible else 0
        score += 2 if recovery.phase in (ExecutionPhase.RUNTIME, ExecutionPhase.PROVIDER, ExecutionPhase.READBACK) else 0
        score += min(2, len(set(failure.proof_refs + recovery.proof_refs)))
        return ProofPairDecision(
            failure.evidence_id,
            recovery.evidence_id,
            True,
            ConvertibilityReason.CONVERTIBLE,
            surface_fingerprint,
            score,
        )

    @classmethod
    def rank_pairs(
        cls,
        candidates: Iterable[tuple[ProofEvidence, ProofEvidence]],
    ) -> tuple[ReceiverLane, ...]:
        lanes: list[ReceiverLane] = []
        for failure, recovery in candidates:
            decision = cls.pair(failure, recovery)
            if not decision.convertible:
                continue
            provider_depth = int(recovery.phase in (ExecutionPhase.PROVIDER, ExecutionPhase.READBACK))
            proof_depth = min(9, len(set(failure.proof_refs + recovery.proof_refs)))
            burden = int(recovery.owner_secret_required)
            lanes.append(
                ReceiverLane(
                    receiver_id=failure.surface.receiver_id,
                    surface_fingerprint=decision.surface_fingerprint,
                    failure_id=failure.evidence_id,
                    recovery_id=recovery.evidence_id,
                    proof_score=decision.proof_score,
                    rank_key=(
                        -decision.proof_score,
                        -provider_depth,
                        -proof_depth,
                        burden,
                        decision.surface_fingerprint,
                    ),
                )
            )
        return tuple(sorted(lanes, key=lambda item: item.rank_key))


@dataclass
class SurfaceSearchBudget:
    """Circuit-break repeated evidence mining on an unchanged semantic surface."""

    maximum_misses: int = 3

    def __post_init__(self) -> None:
        if self.maximum_misses < 1:
            raise ValueError("maximum_misses must be >= 1")
        self._misses: dict[str, int] = {}

    def record_miss(self, surface: SemanticSurface) -> int:
        fingerprint = surface.fingerprint
        self._misses[fingerprint] = self._misses.get(fingerprint, 0) + 1
        return self._misses[fingerprint]

    def should_demote(self, surface: SemanticSurface) -> bool:
        return self._misses.get(surface.fingerprint, 0) >= self.maximum_misses

    def reset(self, surface: SemanticSurface) -> None:
        self._misses.pop(surface.fingerprint, None)
