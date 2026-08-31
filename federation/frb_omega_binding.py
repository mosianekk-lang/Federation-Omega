from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.resource_gate import (
    CapabilityCandidate,
    CapabilityRequirement,
    SufficiencyState,
    evaluate_requirement,
)
from evidenceops.caseforge.federation_validation import CapabilityForge, CapabilityProbe
from frontier_convergence.core import FinOpsParetoRouter, ValueReceipt
from federation.idea_system_build_runtime import BuildGenerator, BuildRuntimeReceipt, IdeaSystemBuildRuntime
from federation.idea_to_system_compiler import CapabilityRecord, IdeaSystemPlan, compile_idea_to_system, infer_intent

_SCHEMA = "FEDERATION-FRB-OMEGA-IDEA-BINDING-V1"
_READY_STATES = frozenset(
    {
        SufficiencyState.SATISFIED,
        SufficiencyState.REUSE_EXISTING,
        SufficiencyState.REPURPOSE_EXISTING,
        SufficiencyState.COMPOSE_EXISTING,
    }
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _tag(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(value).upper()).strip("_")


def _bounded(value: float, *, field: str) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field} must be in [0,1]")
    return value


@dataclass(frozen=True, slots=True)
class FRBResourceObservation:
    resource_id: str
    capabilities: tuple[str, ...]
    heartbeat_state: str
    ttl_seconds: int
    age_seconds: int
    semantic_ok: bool
    readback_ok: bool
    authority_verified: bool
    reliability: float
    fit: float = 1.0
    evidence_factor: float = 1.0
    provider_live: bool = False
    mutation_authority: bool = False
    independent_verifier_available: bool = False
    reversible: bool = True
    incremental_cost: float | None = None
    latency_ms: float | None = None
    owner_burden: float | None = None
    outcome_value: float | None = None
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> "FRBResourceObservation":
        if not self.resource_id.strip():
            raise ValueError("resource_id is required")
        if not self.normalized_capabilities:
            raise ValueError("at least one capability is required")
        if int(self.ttl_seconds) <= 0 or int(self.age_seconds) < 0:
            raise ValueError("ttl_seconds must be positive and age_seconds non-negative")
        _bounded(self.reliability, field="reliability")
        _bounded(self.fit, field="fit")
        _bounded(self.evidence_factor, field="evidence_factor")
        if self.incremental_cost is not None and float(self.incremental_cost) < 0:
            raise ValueError("incremental_cost must be non-negative when known")
        if self.latency_ms is not None and float(self.latency_ms) < 0:
            raise ValueError("latency_ms must be non-negative when known")
        if self.owner_burden is not None:
            _bounded(self.owner_burden, field="owner_burden")
        if self.outcome_value is not None:
            _bounded(self.outcome_value, field="outcome_value")
        return self

    @property
    def normalized_capabilities(self) -> tuple[str, ...]:
        return tuple(sorted({_tag(item) for item in self.capabilities if _tag(item)}))

    @property
    def freshness_factor(self) -> float:
        ttl = max(1, int(self.ttl_seconds))
        age = max(0, int(self.age_seconds))
        return 1.0 if age <= ttl else max(0.0, min(1.0, ttl / age))

    @property
    def value_metrics_complete(self) -> bool:
        return (
            self.incremental_cost is not None
            and self.latency_ms is not None
            and self.owner_burden is not None
            and self.outcome_value is not None
            and bool(self.proof_refs)
        )

    @property
    def confidence(self) -> float:
        return round(
            _bounded(self.fit, field="fit")
            * _bounded(self.evidence_factor, field="evidence_factor")
            * self.freshness_factor
            * _bounded(self.reliability, field="reliability"),
            12,
        )

    def as_probe(self) -> CapabilityProbe:
        return CapabilityProbe(
            capability_id=self.resource_id,
            heartbeat_state=self.heartbeat_state,
            ttl_seconds=int(self.ttl_seconds),
            age_seconds=int(self.age_seconds),
            semantic_ok=bool(self.semantic_ok),
            readback_ok=bool(self.readback_ok),
            authority_verified=bool(self.authority_verified),
            reliability=float(self.reliability),
            effectful=False,
        )

    def as_candidate(self, capability: str) -> CapabilityCandidate:
        return CapabilityCandidate(
            candidate_id=self.resource_id,
            capability=_tag(capability),
            fit=float(self.fit),
            evidence_factor=float(self.evidence_factor),
            freshness_factor=self.freshness_factor,
            provider_live=bool(self.provider_live),
            mutation_authority=bool(self.mutation_authority),
            independent_verifier_available=bool(self.independent_verifier_available),
            reversible=bool(self.reversible),
            incremental_cost=(None if self.incremental_cost is None else float(self.incremental_cost)),
            source_kind="FRB_OBSERVATION",
        )

    def as_value_receipt(self) -> ValueReceipt:
        if not self.value_metrics_complete:
            raise ValueError("complete value metrics and proof_refs are required for Pareto ranking")
        return ValueReceipt.create(
            candidate_id=self.resource_id,
            quality=float(self.fit),
            reliability=float(self.reliability),
            latency_ms=float(self.latency_ms),
            cost=float(self.incremental_cost),
            owner_burden=float(self.owner_burden),
            outcome_value=float(self.outcome_value),
            evidence_refs=self.proof_refs,
        )


