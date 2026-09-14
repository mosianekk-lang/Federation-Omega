from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable

from .forest_integrity_adapter import ForestIntegrityShadowAdapter
from .forest_omega import ForestFirstOmega, ForestOmegaContext


@dataclass(frozen=True, slots=True)
class EquivalenceScenario:
    scenario_id: str
    context: ForestOmegaContext
    expected_classification: str
    note: str = ""


@dataclass(frozen=True, slots=True)
class EquivalenceRow:
    scenario_id: str
    legacy_selected_path: str | None
    typed_selected_path: str | None
    legacy_owner_hold: bool
    typed_release_ready: bool
    selection_preserved: bool
    declared_true_unbound_count: int
    unverified_evidence_count: int
    routes_with_missing_admissibility: int
    missing_admissibility_fields: int
    classification: str
    explanation: str


@dataclass(frozen=True, slots=True)
class EquivalenceReport:
    schema: str
    scenario_count: int
    preserved_count: int
    safety_tightened_count: int
    unexplained_divergence_count: int
    promotion_ready: bool
    rows: tuple[dict[str, Any], ...]
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False
    runtime_rewired: bool = False
    truth_class: str = "DETERMINISTIC_SHADOW_EQUIVALENCE_NOT_OPERATIONAL_OUTCOME_PROOF"


def _selected_path_id(result: Any) -> str | None:
    selected = result.decision.get("selected_path")
    if not selected:
        return None
    return str(selected.get("route_id"))


def _typed_selected_path_id(report: Any) -> str | None:
    if not report.admissible_paths:
        return None
    return str(report.admissible_paths[0]["path_id"])


def _classify(
    *,
    legacy_selected: str | None,
    typed_selected: str | None,
    legacy_owner_hold: bool,
    typed_release_ready: bool,
    missing_fields: int,
    typed_admissible_ids: set[str],
) -> tuple[str, str]:
    if legacy_selected == typed_selected:
        return (
            "PRESERVED",
            "Legacy and typed routing select the same admissible path.",
        )

    if legacy_selected is not None and legacy_selected not in typed_admissible_ids:
        if missing_fields:
            return (
                "SAFETY_TIGHTENED",
                "Legacy selected a path whose typed admissibility contract is incomplete; typed routing fails closed.",
            )
        return (
            "SAFETY_TIGHTENED",
            "Legacy selected a path that fails one or more explicit admissibility gates; typed routing excludes it before ranking.",
        )

    if legacy_owner_hold and not typed_release_ready:
        return (
            "PRESERVED",
            "Both interpretations retain a hold at the consequential authority boundary.",
        )

    return (
        "UNEXPLAINED_DIVERGENCE",
        "Typed and legacy behavior differ without an identified admissibility or authority justification.",
    )


class ForestIntegrityEquivalenceHarness:
    """Compare current ForestOmega behavior with the typed integrity shadow.

    The harness never changes ForestFirstOmega.run(), performs no provider action,
    and does not treat stricter typed behavior as automatically superior. A delta
    is promotion-safe only when it is either equivalent or explicitly explained
    by a fail-closed admissibility/authority condition.
    """

    def __init__(self) -> None:
        self.legacy = ForestFirstOmega()
        self.typed = ForestIntegrityShadowAdapter()

    def evaluate(self, scenario: EquivalenceScenario) -> EquivalenceRow:
        legacy = self.legacy.run(scenario.context)
        typed = self.typed.evaluate(scenario.context)

        legacy_selected = _selected_path_id(legacy)
        typed_selected = _typed_selected_path_id(typed)
        typed_ids = {str(row["path_id"]) for row in typed.admissible_paths}
        missing_fields = sum(len(fields) for fields in typed.missing_route_fields.values())
        classification, explanation = _classify(
            legacy_selected=legacy_selected,
            typed_selected=typed_selected,
            legacy_owner_hold=bool(legacy.decision.get("owner_hold")),
            typed_release_ready=typed.consequential_release_ready,
            missing_fields=missing_fields,
            typed_admissible_ids=typed_ids,
        )

        return EquivalenceRow(
            scenario_id=scenario.scenario_id,
            legacy_selected_path=legacy_selected,
            typed_selected_path=typed_selected,
            legacy_owner_hold=bool(legacy.decision.get("owner_hold")),
            typed_release_ready=typed.consequential_release_ready,
            selection_preserved=legacy_selected == typed_selected,
            declared_true_unbound_count=sum(
                row["typed_state"] == "DECLARED_TRUE_UNBOUND"
                for row in typed.control_assessments
            ),
            unverified_evidence_count=sum(
                row["truth_state"].value == "UNVERIFIED"
                if hasattr(row["truth_state"], "value")
                else str(row["truth_state"]) == "UNVERIFIED"
                for row in typed.evidence_atoms
            ),
            routes_with_missing_admissibility=len(typed.missing_route_fields),
            missing_admissibility_fields=missing_fields,
            classification=classification,
            explanation=explanation,
        )

    def run(self, scenarios: Iterable[EquivalenceScenario]) -> EquivalenceReport:
        rows = tuple(self.evaluate(scenario) for scenario in scenarios)
        preserved = sum(row.classification == "PRESERVED" for row in rows)
        tightened = sum(row.classification == "SAFETY_TIGHTENED" for row in rows)
        unexplained = sum(row.classification == "UNEXPLAINED_DIVERGENCE" for row in rows)
        return EquivalenceReport(
            schema="FOREST_FIRST_INTEGRITY_EQUIVALENCE_V1",
            scenario_count=len(rows),
            preserved_count=preserved,
            safety_tightened_count=tightened,
            unexplained_divergence_count=unexplained,
            promotion_ready=bool(rows) and unexplained == 0,
            rows=tuple(asdict(row) for row in rows),
        )


