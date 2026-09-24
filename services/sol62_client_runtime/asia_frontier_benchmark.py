from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from math import comb
import json
from statistics import mean, median
from typing import Mapping, Sequence

from services.sol62_client_runtime.asia_frontier_composite import (
    REQUIRED_BENCHMARK_DIMENSIONS,
    MatchedDimension,
    matched_frontier_verdict,
)


SCHEMA = "SOL62_ASIA_FRONTIER_MATCHED_BENCHMARK_RUNTIME_V1"


@dataclass(frozen=True)
class FrozenFrontier:
    cohort_id: str
    frozen_at: str
    source_refs: tuple[str, ...]
    mechanism_gene_ids: tuple[str, ...]
    workload_manifest_sha256: str
    runtime_epoch: str

    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class MatchedSample:
    dimension: str
    sample_id: str
    workload_id: str
    candidate_score: float
    frontier_score: float
    candidate_owner_interventions: int = 0
    frontier_owner_interventions: int = 0
    candidate_wall_time_ms: int = 0
    frontier_wall_time_ms: int = 0
    candidate_cost: float = 0.0
    frontier_cost: float = 0.0
    candidate_tool_calls: int = 0
    frontier_tool_calls: int = 0
    critical_regression: bool = False
    evidence_ref: str = ""
    synthetic: bool = False


@dataclass(frozen=True)
class DimensionCourt:
    dimension: str
    matched_samples: int
    noninferior: bool
    significant_win: bool
    critical_regressions: int
    mean_delta: float
    median_delta: float
    wins: int
    losses: int
    ties: int
    one_sided_sign_p: float
    candidate_owner_interventions_mean: float
    frontier_owner_interventions_mean: float
    candidate_wall_time_ms_mean: float
    frontier_wall_time_ms_mean: float
    candidate_cost_mean: float
    frontier_cost_mean: float
    candidate_tool_calls_mean: float
    frontier_tool_calls_mean: float
    evidence_refs: tuple[str, ...]
    natural_samples: int


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def freeze_frontier(
    *,
    frozen_at: str,
    source_refs: Sequence[str],
    mechanism_gene_ids: Sequence[str],
    workload_manifest: Mapping[str, object],
    runtime_epoch: str,
) -> FrozenFrontier:
    sources = tuple(sorted({ref.strip() for ref in source_refs if ref.strip()}))
    genes = tuple(sorted({gene.strip() for gene in mechanism_gene_ids if gene.strip()}))
    if not sources:
        raise ValueError("FRONTIER_SOURCE_REQUIRED")
    if not genes:
        raise ValueError("FRONTIER_GENE_REQUIRED")
    manifest_sha = _digest(workload_manifest)
    cohort_id = "ASIA-FRONTIER-" + _digest(
        {
            "frozen_at": frozen_at,
            "sources": sources,
            "genes": genes,
            "manifest_sha": manifest_sha,
            "runtime_epoch": runtime_epoch,
        }
    )[:20].upper()
    return FrozenFrontier(
        cohort_id=cohort_id,
        frozen_at=frozen_at,
        source_refs=sources,
        mechanism_gene_ids=genes,
        workload_manifest_sha256=manifest_sha,
        runtime_epoch=runtime_epoch,
    )


def _validate_sample(sample: MatchedSample) -> None:
    if sample.dimension not in REQUIRED_BENCHMARK_DIMENSIONS:
        raise ValueError("UNKNOWN_BENCHMARK_DIMENSION")
    if not sample.sample_id.strip() or not sample.workload_id.strip():
        raise ValueError("MATCHED_SAMPLE_ID_REQUIRED")
    if not 0 <= sample.candidate_score <= 1 or not 0 <= sample.frontier_score <= 1:
        raise ValueError("NORMALIZED_SCORE_OUT_OF_RANGE")
    for value in (
        sample.candidate_owner_interventions,
        sample.frontier_owner_interventions,
        sample.candidate_wall_time_ms,
        sample.frontier_wall_time_ms,
        sample.candidate_tool_calls,
        sample.frontier_tool_calls,
    ):
        if value < 0:
            raise ValueError("NEGATIVE_BENCHMARK_METRIC")
    if sample.candidate_cost < 0 or sample.frontier_cost < 0:
        raise ValueError("NEGATIVE_COST")


