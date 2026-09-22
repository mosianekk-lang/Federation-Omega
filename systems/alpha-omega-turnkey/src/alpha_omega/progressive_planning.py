from __future__ import annotations

from typing import Any, Iterable, Mapping

from .progressive_models import (
    EffectClass,
    ProgressivePlan,
    StreamUnit,
    UnitState,
    _slug,
    _stable_id,
)


class ProgressivePlanningMixin:
    def compile_plan(
        self,
        raw: Mapping[str, Any],
        *,
        discovered_capabilities: Iterable[str] = (),
    ) -> ProgressivePlan:
        objective = str(raw.get("description") or raw.get("objective") or "").strip()
        if not objective:
            raise ValueError("description or objective is required")
        title = str(raw.get("title") or "Progressive Mission").strip()
        mission_id = _stable_id("MISSION", title, objective)
        cycle_id = _stable_id(
            "CYCLE",
            mission_id,
            str(len(self.learning.events) + 1),
        )
        routes = self.formation.form_routes(raw)
        selected = self.formation.select_route(routes)
        reusable = self.learning.verified_reuse()

        capabilities = tuple(
            sorted(
                {
                    str(item).strip()
                    for item in [
                        *discovered_capabilities,
                        *raw.get("required_capabilities", []),
                    ]
                    if str(item).strip()
                }
            )
        )
        if not capabilities:
            capabilities = (
                "control plane",
                "proof and learning",
                "operator interface",
            )

        units: dict[str, StreamUnit] = {}

        def add(
            stream: str,
            stage: str,
            objective_text: str,
            *,
            dependencies: Iterable[str] = (),
            collisions: Iterable[str] = (),
            effect: EffectClass = EffectClass.INTERNAL,
            priority: int = 50,
            information_gain: float = 0.5,
            reusable_key: str | None = None,
            proof_gate: str = "INTERNAL_READBACK",
            authority_required: str = "A1_INTERNAL",
            path_id: str | None = None,
            metadata: Mapping[str, Any] | None = None,
        ) -> str:
            unit_id = _stable_id(
                "UNIT",
                mission_id,
                stream,
                stage,
                objective_text,
            )
            if unit_id in units:
                raise ValueError(f"duplicate unit id: {unit_id}")
            units[unit_id] = StreamUnit(
                unit_id=unit_id,
                stream_id=stream,
                path_id=path_id or selected.path_id,
                stage=stage,
                objective=objective_text,
                dependencies=tuple(dependencies),
                collision_keys=tuple(sorted(set(collisions))),
                effect_class=effect,
                authority_required=authority_required,
                proof_gate=proof_gate,
                priority=priority,
                information_gain=information_gain,
                reusable_key=reusable_key,
                metadata=dict(metadata or {}),
            )
            return unit_id

        lock = add(
            "mission",
            "INTAKE",
            "Lock exact objective, scope, success state and truth boundary",
            priority=100,
        )
        awareness = add(
            "discovery",
            "DISCOVERY",
            "Read current surface, route, authority and capability state",
            dependencies=(lock,),
            priority=95,
            information_gain=0.9,
        )
        evidence = add(
            "evidence",
            "DISCOVERY",
            "Map evidence, facts, assumptions, unknowns and proof obligations",
            dependencies=(lock,),
            priority=94,
            information_gain=0.95,
        )
        reuse_scan = add(
            "reuse",
            "DISCOVERY",
            "Discover verified reusable capabilities and prior learning",
            dependencies=(lock,),
            priority=93,
            information_gain=0.85,
        )
        constraints = add(
            "constraints",
            "DISCOVERY",
            "Classify dependencies, collisions, authority and failure boundaries",
            dependencies=(lock,),
            priority=92,
            information_gain=0.9,
        )
        route_evaluations: list[str] = []
        for route in routes:
            if not route.eligible:
                continue
            route_evaluations.append(
                add(
                    f"route:{route.kind.value.lower()}",
                    "ROUTE_EVALUATION",
                    f"Evaluate {route.title} against current evidence and constraints",
                    dependencies=(
                        awareness,
                        evidence,
                        reuse_scan,
                        constraints,
                    ),
                    effect=EffectClass.READ_ONLY,
                    priority=91,
                    information_gain=route.information_gain,
                    path_id=route.path_id,
                    metadata={
                        "route_kind": route.kind.value,
                        "formation_score": route.score,
                        "rationale": route.rationale,
                    },
                )
            )
        tournament = add(
            "formation",
            "ROUTE_TOURNAMENT",
            "Compare evidence from all eligible route families and select the strongest complete safe path",
            dependencies=tuple(route_evaluations),
            priority=90,
            information_gain=0.92,
        )
        genome = add(
            "architecture",
            "SOLUTION_GENOME",
            "Compile selected route into requirements, components, interfaces, tests, rollback and metrics",
            dependencies=(tournament,),
            collisions=(f"mission:{mission_id}:genome",),
            priority=88,
        )

        assurance_units: list[str] = []
        planned_reuse_hits = 0
        planned_work_units_avoided = 0
        for capability in capabilities:
            capability_key = f"capability:{_slug(capability)}"
            if capability_key in reusable:
                planned_reuse_hits += 1
                planned_work_units_avoided += 2
                verify = add(
                    f"reuse:{_slug(capability)}",
                    "VERIFY_REUSE",
                    f"Verify proof freshness and compatibility for reusable {capability}",
                    dependencies=(genome,),
                    collisions=(capability_key,),
                    effect=EffectClass.READ_ONLY,
                    priority=86,
                    information_gain=0.75,
                    reusable_key=capability_key,
                    metadata={
                        "reused": True,
                        "source_proof_refs": reusable[capability_key].get(
                            "proof_refs",
                            [],
                        ),
                    },
                )
                regression = add(
                    f"assurance:{_slug(capability)}",
                    "REGRESSION",
                    f"Run regression and incompatibility checks for reused {capability}",
                    dependencies=(verify,),
                    priority=80,
                    information_gain=0.7,
                    reusable_key=capability_key,
                    metadata={
                        "reused": True,
                        "work_units_avoided": 2,
                    },
                )
                assurance_units.append(regression)
                continue

            build = add(
                f"build:{_slug(capability)}",
                "BUILD",
                f"Build minimum complete {capability} component",
                dependencies=(genome,),
                collisions=(capability_key,),
                effect=EffectClass.PRIVATE_REVERSIBLE,
                priority=84,
                reusable_key=capability_key,
            )
            test = add(
                f"test:{_slug(capability)}",
                "TEST",
                f"Run deterministic healthy-path, failure, idempotency and rollback tests for {capability}",
                dependencies=(build,),
                priority=79,
                information_gain=0.8,
                reusable_key=capability_key,
            )
            red_team = add(
                f"redteam:{_slug(capability)}",
                "RED_TEAM",
                f"Challenge security, privacy, proof and false-completion boundaries for {capability}",
                dependencies=(build,),
                priority=78,
                information_gain=0.9,
                reusable_key=capability_key,
            )
            capability_verify = add(
                f"assurance:{_slug(capability)}",
                "CAPABILITY_VERIFY",
                f"Fan in test and red-team proof and qualify {capability} for reusable admission",
                dependencies=(test, red_team),
                effect=EffectClass.READ_ONLY,
                priority=77,
                information_gain=0.82,
                reusable_key=capability_key,
                proof_gate="CAPABILITY_ASSURANCE_FANIN",
            )
            assurance_units.append(capability_verify)

        integrate = add(
            "integration",
            "INTEGRATE",
            "Integrate only components that passed their local assurance gates",
            dependencies=tuple(assurance_units),
            collisions=(f"mission:{mission_id}:integration",),
            effect=EffectClass.PRIVATE_REVERSIBLE,
            priority=76,
        )
        proof = add(
            "proof",
            "VERIFY",
            "Compile independent semantic readback, health, persistence and rollback evidence",
            dependencies=(integrate,),
            effect=EffectClass.READ_ONLY,
            priority=72,
            information_gain=0.85,
            proof_gate="INDEPENDENT_SEMANTIC_READBACK",
        )
        learning = add(
            "learning",
            "LEARN",
            "Extract reusable capability deltas, negative results and regression triggers",
            dependencies=(proof,),
            collisions=(f"mission:{mission_id}:learning",),
            priority=68,
            information_gain=0.8,
        )

        desired_effect = str(raw.get("desired_effect", "INTERNAL")).upper()
        if desired_effect in {
            "PROVIDER",
            "DEPLOY",
            "EXTERNAL",
            "CONSEQUENTIAL",
        }:
            provider_preflight = add(
                "provider",
                "PROVIDER_PREFLIGHT",
                "Revalidate exact provider identity, target, authority, cost and rollback",
                dependencies=(proof,),
                collisions=("provider:effect-lane",),
                effect=EffectClass.PROVIDER_EFFECT,
                authority_required="PROVIDER_SPECIFIC",
                priority=66,
                information_gain=0.95,
                proof_gate="PROVIDER_IDENTITY_READBACK",
            )
            canary = add(
                "provider",
                "PROVIDER_CANARY",
                "Run the smallest reversible action-specific provider canary",
                dependencies=(provider_preflight,),
                collisions=("provider:effect-lane",),
                effect=EffectClass.PROVIDER_EFFECT,
                authority_required="PROVIDER_SPECIFIC",
                priority=64,
                proof_gate="PROVIDER_SEMANTIC_READBACK",
            )
            add(
                "provider",
                "PROMOTE",
                "Promote only the exact proven provider scope after rollback verification",
                dependencies=(canary, learning),
                collisions=(
                    "provider:effect-lane",
                    "canonical:promotion",
                ),
                effect=EffectClass.CONSEQUENTIAL,
                authority_required="OWNER_EFFECT_PERMIT",
                priority=60,
                proof_gate="OWNER_AND_PROVIDER_PROMOTION_GATE",
            )

        truth_boundary = {
            "authority_ceiling": "A1_INTERNAL",
            "external_effect_default": False,
            "multi_stream_safe_parallelism": True,
            "effectful_mutations_serialized": True,
            "source_or_plan_is_not_runtime_proof": True,
            "speed_improvement_requires_matched_capability_cycle_measurement": True,
            "provider_execution_proven": False,
        }
        return ProgressivePlan(
            mission_id=mission_id,
            cycle_id=cycle_id,
            objective=objective,
            selected_path_id=selected.path_id,
            routes=routes,
            units=units,
            truth_boundary=truth_boundary,
            created_from={
                "title": title,
                "capabilities": capabilities,
                "selected_route": selected.kind.value,
                "planned_reuse_hits": planned_reuse_hits,
                "planned_work_units_avoided": planned_work_units_avoided,
            },
        )

    def promote_path(
        self,
        plan: ProgressivePlan,
        path_id: str,
        *,
        proof_refs: Iterable[str],
    ) -> None:
        refs = tuple(
            str(item).strip()
            for item in proof_refs
            if str(item).strip()
        )
        if not refs:
            raise ValueError("route promotion requires proof references")
        route = next(
            (
                candidate
                for candidate in plan.routes
                if candidate.path_id == path_id
            ),
            None,
        )
        if route is None:
            raise ValueError(f"unknown path: {path_id}")
        if not route.eligible:
            raise ValueError("ineligible path cannot be promoted")
        protected_stages = {
            "INTAKE",
            "DISCOVERY",
            "ROUTE_EVALUATION",
            "ROUTE_TOURNAMENT",
        }
        if any(
            unit.stage not in protected_stages
            and unit.state is not UnitState.PENDING
            for unit in plan.units.values()
        ):
            raise ValueError(
                "path cannot change after downstream execution begins"
            )
        previous = plan.selected_path_id
        plan.selected_path_id = path_id
        for unit in plan.units.values():
            if unit.stage not in {"DISCOVERY", "ROUTE_EVALUATION"}:
                unit.path_id = path_id
        self.learning.append(
            "CORRECTION",
            {
                "mission_id": plan.mission_id,
                "cycle_id": plan.cycle_id,
                "change": "ROUTE_PROMOTION",
                "previous_path_id": previous,
                "selected_path_id": path_id,
                "route_kind": route.kind.value,
                "proof_refs": list(refs),
            },
        )
