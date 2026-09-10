from __future__ import annotations
import uuid
from typing import Any, Sequence
from .schemas import SecurityEvent, Assessment, Signal
from .neural.anomaly import robust_anomaly_score
from .neural.calibration import calibrated_probability
from .adversarial.immune_graph import analyze_evidence_graph, source_balanced_scores

_EVENT_WEIGHTS = {
    "device_integrity": 1.0,
    "forensic_artifact": 1.0,
    "platform_alert": 0.95,
    "identity_risk": 0.85,
    "network_risk": 0.75,
    "app_risk": 0.75,
    "control_state": 0.55,
}


class _DefaultPolicy:
    max_weight = .50
    source_mean_weight = .20
    class_mean_weight = .15
    anomaly_weight = .15
    graph_weight = .30
    manual_threshold = .70
    high_threshold = .85


def _unique_by_event_id(events: Sequence[SecurityEvent]) -> list[SecurityEvent]:
    unique: dict[str, SecurityEvent] = {}
    for event in events:
        # First observation wins: same event identity cannot be replayed to inflate risk.
        unique.setdefault(event.event_id, event)
    return list(unique.values())


def assess_events_with_policy(events: Sequence[SecurityEvent], policy: Any) -> Assessment:
    xs = list(events)
    if not xs:
        return Assessment(case_id=str(uuid.uuid4()), risk_score=0.0, confidence=0.0,
                          disposition="observe", signals=[], requires_human_approval=True,
                          rationale=["No evidence supplied."])

    unique = _unique_by_event_id(xs)
    graph = analyze_evidence_graph(xs)
    scores_by_id: dict[str, float] = {}
    signals: list[Signal] = []
    independent_classes = set()
    sources = set()
    for e in unique:
        w = _EVENT_WEIGHTS.get(e.event_class.value, 0.5)
        score = max(0.0, min(1.0, e.severity * e.confidence * w))
        scores_by_id[e.event_id] = score
        independent_classes.add(e.event_class.value)
        sources.add(e.source.strip().lower())
        signals.append(Signal(name=e.event_class.value, score=score, evidence=[e.event_id]))

    weighted = list(scores_by_id.values())
    anomaly = robust_anomaly_score(weighted)
    source_mean, class_mean = source_balanced_scores(unique, scores_by_id)
    primary = (
        float(policy.max_weight) * max(weighted, default=0.0)
        + float(policy.source_mean_weight) * source_mean
        + float(policy.class_mean_weight) * class_mean
        + float(policy.anomaly_weight) * anomaly
    )
    # Evidence quality gates rather than merely adding more events. High graph
    # corroboration can modestly strengthen independent evidence; concentration,
    # replay and class monoculture reduce trust through poisoning_resistance_factor.
    graph_multiplier = (
        (1.0 - float(policy.graph_weight))
        + float(policy.graph_weight) * (0.55 + 0.45 * graph.corroboration_score)
    )
    quality = graph_multiplier * graph.poisoning_resistance_factor
    raw = max(0.0, min(1.0, primary * quality))

    evidence_count_for_calibration = min(4, max(1, len(independent_classes) + len(sources) - 1))
    risk = calibrated_probability(raw, evidence_count_for_calibration)
    confidence = min(1.0,
        0.20
        + 0.18 * len(independent_classes)
        + 0.14 * len(sources)
        + 0.20 * graph.corroboration_score
        - 0.20 * graph.replay_ratio
        - 0.18 * max(0.0, graph.source_concentration - .60)
    )

    high_threshold = float(policy.high_threshold)
    manual_threshold = float(policy.manual_threshold)
    if risk >= high_threshold and len(independent_classes) >= 2 and len(sources) >= 2:
        disposition = "containment_recommended"
    elif risk >= manual_threshold and graph.poisoning_resistance_factor >= .55:
        disposition = "investigate"
    elif (
        len(independent_classes) >= 3
        and len(sources) >= 3
        and graph.corroboration_score >= .70
        and risk >= .34
    ):
        # Low-and-slow convergence: several independent moderate observations
        # should trigger investigation without requiring one extreme signal.
        disposition = "investigate"
    elif (
        len(independent_classes) >= 2
        and len(sources) >= 2
        and graph.source_concentration <= .60
        and graph.poisoning_resistance_factor >= .80
        and (graph.corroboration_score >= .70 and risk >= .48 or risk >= .54)
    ):
        disposition = "investigate"
    else:
        disposition = "observe"

    rationale = [
        f"{len(unique)} unique authorized event(s) fused from {len(xs)} observation(s).",
        f"{len(independent_classes)} evidence class(es) and {len(sources)} independent source(s) contributed.",
        f"Evidence-graph corroboration={graph.corroboration_score:.3f}; poisoning resistance={graph.poisoning_resistance_factor:.3f}.",
        "Replay volume and single-source concentration cannot manufacture corroboration.",
        "No single weak anomaly is treated as proof of compromise.",
    ]
    return Assessment(case_id=str(uuid.uuid4()), risk_score=round(risk, 6), confidence=round(confidence, 6),
                      disposition=disposition, signals=signals, requires_human_approval=True, rationale=rationale)


def assess_events(events: list[SecurityEvent], manual_threshold: float = 0.70, high_threshold: float = 0.85) -> Assessment:
    policy = _DefaultPolicy()
    policy.manual_threshold = manual_threshold
    policy.high_threshold = high_threshold
    return assess_events_with_policy(events, policy)
