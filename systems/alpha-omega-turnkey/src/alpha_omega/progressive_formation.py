from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable, Mapping

from .progressive_models import PathKind, RouteCandidate, _stable_id


class FormationInnovationEngine:
    """Forms materially different route families and runs a bounded tournament."""

    def form_routes(self, raw: Mapping[str, Any]) -> tuple[RouteCandidate, ...]:
        objective = str(raw.get("description") or raw.get("objective") or "").strip()
        if not objective:
            raise ValueError("description or objective is required")
        # Reuse eligibility requires an explicitly verified capability reference.
        # A preferred surface is a route preference, not proof that reusable
        # implementation exists.
        reuse_refs = tuple(
            sorted(
                {
                    str(item).strip()
                    for item in [
                        *raw.get("existing_capabilities", []),
                        *raw.get("verified_reuse_refs", []),
                    ]
                    if str(item).strip()
                }
            )
        )
        unknowns = tuple(
            str(item).strip() for item in raw.get("unknowns", []) if str(item).strip()
        )
        hard_constraints = tuple(
            str(item).strip()
            for item in raw.get("hard_constraints", [])
            if str(item).strip()
        )
        has_reuse = bool(reuse_refs)
        uncertainty = min(1.0, 0.15 * len(unknowns))

        routes = (
            RouteCandidate(
                path_id=_stable_id("PATH", objective, PathKind.REUSE_OPTIMISE.value),
                kind=PathKind.REUSE_OPTIMISE,
                title="Reuse and optimise the strongest verified capability",
                rationale=(
                    "Minimise rebuild, dependency load and time-to-proof while "
                    "preserving the objective."
                ),
                reuse_refs=reuse_refs,
                assumptions=("Reusable capability remains current and proof-compatible.",),
                mission_fidelity=1.0,
                proof_strength=0.95 if has_reuse else 0.25,
                reversibility=0.95,
                information_gain=0.45,
                speed=0.95 if has_reuse else 0.35,
                cost_efficiency=0.98 if has_reuse else 0.45,
                owner_burden=0.10 if has_reuse else 0.45,
                risk=0.10 if has_reuse else 0.40,
                eligible=has_reuse,
                rejection_reasons=() if has_reuse else ("NO_VERIFIED_REUSE_CANDIDATE",),
            ),
            RouteCandidate(
                path_id=_stable_id("PATH", objective, PathKind.COMPOSE_EXTEND.value),
                kind=PathKind.COMPOSE_EXTEND,
                title="Compose and extend complementary existing capabilities",
                rationale="Create a minimum complete system from several bounded components.",
                reuse_refs=reuse_refs,
                assumptions=("Component interfaces can be normalised.",),
                mission_fidelity=0.98,
                proof_strength=0.80 if has_reuse else 0.58,
                reversibility=0.85,
                information_gain=0.70,
                speed=0.82 if has_reuse else 0.62,
                cost_efficiency=0.90,
                owner_burden=0.18,
                risk=0.18 + 0.20 * uncertainty,
            ),
            RouteCandidate(
                path_id=_stable_id("PATH", objective, PathKind.MATERIAL_NEW.value),
                kind=PathKind.MATERIAL_NEW,
                title="Build a materially new deterministic solution",
                rationale=(
                    "Use when existing capabilities cannot satisfy the complete "
                    "objective without distortion."
                ),
                reuse_refs=(),
                assumptions=(
                    "A new implementation is justified by a proven coverage gap.",
                ),
                mission_fidelity=0.96,
                proof_strength=0.60,
                reversibility=0.72,
                information_gain=0.82,
                speed=0.52,
                cost_efficiency=0.65,
                owner_burden=0.32,
                risk=0.30 + 0.25 * uncertainty,
            ),
            RouteCandidate(
                path_id=_stable_id(
                    "PATH", objective, PathKind.REVERSIBLE_EXPERIMENT.value
                ),
                kind=PathKind.REVERSIBLE_EXPERIMENT,
                title="Run the highest-information reversible experiment",
                rationale=(
                    "Resolve the largest decision-changing unknown before "
                    "committing to a larger build."
                ),
                reuse_refs=reuse_refs,
                assumptions=("Experiment is harmless, bounded and rollback-safe.",),
                mission_fidelity=0.88,
                proof_strength=0.70,
                reversibility=1.0,
                information_gain=min(1.0, 0.75 + uncertainty),
                speed=0.88,
                cost_efficiency=0.96,
                owner_burden=0.08,
                risk=0.08,
            ),
        )

        # A hard constraint does not make route formation impossible, but forces
        # selection away from weakly evidenced large builds until mapped.
        if hard_constraints:
            adjusted: list[RouteCandidate] = []
            for route in routes:
                if route.kind is PathKind.MATERIAL_NEW:
                    adjusted.append(
                        RouteCandidate(
                            **{
                                **asdict(route),
                                "kind": route.kind,
                                "risk": min(1.0, route.risk + 0.15),
                                "assumptions": route.assumptions
                                + (
                                    "Hard constraints must be resolved before "
                                    "material build.",
                                ),
                            }
                        )
                    )
                else:
                    adjusted.append(route)
            routes = tuple(adjusted)
        return routes

    @staticmethod
    def select_route(routes: Iterable[RouteCandidate]) -> RouteCandidate:
        eligible = [route for route in routes if route.eligible]
        if not eligible:
            raise ValueError("no eligible route candidate")
        eligible.sort(key=lambda route: (-route.score, route.path_id))
        return eligible[0]