@dataclass(frozen=True, slots=True)
class FRBRequirementRoute:
    requirement: str
    state: str
    candidate_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class FRBSelectionReceipt:
    required_capabilities: tuple[str, ...]
    selected_resource_ids: tuple[str, ...]
    unresolved_capabilities: tuple[str, ...]
    requirement_routes: tuple[FRBRequirementRoute, ...]
    admitted_capabilities_by_resource: tuple[tuple[str, tuple[str, ...]], ...]
    pareto_fronts: tuple[tuple[str, tuple[str, ...]], ...]
    unranked_resource_ids: tuple[str, ...]
    source_observation_count: int

    def canonical_mapping(self) -> dict[str, Any]:
        return {
            "schema": _SCHEMA,
            "required_capabilities": list(self.required_capabilities),
            "selected_resource_ids": list(self.selected_resource_ids),
            "unresolved_capabilities": list(self.unresolved_capabilities),
            "requirement_routes": [asdict(item) for item in self.requirement_routes],
            "admitted_capabilities_by_resource": [
                {"resource_id": resource_id, "capabilities": list(capabilities)}
                for resource_id, capabilities in self.admitted_capabilities_by_resource
            ],
            "pareto_fronts": [
                {"requirement": requirement, "resource_ids": list(resource_ids)}
                for requirement, resource_ids in self.pareto_fronts
            ],
            "unranked_resource_ids": list(self.unranked_resource_ids),
            "source_observation_count": self.source_observation_count,
            "truth_boundary": {
                "broker_selection_grants_authority": False,
                "discovery_is_provider_execution": False,
                "unknown_value_metrics_are_inferred": False,
                "unregistered_resource_is_reused": False,
                "unregistered_capability_is_inherited": False,
                "pareto_dominance_overrides_capability_coverage": False,
            },
        }

    @property
    def digest(self) -> str:
        return _digest(self.canonical_mapping())

    def compiler_records(self, records: Sequence[CapabilityRecord]) -> tuple[CapabilityRecord, ...]:
        by_id = {item.capability_id: item for item in records}
        selected = set(self.selected_resource_ids)
        result: list[CapabilityRecord] = []
        for resource_id, capabilities in self.admitted_capabilities_by_resource:
            if resource_id not in selected:
                continue
            source = by_id.get(resource_id)
            if source is None:
                continue
            registered_tags = source.normalized_tags()
            requested_tags = frozenset(_tag(item) for item in capabilities if _tag(item))
            unregistered = tuple(sorted(requested_tags - registered_tags))
            if unregistered:
                raise ValueError(
                    "FRB observation cannot extend registered capability surface for "
                    f"{resource_id}: " + ",".join(unregistered)
                )
            result.append(
                CapabilityRecord(
                    capability_id=source.capability_id,
                    name=source.name,
                    tags=tuple(sorted(requested_tags)),
                    evidence_state=source.evidence_state,
                    reusable=source.reusable,
                    provider_live=source.provider_live,
                    cost_class=source.cost_class,
                )
            )
        return tuple(sorted(result, key=lambda item: item.capability_id))


