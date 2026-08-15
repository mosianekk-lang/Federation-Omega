from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence

AUTHORITY_CEILING = "A1_INTERNAL"
ALLOWED_AUTHORITIES = {"A0_READ", AUTHORITY_CEILING}


def _clamp(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _texts(values: Iterable[Any]) -> list[str]:
    return sorted({_text(v) for v in values if _text(v)})


@dataclass(frozen=True)
class RouteAssessment:
    route_id: str
    description: str
    authority: str
    support: float
    contradiction: float
    evidence_quality: float
    information_gain: float
    decision_impact: float
    reversibility: float
    dependency_diversity: float
    owner_burden: float
    latency: float
    risk: float
    replication: float
    independence: float
    confidence_index: float
    confidence_band: str
    score: float
    unresolved_falsifiers: tuple[str, ...] = ()
    high_severity_falsifiers: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    scenario_stability: Optional[float] = None


class CognitivePrecisionKernel:
    """Bounded decision-quality layer for ChatGov/Bubbles.

    It does not expand authority or turn analysis into fact. It ranks candidate
    routes, makes contradictions and falsifiers load-bearing, detects shared
    dependencies, selects high-information reversible tests through the existing
    EvidenceOps InformationGainRouteSelector, and stops premature convergence.
    """

    version = "1.0.0"
    authority_ceiling = AUTHORITY_CEILING
    external_effect = False

    def __init__(self, information_gain_selector: Any = None) -> None:
        if information_gain_selector is None:
            from evidenceops.innovation_engine import InformationGainRouteSelector
            information_gain_selector = InformationGainRouteSelector()
        self.information_gain_selector = information_gain_selector

    @staticmethod
    def _falsifiers(candidate: Mapping[str, Any]) -> tuple[list[str], list[str]]:
        unresolved: list[str] = []
        severe: list[str] = []
        for raw in candidate.get("falsifiers", ()) or ():
            if isinstance(raw, Mapping):
                if bool(raw.get("resolved")):
                    continue
                description = _text(raw.get("description") or raw.get("falsifier") or raw.get("id"))
                severity = _text(raw.get("severity")).upper() or "MEDIUM"
            else:
                description = _text(raw)
                severity = "MEDIUM"
            if not description:
                continue
            unresolved.append(description)
            if severity in {"HIGH", "CRITICAL"}:
                severe.append(description)
        return sorted(set(unresolved)), sorted(set(severe))

    @staticmethod
    def _scenario_stability(candidate: Mapping[str, Any]) -> Optional[float]:
        raw = candidate.get("scenario_scores")
        if not isinstance(raw, Mapping) or not raw:
            return None
        values = [_clamp(v, 0.5) for v in raw.values()]
        return round(1.0 - (max(values) - min(values)), 6)

    @staticmethod
    def _confidence(
        *,
        support: float,
        contradiction: float,
        evidence_quality: float,
        replication: float,
        independence: float,
        high_falsifier_count: int,
    ) -> tuple[float, str]:
        index = _clamp(
            0.34 * support
            + 0.28 * evidence_quality
            + 0.18 * replication
            + 0.20 * independence
            - 0.48 * contradiction
            - min(0.30, 0.15 * high_falsifier_count)
        )
        if index >= 0.72:
            band = "HIGH"
        elif index >= 0.48:
            band = "MEDIUM"
        else:
            band = "LOW"
        return round(index, 6), band

    def assess_route(self, candidate: Mapping[str, Any], index: int = 1) -> RouteAssessment:
        route_id = _text(candidate.get("route_id")) or f"ROUTE-{index:03d}"
        support = _clamp(candidate.get("support"), 0.5)
        contradiction = _clamp(candidate.get("contradiction"), 0.0)
        evidence_quality = _clamp(candidate.get("evidence_quality"), 0.5)
        information_gain = _clamp(candidate.get("information_gain"), 0.5)
        decision_impact = _clamp(candidate.get("decision_impact"), 0.5)
        reversibility = _clamp(candidate.get("reversibility"), 1.0)
        dependency_diversity = _clamp(candidate.get("dependency_diversity"), 0.5)
        owner_burden = _clamp(candidate.get("owner_burden"), 0.1)
        latency = _clamp(candidate.get("latency"), 0.2)
        risk = _clamp(candidate.get("risk"), 0.1)
        replication = _clamp(candidate.get("replication"), 0.0)
        independence = _clamp(candidate.get("independence"), 0.5)
        unresolved, severe = self._falsifiers(candidate)
        scenario_stability = self._scenario_stability(candidate)

        confidence_index, confidence_band = self._confidence(
            support=support,
            contradiction=contradiction,
            evidence_quality=evidence_quality,
            replication=replication,
            independence=independence,
            high_falsifier_count=len(severe),
        )

        positive = (
            (0.20 + 0.80 * support)
            * (0.25 + 0.75 * evidence_quality)
            * (0.35 + 0.65 * decision_impact)
            * (0.40 + 0.60 * information_gain)
            * (0.45 + 0.55 * reversibility)
            * (0.55 + 0.45 * dependency_diversity)
        )
        if scenario_stability is not None:
            positive *= 0.65 + 0.35 * scenario_stability

        penalty = (
            0.18
            + 1.35 * contradiction
            + 0.50 * risk
            + 0.35 * owner_burden
            + 0.25 * latency
            + 0.18 * len(unresolved)
            + 0.30 * len(severe)
        )
        score = round(positive / penalty, 8)

        return RouteAssessment(
            route_id=route_id,
            description=_text(candidate.get("description")),
            authority=_text(candidate.get("authority")) or AUTHORITY_CEILING,
            support=support,
            contradiction=contradiction,
            evidence_quality=evidence_quality,
            information_gain=information_gain,
            decision_impact=decision_impact,
            reversibility=reversibility,
            dependency_diversity=dependency_diversity,
            owner_burden=owner_burden,
            latency=latency,
            risk=risk,
            replication=replication,
            independence=independence,
            confidence_index=confidence_index,
            confidence_band=confidence_band,
            score=score,
            unresolved_falsifiers=tuple(unresolved),
            high_severity_falsifiers=tuple(severe),
            dependencies=tuple(_texts(candidate.get("dependencies", ()) or ())),
            scenario_stability=scenario_stability,
        )

    def rank_routes(self, candidates: Sequence[Mapping[str, Any]]) -> list[RouteAssessment]:
        ranked = [self.assess_route(candidate, i) for i, candidate in enumerate(candidates, start=1)]
        ranked = [route for route in ranked if route.authority in ALLOWED_AUTHORITIES]
        ranked.sort(key=lambda route: (-route.score, route.route_id))
        return ranked

    @staticmethod
    def dependency_risk(ranked: Sequence[RouteAssessment], top_n: int = 3) -> dict[str, Any]:
        top = list(ranked[:top_n])
        counts: dict[str, int] = {}
        for route in top:
            for dependency in set(route.dependencies):
                counts[dependency] = counts.get(dependency, 0) + 1
        shared = sorted(dep for dep, count in counts.items() if count >= 2)
        universal = sorted(dep for dep, count in counts.items() if top and count == len(top))
        return {
            "top_route_count": len(top),
            "shared_dependencies": shared,
            "universal_single_points": universal,
            "risk_state": "HIGH" if universal else ("WATCH" if shared else "LOW"),
        }

    @staticmethod
    def cognitive_load(metrics: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        metrics = metrics or {}
        path_count = max(0, int(metrics.get("path_count", 0) or 0))
        contradiction_count = max(0, int(metrics.get("contradiction_count", 0) or 0))
        stale_fact_count = max(0, int(metrics.get("stale_fact_count", 0) or 0))
        owner_corrections = max(0, int(metrics.get("owner_corrections", 0) or 0))
        retrievals = max(0, int(metrics.get("retrievals", 0) or 0))
        unresolved_dependencies = max(0, int(metrics.get("unresolved_dependencies", 0) or 0))

        load = min(
            1.0,
            0.18 * min(1.0, path_count / 8.0)
            + 0.17 * min(1.0, contradiction_count / 6.0)
            + 0.18 * min(1.0, stale_fact_count / 4.0)
            + 0.22 * min(1.0, owner_corrections / 2.0)
            + 0.12 * min(1.0, retrievals / 12.0)
            + 0.13 * min(1.0, unresolved_dependencies / 5.0),
        )
        if load >= 0.72:
            state = "CHECKPOINT_AND_COMPRESS"
        elif load >= 0.48:
            state = "WATCH_AND_PRUNE"
        else:
            state = "NORMAL"
        return {"index": round(load, 6), "state": state}

    def select_next_test(self, experiments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        result = self.information_gain_selector.run(experiments)
        if hasattr(result, "as_dict"):
            return result.as_dict()
        if hasattr(result, "output"):
            return {
                "status": getattr(result, "status", ""),
                "output": dict(result.output),
                "violations": list(getattr(result, "violations", ())),
            }
        if isinstance(result, Mapping):
            return dict(result)
        raise TypeError("Information-gain selector returned unsupported result type")

    @staticmethod
    def convergence_state(ranked: Sequence[RouteAssessment]) -> dict[str, Any]:
        if not ranked:
            return {"state": "NO_AUTHORISED_ROUTE", "leading_route": None, "margin": 0.0, "reasons": []}
        leader = ranked[0]
        second_score = ranked[1].score if len(ranked) > 1 else 0.0
        margin = round(leader.score - second_score, 8)
        reasons: list[str] = []
        if leader.confidence_band == "LOW":
            reasons.append("LOW_CONFIDENCE")
        if leader.contradiction > 0.25:
            reasons.append("MATERIAL_CONTRADICTION")
        if leader.high_severity_falsifiers:
            reasons.append("HIGH_SEVERITY_FALSIFIER_OPEN")
        if len(ranked) > 1 and margin < 0.08:
            reasons.append("ROUTE_MARGIN_TOO_SMALL")
        if leader.score < 0.35:
            reasons.append("LEADING_ROUTE_WEAK")
        state = "READY_TO_ACT_WITHIN_AUTHORITY" if not reasons else "HOLD_FOR_HIGH_INFORMATION_TEST"
        return {
            "state": state,
            "leading_route": leader.route_id,
            "margin": margin,
            "reasons": reasons,
        }

    def compile_decision(
        self,
        *,
        candidates: Sequence[Mapping[str, Any]],
        experiments: Sequence[Mapping[str, Any]] = (),
        context_metrics: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        ranked = self.rank_routes(candidates)
        convergence = self.convergence_state(ranked)
        dependencies = self.dependency_risk(ranked)
        load = self.cognitive_load(context_metrics)
        next_test = self.select_next_test(experiments) if experiments else None

        leading = ranked[0] if ranked else None
        selected = (
            leading.route_id
            if leading and convergence["state"] == "READY_TO_ACT_WITHIN_AUTHORITY"
            else None
        )
        adversarial_questions = []
        if leading:
            adversarial_questions = [
                f"What strongest evidence contradicts {leading.route_id}?",
                f"What alternative explanation fits the same observations as {leading.route_id}?",
                f"What result would force {leading.route_id} to be downgraded or retracted?",
                "Are the apparently independent routes sharing one hidden dependency?",
                "Would the preferred route still dominate under the strongest plausible adverse scenario?",
            ]

        body = {
            "kernel": "CHATGOV_COGNITIVE_PRECISION_V1",
            "version": self.version,
            "authority_ceiling": self.authority_ceiling,
            "external_effect": self.external_effect,
            "ranked_routes": [asdict(route) for route in ranked],
            "leading_route": leading.route_id if leading else None,
            "selected_route": selected,
            "convergence": convergence,
            "dependency_risk": dependencies,
            "cognitive_load": load,
            "next_information_test": next_test,
            "adversarial_questions": adversarial_questions,
            "truth_boundary": (
                "Scores, confidence bands and counterfactual stability are decision aids, not facts, "
                "probabilities of legal/real-world success, authority grants or provider-effect proof."
            ),
        }
        body["receipt_sha256"] = _sha(body)
        return body
