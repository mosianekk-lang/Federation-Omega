from __future__ import annotations

import importlib
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from evidenceops.innovation_engine.foundry import EvidenceOpsAlgorithmFoundry
from evidenceops.innovation_engine.of50_adapter import compile_of50_formation_decision
from formation_omega.powerhouse import FormationOmega
from sol_61_runtime.sol_62_frontier_primitives import digest
from sol_61_runtime.sol_62_complete_client_runtime import RouteCandidate


SCHEMA = "SOL62_ALPHA_OMEGA_FORMATION_BINDING_V2"
AUTHORITY_CEILING = "A1_INTERNAL"
FORMATION_PRODUCER = "EVIDENCEOPS-ALGORITHM-FOUNDRY"
ALPHA_OMEGA_PRODUCER = "ALPHA_OMEGA_TURNKEY_BUILD_ENGINE"


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

    @property
    def score(self) -> float:
        if not (self.complete and self.authorised and self.reversible):
            return -1_000_000.0
        return round((self.proof_quality * 100.0) - (self.burden * 10.0), 6)


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
    formation_foundry_result: Mapping[str, Any]
    formation_decision: Mapping[str, Any]
    alpha_omega_result: Mapping[str, Any] | None
    alternatives: tuple[Mapping[str, Any], ...]
    authority_ceiling: str
    external_effect: bool
    receipt_sha256: str
    truth_boundary: Mapping[str, bool]