class FRBOmegaBinding:
    """Thin executable binding over existing Federation resource-selection primitives.

    CapabilityForge owns freshness/semantic/readback/authority eligibility.
    CFBE ResourceGate owns reuse/provider/cost/owner sufficiency gates.
    Frontier FinOpsParetoRouter supplies value-front evidence. This binding only
    composes their outputs into a minimum-sufficient Idea->System registry slice.
    """

    def __init__(self, observations: Sequence[FRBResourceObservation]) -> None:
        checked = [item.validate() for item in observations]
        ids = [item.resource_id for item in checked]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate resource_id is not allowed")
        self.observations = tuple(sorted(checked, key=lambda item: item.resource_id))

    def select(
        self,
        requirements: Iterable[str],
        *,
        provider_live_required: Iterable[str] = (),
        mutation_authority_required: Iterable[str] = (),
        min_fit: float = 0.80,
        minimum_reliability: float = 0.80,
        max_incremental_cost: float = 0.0,
    ) -> FRBSelectionReceipt:
        required = tuple(sorted({_tag(item) for item in requirements if _tag(item)}))
        if not required:
            raise ValueError("at least one requirement is required")
        _bounded(min_fit, field="min_fit")
        _bounded(minimum_reliability, field="minimum_reliability")
        if max_incremental_cost < 0:
            raise ValueError("max_incremental_cost must be non-negative")

        provider_live = {_tag(item) for item in provider_live_required}
        mutation = {_tag(item) for item in mutation_authority_required}
        route_by_requirement: dict[str, FRBRequirementRoute] = {}
        roles: dict[str, set[str]] = {item.resource_id: set() for item in self.observations}
        pareto_fronts: dict[str, tuple[str, ...]] = {}
        unranked: set[str] = set()

        if self.observations:
            forge = CapabilityForge()
            forge_result = forge.evaluate(tuple(item.as_probe() for item in self.observations))
            eligible = set(forge_result.eligible)
        else:
            forge = CapabilityForge()
            forge_result = None
            eligible = set()

        for requirement in required:
            matching = [item for item in self.observations if requirement in item.normalized_capabilities]
            if not matching:
                route_by_requirement[requirement] = FRBRequirementRoute(
                    requirement,
                    SufficiencyState.BUILD_REQUIRED.value,
                    (),
                    "No observed Federation resource currently exposes this capability.",
                )
                continue

            eligible_matching = [item for item in matching if item.resource_id in eligible]
            if not eligible_matching:
                route_by_requirement[requirement] = FRBRequirementRoute(
                    requirement,
                    "QUALIFICATION_GATE",
                    tuple(sorted(item.resource_id for item in matching)),
                    "Matching resources exist but current freshness/semantic/readback/authority proof is incomplete.",
                )
                continue

            requirement_contract = CapabilityRequirement(
                requirement_id=f"FRB:{requirement}",
                capability=requirement,
                min_fit=float(min_fit),
                provider_live_required=requirement in provider_live,
                mutation_authority_required=requirement in mutation,
                independent_verifier_required=True,
                max_incremental_cost=float(max_incremental_cost),
            )

            admissible: list[FRBResourceObservation] = []
            for item in eligible_matching:
                decision = evaluate_requirement(requirement_contract, (item.as_candidate(requirement),))
                if decision.state in _READY_STATES:
                    admissible.append(item)

            if not admissible:
                combined = evaluate_requirement(
                    requirement_contract,
                    tuple(item.as_candidate(requirement) for item in eligible_matching),
                )
                route_by_requirement[requirement] = FRBRequirementRoute(
                    requirement,
                    combined.state.value,
                    combined.selected_candidate_ids,
                    combined.rationale,
                )
                continue

            ranked_ready = [item for item in admissible if item.value_metrics_complete]
            for item in admissible:
                if not item.value_metrics_complete:
                    unranked.add(item.resource_id)
            if not ranked_ready:
                route_by_requirement[requirement] = FRBRequirementRoute(
                    requirement,
                    "VALUE_METRICS_GATE",
                    tuple(sorted(item.resource_id for item in admissible)),
                    "Functionally admissible resources exist, but FRB latency/cost/owner-burden/outcome-value proof is incomplete.",
                )
                continue

            front = FinOpsParetoRouter.pareto_front(
                tuple(item.as_value_receipt() for item in ranked_ready),
                minimum_quality=float(min_fit),
                minimum_reliability=float(minimum_reliability),
            )
            front_ids = tuple(sorted(item.candidate_id for item in front))
            pareto_fronts[requirement] = front_ids
            if not front_ids:
                route_by_requirement[requirement] = FRBRequirementRoute(
                    requirement,
                    "VALUE_GATE",
                    tuple(sorted(item.resource_id for item in ranked_ready)),
                    "Observed resources failed the protected quality/reliability value floor.",
                )
                continue

            # Do not delete a dominated resource here: it may cover other required
            # capabilities and reduce the globally minimum sufficient resource set.
            for item in ranked_ready:
                roles[item.resource_id].add(requirement)
            route_by_requirement[requirement] = FRBRequirementRoute(
                requirement,
                "ROUTABLE",
                tuple(sorted(item.resource_id for item in ranked_ready)),
                "Current proof, hard gates and value metrics admit bounded reuse; global minimum-set selection follows.",
            )

        pareto_hits: dict[str, int] = {item.resource_id: 0 for item in self.observations}
        for ids in pareto_fronts.values():
            for resource_id in ids:
                pareto_hits[resource_id] = pareto_hits.get(resource_id, 0) + 1
        observation_by_id = {item.resource_id: item for item in self.observations}
        ordered_ids = sorted(
            roles,
            key=lambda resource_id: (
                -len(roles[resource_id]),
                -pareto_hits.get(resource_id, 0),
                -observation_by_id[resource_id].confidence,
                resource_id,
            ),
        )
        ordered_roles = {
            resource_id: tuple(sorted(roles[resource_id]))
            for resource_id in ordered_ids
            if roles[resource_id]
        }

        if forge_result is not None and ordered_roles:
            selected, uncovered = forge.select_minimum_sufficient(required, ordered_roles, forge_result)
        else:
            selected, uncovered = (), required

        selected_set = set(selected)
        admitted = tuple(
            (resource_id, tuple(sorted(capabilities & set(required))))
            for resource_id, capabilities in roles.items()
            if resource_id in selected_set
        )

        final_routes: list[FRBRequirementRoute] = []
        for requirement in required:
            route = route_by_requirement[requirement]
            covering = tuple(
                resource_id
                for resource_id in selected
                if requirement in roles.get(resource_id, set())
            )
            if covering:
                route = FRBRequirementRoute(
                    requirement,
                    "ROUTABLE",
                    covering,
                    "Selected by the minimum-sufficient global resource set after proof and value gates.",
                )
            final_routes.append(route)

        unresolved = tuple(
            sorted(
                requirement
                for requirement in required
                if not any(requirement in roles.get(resource_id, set()) for resource_id in selected)
            )
        )
        if tuple(sorted(uncovered)) != unresolved:
            raise RuntimeError("FRB minimum-sufficient selection readback mismatch")

        return FRBSelectionReceipt(
            required_capabilities=required,
            selected_resource_ids=tuple(selected),
            unresolved_capabilities=unresolved,
            requirement_routes=tuple(final_routes),
            admitted_capabilities_by_resource=tuple(sorted(admitted)),
            pareto_fronts=tuple(sorted((key, value) for key, value in pareto_fronts.items())),
            unranked_resource_ids=tuple(sorted(unranked)),
            source_observation_count=len(self.observations),
        )