def _sign_test_one_sided_p(wins: int, losses: int) -> float:
    """P[X >= wins] for X~Binomial(n, .5), ties excluded."""
    n = wins + losses
    if n == 0:
        return 1.0
    numerator = sum(comb(n, k) for k in range(wins, n + 1))
    return numerator / (2 ** n)


def dimension_court(
    dimension: str,
    samples: Sequence[MatchedSample],
    *,
    noninferiority_margin: float = 0.02,
    significant_delta_floor: float = 0.03,
    significance_alpha: float = 0.05,
    minimum_samples: int = 12,
    natural_sample_floor: int = 6,
) -> DimensionCourt:
    rows = [sample for sample in samples if sample.dimension == dimension]
    if dimension not in REQUIRED_BENCHMARK_DIMENSIONS:
        raise ValueError("UNKNOWN_BENCHMARK_DIMENSION")
    for sample in rows:
        _validate_sample(sample)
    sample_ids = [row.sample_id for row in rows]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("DUPLICATE_MATCHED_SAMPLE_ID")

    deltas = [row.candidate_score - row.frontier_score for row in rows]
    wins = sum(delta > 1e-12 for delta in deltas)
    losses = sum(delta < -1e-12 for delta in deltas)
    ties = len(rows) - wins - losses
    critical = sum(1 for row in rows if row.critical_regression)
    natural_samples = sum(1 for row in rows if not row.synthetic)
    mean_delta = mean(deltas) if deltas else 0.0
    median_delta = median(deltas) if deltas else 0.0
    p = _sign_test_one_sided_p(wins, losses)

    enough = len(rows) >= minimum_samples
    natural_enough = natural_samples >= natural_sample_floor
    noninferior = (
        enough
        and natural_enough
        and critical == 0
        and mean_delta >= -noninferiority_margin
    )
    significant_win = (
        noninferior
        and mean_delta >= significant_delta_floor
        and wins > losses
        and p <= significance_alpha
    )

    def avg(attr: str) -> float:
        return mean(getattr(row, attr) for row in rows) if rows else 0.0

    return DimensionCourt(
        dimension=dimension,
        matched_samples=len(rows),
        noninferior=noninferior,
        significant_win=significant_win,
        critical_regressions=critical,
        mean_delta=mean_delta,
        median_delta=median_delta,
        wins=wins,
        losses=losses,
        ties=ties,
        one_sided_sign_p=p,
        candidate_owner_interventions_mean=avg("candidate_owner_interventions"),
        frontier_owner_interventions_mean=avg("frontier_owner_interventions"),
        candidate_wall_time_ms_mean=avg("candidate_wall_time_ms"),
        frontier_wall_time_ms_mean=avg("frontier_wall_time_ms"),
        candidate_cost_mean=avg("candidate_cost"),
        frontier_cost_mean=avg("frontier_cost"),
        candidate_tool_calls_mean=avg("candidate_tool_calls"),
        frontier_tool_calls_mean=avg("frontier_tool_calls"),
        evidence_refs=tuple(sorted({row.evidence_ref for row in rows if row.evidence_ref})),
        natural_samples=natural_samples,
    )


