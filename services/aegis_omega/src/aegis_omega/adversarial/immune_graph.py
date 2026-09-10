from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import timezone
import hashlib
import json
from typing import Iterable

from ..schemas import SecurityEvent


@dataclass(frozen=True, slots=True)
class EvidenceGraphReport:
    total_events: int
    unique_events: int
    duplicate_events: int
    independent_sources: int
    independent_classes: int
    source_concentration: float
    class_concentration: float
    replay_ratio: float
    diversity_score: float
    temporal_coherence: float
    corroboration_score: float
    poisoning_resistance_factor: float
    graph_sha256: str

    def as_dict(self) -> dict:
        return asdict(self)


def _stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def analyze_evidence_graph(events: Iterable[SecurityEvent]) -> EvidenceGraphReport:
    xs = list(events)
    total = len(xs)
    if not xs:
        body = {
            "total_events": 0, "unique_events": 0, "duplicate_events": 0,
            "independent_sources": 0, "independent_classes": 0,
            "source_concentration": 0.0, "class_concentration": 0.0,
            "replay_ratio": 0.0, "diversity_score": 0.0,
            "temporal_coherence": 0.0, "corroboration_score": 0.0,
            "poisoning_resistance_factor": 1.0,
        }
        return EvidenceGraphReport(**body, graph_sha256=_stable_hash(body))

    by_id: dict[str, SecurityEvent] = {}
    duplicate_events = 0
    for event in xs:
        if event.event_id in by_id:
            duplicate_events += 1
            continue
        by_id[event.event_id] = event
    unique = list(by_id.values())
    unique_count = len(unique)

    source_counts = Counter(e.source.strip().lower() for e in unique)
    class_counts = Counter(e.event_class.value for e in unique)
    max_source = max(source_counts.values(), default=0)
    max_class = max(class_counts.values(), default=0)
    source_concentration = max_source / unique_count if unique_count else 0.0
    class_concentration = max_class / unique_count if unique_count else 0.0
    replay_ratio = duplicate_events / total if total else 0.0

    source_diversity = min(1.0, len(source_counts) / 4.0)
    class_diversity = min(1.0, len(class_counts) / 4.0)
    diversity_score = (source_diversity * class_diversity) ** 0.5

    times = sorted(e.timestamp.astimezone(timezone.utc).timestamp() for e in unique)
    if len(times) <= 1:
        temporal_coherence = 0.5
    else:
        span = max(times[-1] - times[0], 0.0)
        # Evidence spread over up to an hour remains coherent; beyond a day the
        # correlation weakens. This is deliberately conservative and metadata-only.
        temporal_coherence = max(0.0, min(1.0, 1.0 - max(0.0, span - 3600.0) / 86400.0))

    corroboration_score = max(0.0, min(1.0,
        0.40 * source_diversity + 0.40 * class_diversity + 0.20 * temporal_coherence
    ))

    source_penalty = max(0.0, source_concentration - 0.55) / 0.45
    class_penalty = max(0.0, class_concentration - 0.70) / 0.30
    poisoning_penalty = min(1.0, 0.55 * source_penalty + 0.30 * replay_ratio + 0.15 * class_penalty)
    poisoning_resistance_factor = max(0.35, 1.0 - poisoning_penalty)

    body = {
        "total_events": total,
        "unique_events": unique_count,
        "duplicate_events": duplicate_events,
        "independent_sources": len(source_counts),
        "independent_classes": len(class_counts),
        "source_concentration": round(source_concentration, 6),
        "class_concentration": round(class_concentration, 6),
        "replay_ratio": round(replay_ratio, 6),
        "diversity_score": round(diversity_score, 6),
        "temporal_coherence": round(temporal_coherence, 6),
        "corroboration_score": round(corroboration_score, 6),
        "poisoning_resistance_factor": round(poisoning_resistance_factor, 6),
    }
    return EvidenceGraphReport(**body, graph_sha256=_stable_hash(body))


def source_balanced_scores(events: Iterable[SecurityEvent], weighted_scores: dict[str, float]) -> tuple[float, float]:
    """Return source-balanced mean and class-balanced mean.

    Only the strongest score per (source, class) contributes. This prevents a
    replaying or noisy single sensor from manufacturing confidence by volume.
    """
    source_class: dict[tuple[str, str], float] = {}
    for event in events:
        key = (event.source.strip().lower(), event.event_class.value)
        source_class[key] = max(source_class.get(key, 0.0), weighted_scores.get(event.event_id, 0.0))

    by_source: dict[str, list[float]] = defaultdict(list)
    by_class: dict[str, list[float]] = defaultdict(list)
    for (source, event_class), score in source_class.items():
        by_source[source].append(score)
        by_class[event_class].append(score)

    source_values = [sum(v) / len(v) for v in by_source.values() if v]
    class_values = [max(v) for v in by_class.values() if v]
    source_mean = sum(source_values) / len(source_values) if source_values else 0.0
    class_mean = sum(class_values) / len(class_values) if class_values else 0.0
    return source_mean, class_mean
