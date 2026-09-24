from __future__ import annotations

import importlib
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from formation_omega.powerhouse import FormationOmega
from sol_61_runtime.sol_62_frontier_primitives import digest
from sol_61_runtime.sol_62_complete_client_runtime import RouteCandidate


SCHEMA = "SOL62_ALPHA_OMEGA_FORMATION_BINDING_V1"
AUTHORITY_CEILING = "A1_INTERNAL"


@dataclass(frozen=True, slots=True)
class StrategyRoute:
    route_id: str
    family: str
    complete: bool
    authorised: bool
    reversible: bool
    burden: float
    proof_quality: float
    capability_hypothesis: str
    falsifier: str
    source_route_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StrategyReceipt:
    schema: str
    mission_id: str
    objective: str
    reason: str
    selected_route_id: str
    selected_family: str
    reuse_vs_build: str
    implementation_required: bool
    formation_innovation_packet: Mapping[str, Any]
    alpha_omega_packet: Mapping[str, Any] | None
    alternatives: tuple[Mapping[str, Any], ...]
    authority_ceiling: str
    external_effect: bool
    receipt_sha256: str
    truth_boundary: Mapping[str, bool]


class Sol62AlphaOmegaFormationBinding:
    """Compose canonical Formation + Formation Innovation + Alpha->Omega into SOL 6.2.

    This is an adapter. SOL 6.2 remains mission/effect/proof truth. Formation
    remains route formation, EvidenceOps remains the innovation foundry, and
    Alpha->Omega remains build-plan compiler. No authority is inherited.
    """

    def __init__(self, *, repo_root: str | Path | None = None, workspace: str | Path | None = None) -> None:
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[2])
        self.workspace = Path(workspace or (self.repo_root / ".sol62-alpha-omega"))
        self.workspace.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _route_score(route: RouteCandidate) -> float:
        score = float(route.priority)
        score += 40.0 if route.current else -100.0
        score += 40.0 if route.callable else -100.0
        score += 40.0 if route.authorized else -100.0
        score += 40.0 if route.privacy_ok else -100.0
        return score

    def _families(
        self,
        *,
        routes: Sequence[RouteCandidate],
        reason: str,
        selected_upgrade_genes: Sequence[Mapping[str, Any]] = (),
    ) -> tuple[StrategyRoute, ...]:
        eligible = tuple(
            route for route in routes
            if route.current and route.callable and route.authorized and route.privacy_ok
        )
        best = sorted(eligible, key=lambda route: (-self._route_score(route), route.route_id))
        best_ids = tuple(route.route_id for route in best[:3])
        has_route = bool(best)

        reuse = StrategyRoute(
            route_id="FORMATION:REUSE_OR_OPTIMISE",
            family="REUSE_OR_OPTIMISE",
            complete=has_route,
            authorised=has_route,
            reversible=True,
            burden=1.0,
            proof_quality=0.85 if has_route else 0.0,
            capability_hypothesis="Existing qualified SOL route can satisfy the mission with optimisation only.",
            falsifier="No current callable authorised privacy-fit route survives fresh readback.",
            source_route_ids=best_ids[:1],
        )
        compose = StrategyRoute(
            route_id="FORMATION:COMPOSE_OR_EXTEND",
            family="COMPOSE_OR_EXTEND",
            complete=len(best_ids) >= 1,
            authorised=len(best_ids) >= 1,
            reversible=True,
            burden=2.0,
            proof_quality=0.90 if best_ids else 0.0,
            capability_hypothesis="Compose existing SOL/FUSE capabilities and changed-route continuation.",
            falsifier="Required residual cannot be closed by existing capability composition.",
            source_route_ids=best_ids,
        )
        build = StrategyRoute(
            route_id="FORMATION:BUILD_MINIMUM_RESIDUAL",
            family="MATERIALLY_NEW_OR_INNOVATIVE",
            complete=bool(selected_upgrade_genes) or not has_route,
            authorised=True,
            reversible=True,
            burden=4.0,
            proof_quality=0.75,
            capability_hypothesis="Build only the smallest true residual through existing governed foundry lanes.",
            falsifier="Overlap collapse proves an equivalent admitted FUSE capability already exists.",
        )
        experiment = StrategyRoute(
            route_id="FORMATION:HIGHEST_INFORMATION_REVERSIBLE_EXPERIMENT",
            family="HIGHEST_INFORMATION_REVERSIBLE_EXPERIMENT",
            complete=True,
            authorised=True,
            reversible=True,
            burden=1.5,
            proof_quality=0.70,
            capability_hypothesis="Run the lowest-cost reversible experiment that most reduces route uncertainty.",
            falsifier="Experiment cannot change a material routing/build decision.",
        )
        return (reuse, compose, build, experiment)

    def _select(self, objective: str, candidates: Sequence[StrategyRoute]) -> StrategyRoute:
        selected = FormationOmega.smallest_sufficient_decision(
            objective,
            [
                {
                    **asdict(candidate),
                    "complete": candidate.complete,
                    "authorised": candidate.authorised,
                    "reversible": candidate.reversible,
                    "burden": candidate.burden,
                    "proof_quality": candidate.proof_quality,
                }
                for candidate in candidates
            ],
        )
        route_id = str(selected["route_id"])
        return next(candidate for candidate in candidates if candidate.route_id == route_id)

    def _formation_innovation_packet(
        self,
        *,
        mission_id: str,
        objective: str,
        reason: str,
        candidates: Sequence[StrategyRoute],
        selected: StrategyRoute,
        selected_upgrade_genes: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Compile an effect-free request for the existing EvidenceOps foundry."""
        payload = {
            "schema": "SOL62_FORMATION_INNOVATION_REQUEST_V1",
            "cycle_id": "SOL62-FORMATION-" + digest(
                {"mission_id": mission_id, "objective": objective, "reason": reason}
            )[:20].upper(),
            "mission_id": mission_id,
            "objective": objective,
            "reason": reason,
            "route_candidates": [asdict(item) for item in candidates],
            "selected_route_id": selected.route_id,
            "innovation_candidates": [dict(item) for item in selected_upgrade_genes],
            "required_output": {
                "foundry_result_type": "FoundryCycleResult",
                "authority_ceiling": AUTHORITY_CEILING,
                "external_effect": False,
                "must_include": [
                    "algorithm_results",
                    "innovation_delta",
                    "learning_delta",
                    "maturity",
                    "proof",
                ],
            },
            "producer": "EVIDENCEOPS-ALGORITHM-FOUNDRY",
            "consumer": "SOL62_ALPHA_OMEGA_FORMATION_BINDING",
            "authority_ceiling": AUTHORITY_CEILING,
            "external_effect": False,
        }
        payload["request_sha256"] = digest(payload)
        return payload

    def _alpha_omega_plan(
        self,
        *,
        mission_id: str,
        objective: str,
        constraints: Sequence[str],
        preferred_surfaces: Sequence[str],
        selected: StrategyRoute,
    ) -> dict[str, Any] | None:
        if selected.family not in {"MATERIALLY_NEW_OR_INNOVATIVE"}:
            return None

        source_root = self.repo_root / "systems" / "alpha-omega-turnkey" / "src"
        if not source_root.exists():
            return {
                "status": "SOURCE_PRESENT_UNRESOLVED_IMPORT",
                "producer": "ALPHA_OMEGA_TURNKEY_BUILD_ENGINE",
                "implementation_required": True,
            }
        source_text = str(source_root)
        inserted = False
        if source_text not in sys.path:
            sys.path.insert(0, source_text)
            inserted = True
        try:
            module = importlib.import_module("alpha_omega")
            engine_cls = getattr(module, "AlphaOmegaEngine")
            engine = engine_cls(self.workspace / mission_id)
            plan = engine.build_plan(
                {
                    "title": f"SOL62 {mission_id}",
                    "description": objective,
                    "outcomes": ["SOL62_VERIFIED_REALITY"],
                    "constraints": list(constraints),
                    "preferred_surfaces": list(preferred_surfaces),
                }
            )
            body = plan.to_dict()
            body["producer"] = "ALPHA_OMEGA_TURNKEY_BUILD_ENGINE"
            body["authority_ceiling"] = AUTHORITY_CEILING
            body["external_effect"] = False
            body["provider_runtime_verified"] = False
            body["plan_sha256"] = digest(body)
            return body
        finally:
            if inserted:
                try:
                    sys.path.remove(source_text)
                except ValueError:
                    pass

    def compile(
        self,
        *,
        mission_id: str,
        objective: str,
        reason: str,
        routes: Sequence[RouteCandidate],
        constraints: Sequence[str] = (),
        preferred_surfaces: Sequence[str] = (),
        selected_upgrade_genes: Sequence[Mapping[str, Any]] = (),
    ) -> StrategyReceipt:
        candidates = self._families(
            routes=routes,
            reason=reason,
            selected_upgrade_genes=selected_upgrade_genes,
        )
        selected = self._select(objective, candidates)
        implementation_required = selected.family == "MATERIALLY_NEW_OR_INNOVATIVE"
        innovation = self._formation_innovation_packet(
            mission_id=mission_id,
            objective=objective,
            reason=reason,
            candidates=candidates,
            selected=selected,
            selected_upgrade_genes=selected_upgrade_genes,
        )
        alpha_omega = self._alpha_omega_plan(
            mission_id=mission_id,
            objective=objective,
            constraints=constraints,
            preferred_surfaces=preferred_surfaces,
            selected=selected,
        )
        reuse_vs_build = "BUILD_MINIMUM" if implementation_required else (
            "COMPOSE" if selected.family == "COMPOSE_OR_EXTEND" else "REUSE"
        )
        truth_boundary = {
            "formation_route_compiled": True,
            "formation_foundry_executed": False,
            "alpha_omega_plan_compiled": alpha_omega is not None,
            "alpha_omega_local_build_executed": False,
            "provider_execution_verified": False,
            "source_admitted": False,
            "authority_widened": False,
            "external_effect_created": False,
        }
        material = {
            "schema": SCHEMA,
            "mission_id": mission_id,
            "objective": objective,
            "reason": reason,
            "selected_route_id": selected.route_id,
            "selected_family": selected.family,
            "reuse_vs_build": reuse_vs_build,
            "implementation_required": implementation_required,
            "formation_innovation_packet": innovation,
            "alpha_omega_packet": alpha_omega,
            "alternatives": [asdict(item) for item in candidates],
            "authority_ceiling": AUTHORITY_CEILING,
            "external_effect": False,
            "truth_boundary": truth_boundary,
        }
        return StrategyReceipt(
            schema=SCHEMA,
            mission_id=mission_id,
            objective=objective,
            reason=reason,
            selected_route_id=selected.route_id,
            selected_family=selected.family,
            reuse_vs_build=reuse_vs_build,
            implementation_required=implementation_required,
            formation_innovation_packet=innovation,
            alpha_omega_packet=alpha_omega,
            alternatives=tuple(asdict(item) for item in candidates),
            authority_ceiling=AUTHORITY_CEILING,
            external_effect=False,
            receipt_sha256=digest(material),
            truth_boundary=truth_boundary,
        )


def receipt_to_dict(receipt: StrategyReceipt) -> dict[str, Any]:
    return {
        **asdict(receipt),
        "formation_innovation_packet": dict(receipt.formation_innovation_packet),
        "alpha_omega_packet": (
            dict(receipt.alpha_omega_packet) if receipt.alpha_omega_packet is not None else None
        ),
        "alternatives": [dict(item) for item in receipt.alternatives],
        "truth_boundary": dict(receipt.truth_boundary),
    }