def admitted_reference_context(**overrides: Any) -> ForestOmegaContext:
    data: dict[str, Any] = {
        "matter_id": "FOREST-OMEGA-EQUIVALENCE",
        "objective": "Protect the objective while discovering the decision-changing truth",
        "desired_outcome": "Strongest lawful reversible path selected with proof preserved",
        "high_stakes": True,
        "consequence": 0.9,
        "uncertainty": 0.8,
        "dependency_density": 0.8,
        "adversarial_complexity": 0.8,
        "root_hypotheses": ("The immediate event may be part of a larger strategic pattern",),
        "tree_facts": ("primary fact A", "primary fact B"),
        "evidence_dependencies": ("primary record", "decision chain"),
        "cross_lane_risks": ("waiver", "forum contamination"),
        "route_alternatives": (
            {
                "route_id": "REUSE-PRIMARY",
                "route_type": "REUSE",
                "available": True,
                "authorised": True,
                "feasibility": 0.9,
                "proof_strength": 0.95,
                "reversibility": 1.0,
                "speed": 0.8,
                "strategic_value": 0.95,
                "owner_burden": 0.0,
                "privacy_cost": 0.1,
                "maintenance_cost": 0.1,
                "information_gain": 0.9,
            },
            {
                "route_id": "NEW-BUILD",
                "route_type": "NEW_BUILD",
                "available": True,
                "authorised": True,
                "feasibility": 0.5,
                "proof_strength": 0.6,
                "reversibility": 0.7,
                "speed": 0.3,
                "strategic_value": 0.6,
                "owner_burden": 0.4,
                "privacy_cost": 0.2,
                "maintenance_cost": 0.7,
                "information_gain": 0.5,
            },
        ),
    }
    data.update(overrides)
    return ForestOmegaContext(**data)


def fully_admissible(raw: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    result = dict(raw)
    result.update(
        available=True,
        authorised=True,
        safe=True,
        deadline_viable=True,
        privacy_acceptable=True,
        cost_acceptable=True,
        dependencies_ready=True,
        evidence_sufficient=True,
        rollback_available=True,
    )
    result.update(overrides)
    return result


def reference_scenarios() -> tuple[EquivalenceScenario, ...]:
    canonical = admitted_reference_context()
    canonical_routes = tuple(dict(route) for route in canonical.route_alternatives)
    explicit_routes = tuple(fully_admissible(route) for route in canonical_routes)
    unsafe_high = fully_admissible(
        canonical_routes[0],
        route_id="UNAUTHORISED-HIGH",
        authorised=False,
        strategic_value=1.0,
        proof_strength=1.0,
        reversibility=1.0,
    )
    safe_lower = fully_admissible(
        canonical_routes[1],
        route_id="AUTHORISED-LOWER",
        strategic_value=0.7,
        proof_strength=0.8,
        reversibility=0.9,
    )
    return (
        EquivalenceScenario(
            "ADMITTED-LEGACY-FIXTURE",
            canonical,
            "SAFETY_TIGHTENED",
            "Current admitted fixture omits seven typed admissibility fields per route.",
        ),
        EquivalenceScenario(
            "EXPLICITLY-ADMISSIBLE-EQUIVALENCE",
            replace(canonical, route_alternatives=explicit_routes),
            "PRESERVED",
            "Adding explicit admissibility should preserve the incumbent best route.",
        ),
        EquivalenceScenario(
            "UNAUTHORISED-HIGH-SCORE",
            replace(canonical, route_alternatives=(unsafe_high, safe_lower)),
            "SAFETY_TIGHTENED",
            "Typed eligibility must exclude an unauthorised route before ranking.",
        ),
        EquivalenceScenario(
            "CONSEQUENTIAL-HOLD",
            replace(
                canonical,
                consequential_action_planned=True,
                route_alternatives=explicit_routes,
            ),
            "PRESERVED",
            "Consequential work must remain held for owner authority.",
        ),
    )


__all__ = [
    "EquivalenceReport",
    "EquivalenceRow",
    "EquivalenceScenario",
    "ForestIntegrityEquivalenceHarness",
    "admitted_reference_context",
    "fully_admissible",
    "reference_scenarios",
]