def run_matched_frontier_court(
    *,
    frontier: FrozenFrontier,
    samples: Sequence[MatchedSample],
    minimum_samples: int = 12,
    minimum_significant_wins: int = 8,
    natural_sample_floor: int = 6,
) -> dict[str, object]:
    for sample in samples:
        _validate_sample(sample)
    dimensions = [
        dimension_court(
            dimension,
            samples,
            minimum_samples=minimum_samples,
            natural_sample_floor=natural_sample_floor,
        )
        for dimension in REQUIRED_BENCHMARK_DIMENSIONS
    ]
    translated = tuple(
        MatchedDimension(
            dimension=row.dimension,
            matched_samples=row.matched_samples,
            candidate_noninferior=row.noninferior,
            candidate_significant_wins=1 if row.significant_win else 0,
            critical_regressions=row.critical_regressions,
        )
        for row in dimensions
    )
    verdict = matched_frontier_verdict(
        translated,
        minimum_samples_per_dimension=minimum_samples,
        minimum_significant_wins=minimum_significant_wins,
    )
    evidence = {
        "schema": SCHEMA,
        "frontier": asdict(frontier),
        "frontier_digest": frontier.digest(),
        "sample_count": len(samples),
        "dimension_courts": [asdict(row) for row in dimensions],
        "verdict": verdict,
        "independent_judge_required": True,
        "builder_self_certification_allowed": False,
        "truth_boundary": (
            "MATCHED_COURT_RESULT_NE_JUDGE_ACK_NE_SOURCE_ADMITTED_NE_LIVE_GLOBAL_DEFAULT_"
            "NE_OWNER_VALUE_VERIFIED_NE_UNIVERSAL_MARKET_SUPERIORITY"
        ),
    }
    evidence["court_sha256"] = _digest(evidence)
    return evidence


def compile_independent_judge_packet(court: Mapping[str, object]) -> dict[str, object]:
    if court.get("schema") != SCHEMA:
        raise ValueError("MATCHED_COURT_SCHEMA_REQUIRED")
    court_sha = str(court.get("court_sha256") or "")
    if not court_sha:
        raise ValueError("COURT_SHA_REQUIRED")
    verdict = court.get("verdict")
    if not isinstance(verdict, Mapping):
        raise ValueError("COURT_VERDICT_REQUIRED")
    return {
        "schema": "SOL62_ASIA_FRONTIER_JUDGE_PACKET_V1",
        "court_sha256": court_sha,
        "frontier_digest": court.get("frontier_digest"),
        "claimed_status": verdict.get("status"),
        "claimed_market_superiority_proven": verdict.get("market_superiority_proven") is True,
        "judge_must_recompute": True,
        "judge_must_verify_sample_custody": True,
        "judge_must_check_critical_regressions": True,
        "judge_must_check_cohort_currentness": True,
        "builder_verdict_authoritative": False,
        "authority_granted": False,
        "truth_boundary": "JUDGE_PACKET_READY_NE_JUDGE_ACK_NE_PROMOTION",
    }


def natural_workload_sample(
    *,
    dimension: str,
    sample_id: str,
    workload_id: str,
    candidate_accepted: bool,
    frontier_accepted: bool,
    candidate_quality: float,
    frontier_quality: float,
    candidate_owner_interventions: int,
    frontier_owner_interventions: int,
    candidate_wall_time_ms: int,
    frontier_wall_time_ms: int,
    candidate_cost: float,
    frontier_cost: float,
    candidate_tool_calls: int,
    frontier_tool_calls: int,
    candidate_critical_regression: bool,
    evidence_ref: str,
) -> MatchedSample:
    """Normalize one real matched episode into a higher-is-better score.

    Acceptance is a hard value component; quality is bounded [0,1]. Cost/latency/tool
    efficiency remain separately visible rather than being hidden in the score.
    """
    if not 0 <= candidate_quality <= 1 or not 0 <= frontier_quality <= 1:
        raise ValueError("QUALITY_OUT_OF_RANGE")
    candidate_score = 0.7 * candidate_quality + 0.3 * (1.0 if candidate_accepted else 0.0)
    frontier_score = 0.7 * frontier_quality + 0.3 * (1.0 if frontier_accepted else 0.0)
    return MatchedSample(
        dimension=dimension,
        sample_id=sample_id,
        workload_id=workload_id,
        candidate_score=candidate_score,
        frontier_score=frontier_score,
        candidate_owner_interventions=candidate_owner_interventions,
        frontier_owner_interventions=frontier_owner_interventions,
        candidate_wall_time_ms=candidate_wall_time_ms,
        frontier_wall_time_ms=frontier_wall_time_ms,
        candidate_cost=candidate_cost,
        frontier_cost=frontier_cost,
        candidate_tool_calls=candidate_tool_calls,
        frontier_tool_calls=frontier_tool_calls,
        critical_regression=candidate_critical_regression,
        evidence_ref=evidence_ref,
        synthetic=False,
    )
