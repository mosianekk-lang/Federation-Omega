from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import random
from typing import Sequence

from .twin import ScenarioCase
from ..fusion import assess_events_with_policy


@dataclass(frozen=True, slots=True)
class PolicyGenome:
    genome_id: str
    max_weight: float = .50
    source_mean_weight: float = .20
    class_mean_weight: float = .15
    anomaly_weight: float = .15
    graph_weight: float = .30
    manual_threshold: float = .70
    high_threshold: float = .85

    def validate(self) -> "PolicyGenome":
        weights = (self.max_weight, self.source_mean_weight, self.class_mean_weight, self.anomaly_weight)
        if abs(sum(weights) - 1.0) > 1e-6:
            raise ValueError("AEGIS_POLICY_PRIMARY_WEIGHTS_MUST_SUM_TO_1")
        for value in (*weights, self.graph_weight, self.manual_threshold, self.high_threshold):
            if not 0.0 <= value <= 1.0:
                raise ValueError("AEGIS_POLICY_VALUE_OUT_OF_RANGE")
        if self.high_threshold < self.manual_threshold:
            raise ValueError("AEGIS_POLICY_HIGH_THRESHOLD_BELOW_MANUAL")
        return self


@dataclass(frozen=True, slots=True)
class GenomeScore:
    genome_id: str
    threat_recall: float
    benign_specificity: float
    replay_resistance: float
    source_concentration_resistance: float
    expected_disposition_accuracy: float
    score: float


@dataclass(frozen=True, slots=True)
class TournamentReceipt:
    schema: str
    baseline_genome_id: str
    champion_genome_id: str
    champion_is_shadow_candidate: bool
    auto_promotion_performed: bool
    candidate_count: int
    baseline_score: float
    champion_score: float
    improvement: float
    quality_floor_passed: bool
    scores: tuple[GenomeScore, ...]
    receipt_sha256: str


def _hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _rank(disposition: str) -> int:
    return {"observe": 0, "investigate": 1, "containment_recommended": 2}[disposition]


def evaluate_genome(genome: PolicyGenome, scenarios: Sequence[ScenarioCase]) -> GenomeScore:
    genome.validate()
    threat = [s for s in scenarios if s.expected_threat_like]
    benign = [s for s in scenarios if not s.expected_threat_like]
    threat_hits = 0
    benign_hits = 0
    expected_hits = 0
    replay_ok = 1.0
    concentration_ok = 1.0
    for case in scenarios:
        result = assess_events_with_policy(case.events, genome)
        observed_threat = result.disposition != "observe"
        if case.expected_threat_like and observed_threat:
            threat_hits += 1
        if not case.expected_threat_like and not observed_threat:
            benign_hits += 1
        if _rank(result.disposition) >= _rank(case.expected_min_disposition):
            expected_hits += 1
        if case.scenario.value == "replay_flood":
            replay_ok = 1.0 if result.disposition == "observe" else 0.0
        if case.scenario.value == "source_concentration":
            concentration_ok = 1.0 if result.disposition == "observe" else 0.0
    recall = threat_hits / len(threat) if threat else 1.0
    specificity = benign_hits / len(benign) if benign else 1.0
    expected = expected_hits / len(scenarios) if scenarios else 1.0
    score = .35 * recall + .30 * specificity + .15 * expected + .10 * replay_ok + .10 * concentration_ok
    return GenomeScore(
        genome_id=genome.genome_id,
        threat_recall=round(recall, 6),
        benign_specificity=round(specificity, 6),
        replay_resistance=replay_ok,
        source_concentration_resistance=concentration_ok,
        expected_disposition_accuracy=round(expected, 6),
        score=round(score, 6),
    )


def mutate_genomes(baseline: PolicyGenome, *, count: int = 24, seed: int = 41) -> tuple[PolicyGenome, ...]:
    rng = random.Random(seed)
    candidates = [baseline]
    base_weights = [baseline.max_weight, baseline.source_mean_weight, baseline.class_mean_weight, baseline.anomaly_weight]
    for i in range(1, count):
        raw = [max(.05, w + rng.uniform(-.08, .08)) for w in base_weights]
        total = sum(raw)
        weights = [w / total for w in raw]
        manual = min(.80, max(.58, baseline.manual_threshold + rng.uniform(-.06, .06)))
        high = min(.94, max(manual + .08, baseline.high_threshold + rng.uniform(-.05, .05)))
        graph = min(.50, max(.15, baseline.graph_weight + rng.uniform(-.10, .10)))
        candidates.append(PolicyGenome(
            genome_id=f"shadow-{i:02d}", max_weight=weights[0], source_mean_weight=weights[1],
            class_mean_weight=weights[2], anomaly_weight=weights[3], graph_weight=graph,
            manual_threshold=manual, high_threshold=high,
        ))
    return tuple(candidates)


def run_policy_tournament(scenarios: Sequence[ScenarioCase], *, count: int = 24) -> TournamentReceipt:
    baseline = PolicyGenome("baseline-v1")
    genomes = mutate_genomes(baseline, count=count)
    scores = tuple(sorted((evaluate_genome(g, scenarios) for g in genomes), key=lambda s: (-s.score, s.genome_id)))
    baseline_score = next(s for s in scores if s.genome_id == baseline.genome_id)
    champion = scores[0]
    quality_floor = (
        champion.threat_recall >= .80 and champion.benign_specificity >= .80 and
        champion.replay_resistance == 1.0 and champion.source_concentration_resistance == 1.0
    )
    body = {
        "schema": "AEGIS_EVOLUTION_TOURNAMENT_V1",
        "baseline_genome_id": baseline.genome_id,
        "champion_genome_id": champion.genome_id,
        "champion_is_shadow_candidate": True,
        "auto_promotion_performed": False,
        "candidate_count": len(scores),
        "baseline_score": baseline_score.score,
        "champion_score": champion.score,
        "improvement": round(champion.score - baseline_score.score, 6),
        "quality_floor_passed": quality_floor,
        "scores": [asdict(s) for s in scores],
    }
    return TournamentReceipt(
        schema=body["schema"], baseline_genome_id=baseline.genome_id,
        champion_genome_id=champion.genome_id, champion_is_shadow_candidate=True,
        auto_promotion_performed=False, candidate_count=len(scores),
        baseline_score=baseline_score.score, champion_score=champion.score,
        improvement=body["improvement"], quality_floor_passed=quality_floor,
        scores=scores, receipt_sha256=_hash(body),
    )
