from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
from typing import Sequence

from .twin import AdversarialScenario, ScenarioCase, scenario_suite
from .immune_graph import analyze_evidence_graph
from .neural_sentinel import NeuralSentinel, NeuralSentinelReceipt, feature_vector
from .evolution_tournament import TournamentReceipt, run_policy_tournament
from ..fusion import assess_events
from ..normalize import normalize_event


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario: str
    expected_threat_like: bool
    deterministic_disposition: str
    deterministic_risk: float
    graph_poisoning_resistance: float
    neural_shadow_risk: float
    expected_gate_passed: bool


@dataclass(frozen=True, slots=True)
class AdversarialCourtReceipt:
    schema: str
    defensive_only: bool
    synthetic_only: bool
    scenario_count: int
    scenario_pass_count: int
    threat_recall: float
    benign_specificity: float
    replay_resistance_passed: bool
    source_concentration_resistance_passed: bool
    privacy_minimization_passed: bool
    neural_receipt: NeuralSentinelReceipt
    tournament_receipt: TournamentReceipt
    auto_promotion_performed: bool
    provider_effect_performed: bool
    stable_promotion_authorized: bool
    results: tuple[ScenarioResult, ...]
    receipt_sha256: str


def _hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _rank(disposition: str) -> int:
    return {"observe": 0, "investigate": 1, "containment_recommended": 2}[disposition]


def _neural_data(cases: Sequence[ScenarioCase]) -> list[tuple[tuple[float, ...], int]]:
    rows = []
    for case in cases:
        x = feature_vector(case.events)
        y = 1 if case.expected_threat_like else 0
        rows.append((x, y))
        # Deterministic nearby feature variants increase the small synthetic training set.
        for scale in (.94, 1.06):
            varied = tuple(max(0.0, min(1.0, value * scale if i < 2 else value)) for i, value in enumerate(x))
            rows.append((varied, y))
    return rows


def run_adversarial_court(*, seed: int = 7) -> AdversarialCourtReceipt:
    cases = scenario_suite(seed=seed)
    data = _neural_data(cases)
    # Deterministic interleaved holdout keeps benign/threat scenario families in
    # both sets instead of accidentally holding out only the final scenario types.
    holdout = [row for i, row in enumerate(data) if i % 4 == 0]
    train = [row for i, row in enumerate(data) if i % 4 != 0]
    neural, neural_receipt = NeuralSentinel.train_synthetic_shadow(train, holdout)

    results = []
    threat_hits = benign_hits = 0
    threat_total = benign_total = 0
    privacy_ok = False
    replay_ok = False
    concentration_ok = False
    scenario_passes = 0

    for case in cases:
        assessment = assess_events(list(case.events))
        report = analyze_evidence_graph(case.events)
        neural_risk = neural.predict(feature_vector(case.events))
        expected_gate = (
            (_rank(assessment.disposition) >= _rank(case.expected_min_disposition))
            if case.expected_threat_like
            else assessment.disposition == "observe"
        )
        if case.expected_threat_like:
            threat_total += 1
            threat_hits += assessment.disposition != "observe"
        else:
            benign_total += 1
            benign_hits += assessment.disposition == "observe"

        if case.scenario is AdversarialScenario.REPLAY_FLOOD:
            replay_ok = assessment.disposition == "observe" and report.replay_ratio > .80
        elif case.scenario is AdversarialScenario.SOURCE_CONCENTRATION:
            concentration_ok = assessment.disposition == "observe" and report.source_concentration >= .90
        elif case.scenario is AdversarialScenario.PRIVACY_PRESSURE:
            normalized = normalize_event(case.events[0])
            privacy_ok = (
                normalized.attributes.get("message_body") == "[minimized]" and
                normalized.attributes.get("token") == "[minimized]" and
                normalized.attributes.get("safe_flag") == "ok"
            )

        pass_case = expected_gate
        if case.scenario is AdversarialScenario.REPLAY_FLOOD:
            pass_case = pass_case and replay_ok
        if case.scenario is AdversarialScenario.SOURCE_CONCENTRATION:
            pass_case = pass_case and concentration_ok
        if case.scenario is AdversarialScenario.PRIVACY_PRESSURE:
            pass_case = pass_case and privacy_ok
        scenario_passes += pass_case

        results.append(ScenarioResult(
            scenario=case.scenario.value,
            expected_threat_like=case.expected_threat_like,
            deterministic_disposition=assessment.disposition,
            deterministic_risk=assessment.risk_score,
            graph_poisoning_resistance=report.poisoning_resistance_factor,
            neural_shadow_risk=round(neural_risk, 6),
            expected_gate_passed=bool(pass_case),
        ))

    tournament = run_policy_tournament(cases)
    recall = threat_hits / threat_total if threat_total else 1.0
    specificity = benign_hits / benign_total if benign_total else 1.0
    body = {
        "schema": "AEGIS_ADVERSARIAL_PRODUCTION_COURT_V1",
        "defensive_only": True,
        "synthetic_only": True,
        "scenario_count": len(cases),
        "scenario_pass_count": scenario_passes,
        "threat_recall": round(recall, 6),
        "benign_specificity": round(specificity, 6),
        "replay_resistance_passed": replay_ok,
        "source_concentration_resistance_passed": concentration_ok,
        "privacy_minimization_passed": privacy_ok,
        "neural_receipt": asdict(neural_receipt),
        "tournament_receipt": asdict(tournament),
        "auto_promotion_performed": False,
        "provider_effect_performed": False,
        "stable_promotion_authorized": False,
        "results": [asdict(r) for r in results],
    }
    return AdversarialCourtReceipt(
        schema=body["schema"], defensive_only=True, synthetic_only=True,
        scenario_count=len(cases), scenario_pass_count=scenario_passes,
        threat_recall=body["threat_recall"], benign_specificity=body["benign_specificity"],
        replay_resistance_passed=replay_ok,
        source_concentration_resistance_passed=concentration_ok,
        privacy_minimization_passed=privacy_ok,
        neural_receipt=neural_receipt, tournament_receipt=tournament,
        auto_promotion_performed=False, provider_effect_performed=False,
        stable_promotion_authorized=False, results=tuple(results),
        receipt_sha256=_hash(body),
    )
