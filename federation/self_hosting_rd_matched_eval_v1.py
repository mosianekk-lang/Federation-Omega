"""Matched incumbent/challenger evaluation for Self-Hosting R&D v1.

This module evaluates supplied observations only. It never executes provider
effects, deploys, mutates source, or authorizes promotion. It reuses ProofOS CFBE
for dimension scoring and preserves owner-value/Judge as later independent gates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from statistics import median
from typing import Any, Mapping, Sequence

from proofos_omega.cfbe import (
    BenchmarkObservation,
    CFBEAdmissionComparator,
    EVIDENCE_FACTORS,
)

SCHEMA = "FUSE-SELF-HOSTING-RD-MATCHED-EVAL-RECEIPT-V1"
VERSION = "1.0.0"
OPERATIONAL_STATES = {"REPEATED_OPERATIONAL_SCOPED", "PROVIDER_LIVE_INDEPENDENT_READBACK"}
DEFAULT_MINIMUM_MATCHED_PAIRS = 12
DEFAULT_MINIMUM_REAL_PAIRS_FOR_PROMOTION = 20


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _is_sha(value: str) -> bool:
    return len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower())


def _is_digest(value: str) -> bool:
    prefix, sep, digest = value.partition(":")
    return sep == ":" and prefix == "sha256" and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest.lower())


@dataclass(frozen=True, slots=True)
class EngineeringObservation:
    arm: str
    pair_id: str
    mission_class: str
    task_signature: str
    oracle_id: str
    input_digest: str
    environment_digest: str
    source_head_sha: str
    evidence_state: str
    metrics: Mapping[str, float]
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.arm not in {"INCUMBENT", "CHALLENGER"}:
            raise ValueError("MATCHED_EVAL_ARM_INVALID")
        if not self.pair_id or not self.mission_class or not self.task_signature or not self.oracle_id:
            raise ValueError("MATCHED_EVAL_IDENTITY_REQUIRED")
        if not _is_digest(self.input_digest) or not _is_digest(self.environment_digest):
            raise ValueError("MATCHED_EVAL_INPUT_ENV_DIGEST_REQUIRED")
        if not _is_sha(self.source_head_sha):
            raise ValueError("MATCHED_EVAL_SOURCE_SHA_REQUIRED")
        if self.evidence_state not in EVIDENCE_FACTORS:
            raise ValueError("MATCHED_EVAL_EVIDENCE_STATE_INVALID")
        if not self.metrics:
            raise ValueError("MATCHED_EVAL_METRICS_REQUIRED")
        if any(float(v) < 0 for v in self.metrics.values()):
            raise ValueError("MATCHED_EVAL_NEGATIVE_METRIC")
        if any(not str(ref).strip() for ref in self.proof_refs):
            raise ValueError("MATCHED_EVAL_BLANK_PROOF_REF")


@dataclass(frozen=True, slots=True)
class MatchedPair:
    incumbent: EngineeringObservation
    challenger: EngineeringObservation

    def match_failures(self, incumbent_source_head: str, challenger_source_head: str) -> tuple[str, ...]:
        self.incumbent.validate()
        self.challenger.validate()
        failures: list[str] = []
        if self.incumbent.arm != "INCUMBENT" or self.challenger.arm != "CHALLENGER":
            failures.append("MATCHED_EVAL_ARM_PAIR_INVALID")
        for field, code in (
            ("pair_id", "PAIR_ID"),
            ("mission_class", "MISSION_CLASS"),
            ("task_signature", "TASK_SIGNATURE"),
            ("oracle_id", "ORACLE"),
            ("input_digest", "INPUT"),
            ("environment_digest", "ENVIRONMENT"),
            ("evidence_state", "EVIDENCE_STATE"),
        ):
            if getattr(self.incumbent, field) != getattr(self.challenger, field):
                failures.append(f"MATCHED_EVAL_{code}_MISMATCH")
        if self.incumbent.source_head_sha != incumbent_source_head:
            failures.append("MATCHED_EVAL_INCUMBENT_SOURCE_MISMATCH")
        if self.challenger.source_head_sha != challenger_source_head:
            failures.append("MATCHED_EVAL_CHALLENGER_SOURCE_MISMATCH")
        return tuple(failures)

    @property
    def operational_and_independent(self) -> bool:
        if self.incumbent.evidence_state not in OPERATIONAL_STATES or self.challenger.evidence_state not in OPERATIONAL_STATES:
            return False
        irefs=set(self.incumbent.proof_refs)
        crefs=set(self.challenger.proof_refs)
        return len(irefs) >= 2 and len(crefs) >= 2 and bool(irefs.symmetric_difference(crefs))


@dataclass(frozen=True, slots=True)
class PairEvaluation:
    pair_id: str
    matched: bool
    match_failures: tuple[str, ...]
    hard_gates_pass: bool
    cfbe_status: str
    effective_score: float
    operational_and_independent: bool
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class MatchedEvalReceipt:
    schema: str
    version: str
    candidate_id: str
    incumbent_source_head: str
    challenger_source_head: str
    pair_count: int
    matched_pair_count: int
    operational_pair_count: int
    minimum_matched_pairs: int
    minimum_real_pairs_for_promotion: int
    matched_conditions_pass: bool
    quality_nonnegative: bool
    matched_eval_proven: bool
    owner_value_proven: bool
    independent_judge_ack: bool
    promotion_authorized: bool
    median_effective_score: float
    decision: str
    blockers: tuple[str, ...]
    pair_results: tuple[PairEvaluation, ...]
    provider_effect_authorized: bool
    external_effect: bool
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_matched_cohort(
    *,
    candidate_id: str,
    incumbent_source_head: str,
    challenger_source_head: str,
    pairs: Sequence[MatchedPair],
    cfbe_spec: Mapping[str, Any],
    minimum_matched_pairs: int = DEFAULT_MINIMUM_MATCHED_PAIRS,
    minimum_real_pairs_for_promotion: int = DEFAULT_MINIMUM_REAL_PAIRS_FOR_PROMOTION,
) -> MatchedEvalReceipt:
    if not candidate_id.strip():
        raise ValueError("MATCHED_EVAL_CANDIDATE_ID_REQUIRED")
    if not _is_sha(incumbent_source_head) or not _is_sha(challenger_source_head):
        raise ValueError("MATCHED_EVAL_SOURCE_HEADS_REQUIRED")
    if minimum_matched_pairs <= 0 or minimum_real_pairs_for_promotion < minimum_matched_pairs:
        raise ValueError("MATCHED_EVAL_SAMPLE_FLOOR_INVALID")
    pair_ids=[p.incumbent.pair_id for p in pairs]
    if len(pair_ids) != len(set(pair_ids)):
        raise ValueError("MATCHED_EVAL_DUPLICATE_PAIR_ID")

    comparator=CFBEAdmissionComparator(cfbe_spec)
    results: list[PairEvaluation] = []
    blockers: set[str] = set()

    for pair in pairs:
        failures=pair.match_failures(incumbent_source_head,challenger_source_head)
        matched=not failures
        if failures:
            blockers.update(failures)
            result_status="HELD_MATCH_MISMATCH"
            hard=False
            effective=0.0
            cfbe_receipt=""
        else:
            comparison=comparator.compare(
                incumbent=BenchmarkObservation(
                    evidence_state=pair.incumbent.evidence_state,
                    metrics=pair.incumbent.metrics,
                    proof_refs=pair.incumbent.proof_refs,
                ),
                challenger=BenchmarkObservation(
                    evidence_state=pair.challenger.evidence_state,
                    metrics=pair.challenger.metrics,
                    proof_refs=pair.challenger.proof_refs,
                ),
            )
            hard=comparison.hard_gates_pass
            effective=comparison.effective_weighted_score
            result_status=comparison.status
            cfbe_receipt=comparison.receipt_sha256
            if not hard:
                blockers.add("MATCHED_EVAL_QUALITY_OR_SAFETY_REGRESSION")
        payload={
            "pair_id":pair.incumbent.pair_id,
            "matched":matched,
            "failures":failures,
            "hard_gates_pass":hard,
            "status":result_status,
            "effective_score":round(effective,8),
            "operational_and_independent":pair.operational_and_independent,
            "cfbe_receipt":cfbe_receipt,
        }
        results.append(PairEvaluation(
            pair_id=pair.incumbent.pair_id,
            matched=matched,
            match_failures=failures,
            hard_gates_pass=hard,
            cfbe_status=result_status,
            effective_score=effective,
            operational_and_independent=pair.operational_and_independent,
            receipt_sha256=_digest(payload),
        ))

    matched_count=sum(1 for r in results if r.matched)
    operational_count=sum(1 for r in results if r.matched and r.operational_and_independent)
    matched_conditions_pass=bool(results) and matched_count==len(results)
    quality_nonnegative=bool(results) and all(r.matched and r.hard_gates_pass for r in results)
    enough_pairs=len(results) >= minimum_matched_pairs
    if not enough_pairs:
        blockers.add("MATCHED_EVAL_INSUFFICIENT_PAIRS")
    if matched_conditions_pass and operational_count < minimum_matched_pairs:
        blockers.add("MATCHED_EVAL_OPERATIONAL_EVIDENCE_FLOOR_OPEN")

    matched_eval_proven=(
        enough_pairs
        and matched_conditions_pass
        and quality_nonnegative
        and operational_count >= minimum_matched_pairs
    )

    if not enough_pairs:
        decision="HOLD_INSUFFICIENT_MATCHED_PAIRS"
    elif not matched_conditions_pass:
        decision="HOLD_MATCHING_CONTRACT"
    elif not quality_nonnegative:
        decision="HOLD_QUALITY_OR_SAFETY_REGRESSION"
    elif operational_count < minimum_matched_pairs:
        decision="HOLD_NO_OPERATIONAL_MATCHED_EVIDENCE"
    else:
        decision="MATCHED_EVAL_PROVEN__OWNER_VALUE_AND_JUDGE_OPEN"

    median_score=median([r.effective_score for r in results]) if results else 0.0
    payload={
        "schema":SCHEMA,
        "version":VERSION,
        "candidate_id":candidate_id,
        "incumbent_source_head":incumbent_source_head,
        "challenger_source_head":challenger_source_head,
        "pair_count":len(results),
        "matched_pair_count":matched_count,
        "operational_pair_count":operational_count,
        "minimum_matched_pairs":minimum_matched_pairs,
        "minimum_real_pairs_for_promotion":minimum_real_pairs_for_promotion,
        "matched_conditions_pass":matched_conditions_pass,
        "quality_nonnegative":quality_nonnegative,
        "matched_eval_proven":matched_eval_proven,
        "owner_value_proven":False,
        "independent_judge_ack":False,
        "promotion_authorized":False,
        "median_effective_score":round(float(median_score),8),
        "decision":decision,
        "blockers":sorted(blockers),
        "pair_receipts":[r.receipt_sha256 for r in results],
        "provider_effect_authorized":False,
        "external_effect":False,
    }
    return MatchedEvalReceipt(
        schema=SCHEMA,
        version=VERSION,
        candidate_id=candidate_id,
        incumbent_source_head=incumbent_source_head,
        challenger_source_head=challenger_source_head,
        pair_count=len(results),
        matched_pair_count=matched_count,
        operational_pair_count=operational_count,
        minimum_matched_pairs=minimum_matched_pairs,
        minimum_real_pairs_for_promotion=minimum_real_pairs_for_promotion,
        matched_conditions_pass=matched_conditions_pass,
        quality_nonnegative=quality_nonnegative,
        matched_eval_proven=matched_eval_proven,
        owner_value_proven=False,
        independent_judge_ack=False,
        promotion_authorized=False,
        median_effective_score=float(median_score),
        decision=decision,
        blockers=tuple(sorted(blockers)),
        pair_results=tuple(results),
        provider_effect_authorized=False,
        external_effect=False,
        receipt_sha256=_digest(payload),
    )