class Sol62AlphaOmegaFormationBinding:
    """Adopt canonical Formation Innovation and Alpha->Omega beneath SOL 6.2.

    Roles remain separated:
    - SOL 6.2: mission/effect/proof transactional truth.
    - FormationOmega: objective-preserving route formation.
    - EvidenceOpsAlgorithmFoundry: deterministic no-effect innovation cycle.
    - AlphaOmegaEngine: implementation build-plan compiler when required.

    This adapter grants no provider/source/effect authority.
    """

    def __init__(
        self,
        *,
        repo_root: str | Path | None = None,
        workspace: str | Path | None = None,
        learning_policy_path: str | Path | None = None,
    ) -> None:
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[2])
        self.workspace = Path(workspace or (self.repo_root / ".sol62-alpha-omega"))
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.learning_policy_path = Path(
            learning_policy_path
            or (self.repo_root / "governance" / "federation_learning_policy.json")
        )

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
        has_route = bool(best_ids)
        hard_gap = reason.upper() in {
            "NO_QUALIFIED_ROUTE",
            "QUALIFIED_ROUTES_EXHAUSTED",
            "TRANSITION_EXECUTION_BINDING_MISSING",
            "NO_READY_TRANSITION",
        }

        return (
            StrategyRoute(
                route_id="FORMATION:REUSE_OR_OPTIMISE",
                family="REUSE_OR_OPTIMISE",
                complete=has_route,
                authorised=has_route,
                reversible=True,
                burden=1.0,
                proof_quality=0.86 if has_route else 0.0,
                capability_hypothesis="Existing qualified SOL route can satisfy the mission with optimisation only.",
                falsifier="No current callable authorised privacy-fit route survives fresh readback.",
                source_route_ids=best_ids[:1],
            ),
            StrategyRoute(
                route_id="FORMATION:COMPOSE_OR_EXTEND",
                family="COMPOSE_OR_EXTEND",
                complete=has_route,
                authorised=has_route,
                reversible=True,
                burden=2.0,
                proof_quality=0.92 if has_route else 0.0,
                capability_hypothesis="Compose current FUSE routes and durable continuation without a new controller.",
                falsifier="A true residual remains after overlap collapse.",
                source_route_ids=best_ids,
            ),
            StrategyRoute(
                route_id="FORMATION:BUILD_MINIMUM_RESIDUAL",
                family="MATERIALLY_NEW_OR_INNOVATIVE",
                complete=bool(selected_upgrade_genes) or not has_route,
                authorised=True,
                reversible=True,
                burden=4.0,
                proof_quality=0.78,
                capability_hypothesis="Build only the smallest true residual through existing governed foundry lanes.",
                falsifier="An equivalent admitted FUSE capability already closes the exact gap.",
            ),
            StrategyRoute(
                route_id="FORMATION:HIGHEST_INFORMATION_REVERSIBLE_EXPERIMENT",
                family="HIGHEST_INFORMATION_REVERSIBLE_EXPERIMENT",
                complete=not hard_gap,
                authorised=True,
                reversible=True,
                burden=1.5,
                proof_quality=0.72,
                capability_hypothesis="Run a reversible experiment only when it can materially change the route decision.",
                falsifier="The experiment cannot change a material route/build decision.",
            ),
        )

    @staticmethod
    def _select(objective: str, candidates: Sequence[StrategyRoute]) -> StrategyRoute:
        selected = FormationOmega.smallest_sufficient_decision(
            objective,
            [asdict(candidate) for candidate in candidates],
        )
        route_id = str(selected["route_id"])
        return next(candidate for candidate in candidates if candidate.route_id == route_id)

    @staticmethod
    def _lesson_signals(
        *,
        reason: str,
        selected_upgrade_genes: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        signals = [
            {
                "signal_id": "SOL62-RUNTIME-GAP",
                "summary": f"runtime failure gap route selection proof missing recovery {reason}",
                "lesson": "Use changed mechanism, proof-before-claim, owner-burden minimisation and reusable recovery.",
                "impact": 0.9,
                "uncertainty": 0.7,
                "reuse_potential": 0.9,
                "implementation_cost": 0.25,
                "repetition": 1,
                "evidence_refs": [f"SOL62:GAP:{reason}"],
            }
        ]
        for gene in selected_upgrade_genes:
            signals.append(
                {
                    "signal_id": str(gene.get("gene_id") or "SOL62-UPGRADE"),
                    "summary": " ".join(
                        [
                            str(gene.get("mechanism") or ""),
                            " ".join(str(x) for x in gene.get("tags", []) or []),
                            "failure recovery regression test engineering gene information gain experiment",
                        ]
                    ),
                    "lesson": str(gene.get("provenance") or "SOL62 runtime upgrade candidate"),
                    "impact": 0.8,
                    "uncertainty": 0.6,
                    "reuse_potential": 0.85,
                    "implementation_cost": 0.3,
                    "repetition": 1,
                    "evidence_refs": [str(gene.get("gene_id") or "SOL62-UPGRADE")],
                }
            )
        return signals

    def _execute_foundry(
        self,
        *,
        mission_id: str,
        objective: str,
        reason: str,
        candidates: Sequence[StrategyRoute],
        selected_upgrade_genes: Sequence[Mapping[str, Any]],
    ):
        foundry = EvidenceOpsAlgorithmFoundry(
            self.workspace / "formation" / mission_id,
            learning_policy_path=self.learning_policy_path,
        )
        available_routes = [
            {
                "route_id": item.route_id,
                "action": item.family.lower().replace("_", " "),
                "available": bool(item.complete and item.authorised),
            }
            for item in candidates
        ]
        payload = {
            "cycle_id": "SOL62-FORMATION-" + digest(
                {"mission_id": mission_id, "objective": objective, "reason": reason}
            )[:20].upper(),
            "lesson_signals": self._lesson_signals(
                reason=reason,
                selected_upgrade_genes=selected_upgrade_genes,
            ),
            "directive": f"Create an internal source-independent implementation plan for: {objective}",
            "owner_objective": objective,
            "available_routes": available_routes,
            "evidence_refs": [f"SOL62:{mission_id}:{reason}"],
            "current_authority": AUTHORITY_CEILING,
        }
        return foundry.execute_cycle(payload)

    @staticmethod
    def _reuse_build(selected: StrategyRoute, *, upgrade_genes: Sequence[Mapping[str, Any]]) -> str:
        if selected.family == "REUSE_OR_OPTIMISE":
            return "REUSE"
        if selected.family == "COMPOSE_OR_EXTEND":
            return "COMPOSE"
        if selected.family == "HIGHEST_INFORMATION_REVERSIBLE_EXPERIMENT":
            return "EXPERIMENT"
        return "HARVEST" if upgrade_genes else "TEMPORARY_BUILD"

    def _alpha_omega(
        self,
        *,
        mission_id: str,
        objective: str,
        constraints: Sequence[str],
        preferred_surfaces: Sequence[str],
        formation_decision: Any,
    ) -> dict[str, Any] | None:
        if not bool(formation_decision.implementation_required):
            return None

        source_root = self.repo_root / "systems" / "alpha-omega-turnkey" / "src"
        if not source_root.exists():
            raise RuntimeError("ALPHA_OMEGA_CANONICAL_SOURCE_MISSING")
        source_text = str(source_root)
        inserted = False
        if source_text not in sys.path:
            sys.path.insert(0, source_text)
            inserted = True
        try:
            alpha_module = importlib.import_module("alpha_omega")
            adapter_module = importlib.import_module("alpha_omega.of50_adapter")
            engine_cls = getattr(alpha_module, "AlphaOmegaEngine")
            compile_packet = getattr(adapter_module, "compile_of50_alpha_omega_packet")
            engine = engine_cls(self.workspace / "alpha-omega" / mission_id)
            result = compile_packet(
                engine,
                mission_id=mission_id,
                objective=objective,
                formation_decision=formation_decision,
                constraints=list(constraints),
                preferred_surfaces=list(preferred_surfaces),
                rollback_ref=f"SOL62-ROLLBACK:{mission_id}",
                runtime_target="FUSE_SOL_6_2",
                terminal_criteria=("SOL62_VERIFIED_REALITY",),
            )
            if result is None:
                return None
            plan = result.plan.to_dict()
            packet = asdict(result.packet)
            body = {
                "producer": ALPHA_OMEGA_PRODUCER,
                "plan": plan,
                "packet": packet,
                "authority_ceiling": AUTHORITY_CEILING,
                "external_effect": False,
                "local_build_executed": False,
                "provider_runtime_verified": False,
            }
            body["result_sha256"] = digest(body)
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
        foundry_result = self._execute_foundry(
            mission_id=mission_id,
            objective=objective,
            reason=reason,
            candidates=candidates,
            selected_upgrade_genes=selected_upgrade_genes,
        )
        foundry_dict = foundry_result.as_dict()
        if foundry_result.status != "PASSED":
            raise RuntimeError("FORMATION_INNOVATION_CYCLE_NOT_PASSED")

        reuse_vs_build = self._reuse_build(
            selected,
            upgrade_genes=selected_upgrade_genes,
        )
        formation_decision = compile_of50_formation_decision(
            mission_id=mission_id,
            foundry_result=foundry_result,
            route_candidates=[
                {
                    "route_id": item.route_id,
                    "route_family": item.family,
                    "score": item.score,
                    "falsifier": item.falsifier,
                    "capability_hypothesis": item.capability_hypothesis,
                }
                for item in candidates
            ],
            selected_route_id=selected.route_id,
            reuse_vs_build=reuse_vs_build,
            selected_capability_hypothesis=selected.capability_hypothesis,
            implementation_required=selected.family == "MATERIALLY_NEW_OR_INNOVATIVE",
        )
        alpha_omega = self._alpha_omega(
            mission_id=mission_id,
            objective=objective,
            constraints=constraints,
            preferred_surfaces=preferred_surfaces,
            formation_decision=formation_decision,
        )
        formation_body = asdict(formation_decision)
        truth_boundary = {
            "formation_route_compiled": True,
            "formation_foundry_executed": True,
            "formation_foundry_passed": True,
            "formation_receipt_bound_to_decision": (
                formation_decision.foundry_cycle_ref == foundry_dict["receipt_sha256"]
            ),
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
            "implementation_required": formation_decision.implementation_required,
            "formation_foundry_result": foundry_dict,
            "formation_decision": formation_body,
            "alpha_omega_result": alpha_omega,
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
            implementation_required=bool(formation_decision.implementation_required),
            formation_foundry_result=foundry_dict,
            formation_decision=formation_body,
            alpha_omega_result=alpha_omega,
            alternatives=tuple(asdict(item) for item in candidates),
            authority_ceiling=AUTHORITY_CEILING,
            external_effect=False,
            receipt_sha256=digest(material),
            truth_boundary=truth_boundary,
        )


def receipt_to_dict(receipt: StrategyReceipt) -> dict[str, Any]:
    return {
        **asdict(receipt),
        "formation_foundry_result": dict(receipt.formation_foundry_result),
        "formation_decision": dict(receipt.formation_decision),
        "alpha_omega_result": (
            dict(receipt.alpha_omega_result) if receipt.alpha_omega_result is not None else None
        ),
        "alternatives": [dict(item) for item in receipt.alternatives],
        "truth_boundary": dict(receipt.truth_boundary),
    }