@dataclass(frozen=True, slots=True)
class FRBBoundBuildReceipt:
    build_receipt: BuildRuntimeReceipt
    resource_broker_receipt: FRBSelectionReceipt
    generator_provider_receipt: Mapping[str, Any] | None = None

    def canonical_mapping(self) -> dict[str, Any]:
        return {
            "schema": "FEDERATION-FRB-BOUND-BUILD-RECEIPT-V1",
            "build_receipt": self.build_receipt.canonical_mapping(),
            "resource_broker_receipt": self.resource_broker_receipt.canonical_mapping(),
            "generator_provider_receipt": (
                None if self.generator_provider_receipt is None else dict(self.generator_provider_receipt)
            ),
            "truth_boundary": {
                "broker_receipt_is_provider_execution": False,
                "base_runtime_provider_flag_covers_generator_provider_calls": False,
                "provider_generator_receipt_grants_deployment_authority": False,
            },
        }

    @property
    def digest(self) -> str:
        return _digest(self.canonical_mapping())


class FRBBoundIdeaSystemRuntime:
    """Idea->System wrapper that makes FRB selection observable and effective."""

    def __init__(self, runtime: IdeaSystemBuildRuntime, broker: FRBOmegaBinding) -> None:
        self.runtime = runtime
        self.broker = broker
        self._selection_by_plan: dict[str, FRBSelectionReceipt] = {}

    def plan(self, idea: str, *, source_frontier: str, domain_hint: str | None = None) -> IdeaSystemPlan:
        intent = infer_intent(idea)
        selection = self.broker.select(intent.required_capabilities)
        records = self.runtime.discovery.records()
        projected = selection.compiler_records(records)
        projected_ids = {item.capability_id for item in projected}
        missing_registration = set(selection.selected_resource_ids) - projected_ids
        if missing_registration:
            raise ValueError(
                "FRB selected resource is not registered in current capability discovery: "
                + ",".join(sorted(missing_registration))
            )
        plan = compile_idea_to_system(
            idea,
            projected,
            source_frontier=source_frontier,
            domain_hint=domain_hint,
        )
        self._selection_by_plan[plan.digest()] = selection
        return plan

    def selection_for(self, plan: IdeaSystemPlan) -> FRBSelectionReceipt:
        try:
            return self._selection_by_plan[plan.digest()]
        except KeyError as exc:
            raise ValueError("plan was not compiled through this FRB-bound runtime") from exc

    def build(
        self,
        plan: IdeaSystemPlan,
        generator: BuildGenerator,
        *,
        max_attempts: int = 2,
    ) -> FRBBoundBuildReceipt:
        selection = self.selection_for(plan)
        build_receipt = self.runtime.build(plan, generator, max_attempts=max_attempts)
        provider_receipt = None
        receipt_method = getattr(generator, "provider_receipt", None)
        if callable(receipt_method):
            provider_receipt = receipt_method()
        return FRBBoundBuildReceipt(
            build_receipt=build_receipt,
            resource_broker_receipt=selection,
            generator_provider_receipt=provider_receipt,
        )


__all__ = [
    "FRBBoundBuildReceipt",
    "FRBBoundIdeaSystemRuntime",
    "FRBOmegaBinding",
    "FRBRequirementRoute",
    "FRBResourceObservation",
    "FRBSelectionReceipt",
]
