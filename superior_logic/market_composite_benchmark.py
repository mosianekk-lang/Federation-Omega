from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class BenchmarkTask:
    task_id: str
    source_epoch: str
    environment_profile: str
    oracle_id: str
    hard_floors: tuple[str, ...]
    oracle_frozen: bool = True
    scoreable: bool = True


@dataclass(frozen=True, slots=True)
class BenchmarkObservation:
    task_id: str
    system_id: str
    system_class: str
    accepted: bool
    causal_accuracy: float
    quality_score: float
    hard_floor_pass: bool
    owner_interventions: int = 0
    regression_escapes: int = 0
    wall_time_seconds: float = 0.0
    cost_units: float = 0.0


@dataclass(frozen=True, slots=True)
class BenchmarkIntegrityVerdict:
    status: str
    scoreable_task_ids: tuple[str, ...]
    held_task_ids: tuple[str, ...]
    integrity_sha256: str


@dataclass(frozen=True, slots=True)
class AggregateMetrics:
    system_id: str
    system_class: str
    task_count: int
    accepted_rate: float
    causal_accuracy: float
    quality_score: float
    hard_floor_violations: int
    owner_interventions: int
    regression_escapes: int
    wall_time_seconds: float
    cost_units: float


@dataclass(frozen=True, slots=True)
class MarketCompositeVerdict:
    status: str
    candidate: AggregateMetrics
    baselines: tuple[AggregateMetrics, ...]
    dominated_baselines: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    independent_judge_passed: bool
    effect_authority_granted: bool
    verdict_sha256: str


class BenchmarkIntegrityCourt:
    def evaluate(self, tasks: Iterable[BenchmarkTask]) -> BenchmarkIntegrityVerdict:
        rows = tuple(tasks)
        if len({row.task_id for row in rows}) != len(rows):
            raise ValueError("duplicate task_id")
        scoreable, held = [], []
        for row in rows:
            ready = bool(row.task_id and row.source_epoch and row.environment_profile and row.oracle_id and row.hard_floors)
            (scoreable if row.scoreable and row.oracle_frozen and ready else held).append(row.task_id)
        body = {"scoreable": sorted(scoreable), "held": sorted(held)}
        return BenchmarkIntegrityVerdict(
            status="BENCHMARK_INTEGRITY_PASS" if scoreable else "BENCHMARK_INTEGRITY_HOLD",
            scoreable_task_ids=tuple(sorted(scoreable)),
            held_task_ids=tuple(sorted(held)),
            integrity_sha256=_sha(body),
        )


class MarketCompositeCourt:
    MIN_TASKS = 20
    MIN_BASELINE_SYSTEMS = 3

    @staticmethod
    def _aggregate(rows: Iterable[BenchmarkObservation]) -> AggregateMetrics:
        data = tuple(rows)
        if not data or len({row.system_id for row in data}) != 1 or len({row.task_id for row in data}) != len(data):
            raise ValueError("invalid observation cohort")
        for row in data:
            if not 0 <= row.causal_accuracy <= 1 or not 0 <= row.quality_score <= 1:
                raise ValueError("score out of range")
            if min(row.owner_interventions, row.regression_escapes, row.wall_time_seconds, row.cost_units) < 0:
                raise ValueError("negative metric")
        n = len(data)
        return AggregateMetrics(
            system_id=data[0].system_id,
            system_class=data[0].system_class,
            task_count=n,
            accepted_rate=sum(row.accepted for row in data) / n,
            causal_accuracy=sum(row.causal_accuracy for row in data) / n,
            quality_score=sum(row.quality_score for row in data) / n,
            hard_floor_violations=sum(not row.hard_floor_pass for row in data),
            owner_interventions=sum(row.owner_interventions for row in data),
            regression_escapes=sum(row.regression_escapes for row in data),
            wall_time_seconds=sum(row.wall_time_seconds for row in data),
            cost_units=sum(row.cost_units for row in data),
        )

    @staticmethod
    def _dominates(candidate: AggregateMetrics, baseline: AggregateMetrics) -> bool:
        noninferior = (
            candidate.hard_floor_violations == 0
            and candidate.accepted_rate >= baseline.accepted_rate
            and candidate.causal_accuracy >= baseline.causal_accuracy
            and candidate.quality_score >= baseline.quality_score
            and candidate.regression_escapes <= baseline.regression_escapes
            and candidate.owner_interventions <= baseline.owner_interventions
            and (candidate.wall_time_seconds <= baseline.wall_time_seconds * 1.05 or candidate.cost_units <= baseline.cost_units * 1.05)
        )
        strict = (
            candidate.accepted_rate > baseline.accepted_rate
            or candidate.causal_accuracy > baseline.causal_accuracy
            or candidate.quality_score > baseline.quality_score
            or candidate.owner_interventions < baseline.owner_interventions
            or candidate.regression_escapes < baseline.regression_escapes
            or candidate.wall_time_seconds < baseline.wall_time_seconds
            or candidate.cost_units < baseline.cost_units
        )
        return noninferior and strict

    def compare(self, *, tasks: Iterable[BenchmarkTask], candidate_observations: Iterable[BenchmarkObservation], baseline_observations: Iterable[BenchmarkObservation], independent_judge_passed: bool) -> MarketCompositeVerdict:
        integrity = BenchmarkIntegrityCourt().evaluate(tasks)
        task_set = set(integrity.scoreable_task_ids)
        candidate_rows = tuple(candidate_observations)
        if integrity.status != "BENCHMARK_INTEGRITY_PASS" or {row.task_id for row in candidate_rows} != task_set:
            raise ValueError("candidate task cohort mismatch")
        by_system: dict[str, list[BenchmarkObservation]] = {}
        for row in baseline_observations:
            by_system.setdefault(row.system_id, []).append(row)
        if any({row.task_id for row in rows} != task_set for rows in by_system.values()):
            raise ValueError("baseline task cohort mismatch")
        candidate = self._aggregate(candidate_rows)
        baselines = tuple(sorted((self._aggregate(rows) for rows in by_system.values()), key=lambda row: row.system_id))
        dominated = tuple(row.system_id for row in baselines if self._dominates(candidate, row))
        missing = []
        if candidate.task_count < self.MIN_TASKS: missing.append("MINIMUM_MATCHED_TASKS")
        if len(baselines) < self.MIN_BASELINE_SYSTEMS: missing.append("MINIMUM_BASELINE_SYSTEMS")
        if not any(row.system_class == "SYNTHETIC_MARKET_COMPOSITE" for row in baselines): missing.append("SYNTHETIC_MARKET_COMPOSITE_BASELINE")
        if candidate.hard_floor_violations: missing.append("CANDIDATE_HARD_FLOOR_NONREGRESSION")
        if not independent_judge_passed: missing.append("INDEPENDENT_JUDGE")
        if len(dominated) != len(baselines): missing.append("DOMINATE_EVERY_BASELINE")
        status = "MARKET_COMPOSITE_ADVANTAGE_PROVEN" if not missing else "TARGET_NOT_PROVEN"
        body = {"status": status, "candidate": asdict(candidate), "baselines": [asdict(row) for row in baselines], "dominated": dominated, "missing": sorted(set(missing)), "judge": independent_judge_passed}
        return MarketCompositeVerdict(status, candidate, baselines, dominated, tuple(sorted(set(missing))), independent_judge_passed, False, _sha(body))
