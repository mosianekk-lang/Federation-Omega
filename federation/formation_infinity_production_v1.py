from __future__ import annotations

"""Formation Infinity Production Binding v1.

A thin production/end-state compiler over existing FUSE Ecosystem, Formation,
FCOA, HIPB, Hypercube/CFBE, SOL62/Genesis, FDOF/SICF and ProofOS.

It creates no sovereign controller, scheduler, authority root, truth root,
memory root, provider authority or external effect.  It binds current/future
system families, a bounded logical AI workforce and the existing OmniSurface
resource registry into a proof-gated production-closure plan.
"""

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

from federation.omnisurface_fabric_v2 import OmniSurfaceRegistry, build_default_registry


SCHEMA = "FUSE_FORMATION_INFINITY_PRODUCTION_BINDING_V1"
VERSION = "1.0.0"
CONTRACT_ID = "FUSE-FORMATION-INFINITY-PRODUCTION-001"
LOGICAL_AGENT_BUDGET = 99


class PredicateState(StrEnum):
    CLOSED = "CLOSED"
    ACTIVE = "ACTIVE"
    HELD = "HELD"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ResourceClass(StrEnum):
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"


@dataclass(frozen=True, slots=True)
class ProductionPredicate:
    predicate_id: str
    state: PredicateState
    proof_refs: tuple[str, ...] = ()
    blocker: str = ""
    priority: int = 50

    def validate(self) -> "ProductionPredicate":
        if not self.predicate_id.strip():
            raise ValueError("FORMATION_INFINITY_PREDICATE_ID_REQUIRED")
        if self.state is PredicateState.CLOSED and not self.proof_refs:
            raise ValueError("FORMATION_INFINITY_CLOSED_PREDICATE_REQUIRES_PROOF")
        if self.state is PredicateState.HELD and not self.blocker.strip():
            raise ValueError("FORMATION_INFINITY_HELD_PREDICATE_REQUIRES_BLOCKER")
        return self


@dataclass(frozen=True, slots=True)
class AgentRoleSpec:
    role_id: str
    family: str
    scope: tuple[str, ...]
    effect_ceiling: str
    data_labels: tuple[str, ...]
    budget_units: int
    checkpoint_required: bool = True
    audit_required: bool = True
    pause_kill_revoke: bool = True
    ephemeral: bool = True


@dataclass(frozen=True, slots=True)
class FamilyBinding:
    family_id: str
    service_ids: tuple[str, ...]
    formation_propagated: bool
    intelligence_contracts: tuple[str, ...]
    execution_contracts: tuple[str, ...]
    proof_contracts: tuple[str, ...]
    learning_contracts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResourceBinding:
    resource_id: str
    resource_class: str
    provider: str
    product: str
    capabilities: tuple[str, ...]
    protocols: tuple[str, ...]
    provider_readback_required: bool
    authority_minted: bool = False
    provider_execution_proven: bool = False


@dataclass(frozen=True, slots=True)
class FormationInfinityPlan:
    schema: str
    version: str
    contract_id: str
    mission_id: str
    family_bindings: tuple[FamilyBinding, ...]
    resource_bindings: tuple[ResourceBinding, ...]
    agent_roles: tuple[AgentRoleSpec, ...]
    predicates: tuple[ProductionPredicate, ...]
    next_predicate_ids: tuple[str, ...]
    logical_agent_budget: int
    active_logical_agent_slots: int
    all_applicable_predicates_closed: bool
    production_ready: bool
    commercial_ready: bool
    external_effect_authorized: bool
    provider_execution_proven: bool
    creates_new_controller: bool
    creates_new_scheduler: bool
    creates_new_authority_root: bool
    truth_boundary: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


PRODUCT_PREDICATE_IDS = (
    "SOURCE_ADMITTED",
    "PROOF_EXECUTION_SCALABLE",
    "RUNTIME_ENFORCED",
    "NATURAL_PREVENTION_PROVEN",
    "PRODUCT_SHELL_COMPLETE",
    "IDENTITY_AUTH_SECRETS",
    "DEPLOYMENT_MODEL_PROVEN",
    "CONNECTOR_FABRIC",
    "EVIDENCE_GRAPH_CASE_MODEL",
    "SECURE_ACTION_EXECUTOR",
    "AGENT_GOVERNANCE",
    "OBSERVABILITY_SRE",
    "PROVIDER_LOSS_RECOVERY",
    "SECURITY_HARDENING",
    "PRIVACY_RIGHTS_COMPLIANCE",
    "BILLING_ENTITLEMENTS_METERING",
    "FINOPS_UNIT_ECONOMICS",
    "INSTALL_DEPLOY_UPDATE",
    "ONBOARDING_SUPPORT_OPERATIONS",
    "COMMERCIAL_EVIDENCE",
    "GTM_DISTRIBUTION",
    "CUSTOMER_VALUE_PROVEN",
    "REPEATABLE_DELIVERY",
    "OWNER_ROUTINE_BURDEN_BOUNDED",
    "COMMERCIAL_READY_VERIFIED",
)


WORKFORCE_FAMILIES = (
    ("FORMATION_ARCHITECTURE", ("formation","architecture","mission","routing"), 12),
    ("ENGINEERING_CODEFORGE", ("code","build","test","release"), 18),
    ("CYBER_DFIR_DEVICE", ("security","forensics","device","network"), 12),
    ("INTEGRATIONS_DATA", ("connector","data","api","workflow"), 10),
    ("PROOF_REDTEAM_QA", ("proof","judge","test","falsification"), 10),
    ("SRE_DEVOPS_SECURITY", ("runtime","sre","deploy","recovery"), 8),
    ("FCOA_PRODUCT_UX", ("fcoa","product","creative","artifact"), 8),
    ("COMPLIANCE_PRIVACY_IP", ("privacy","rights","compliance","licensing"), 7),
    ("GTM_CUSTOMER_SUCCESS", ("commercial","gtm","customer","support"), 8),
    ("FINOPS_OPERATIONS_KNOWLEDGE", ("cost","finance","operations","knowledge"), 6),
)


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


class FormationInfinityProductionCompiler:
    """Compile end-state production closure from existing family/resource truth."""

    TRUTH_BOUNDARY = (
        "FORMATION_INFINITY_PLAN_COMPILED!=FAMILY_RUNTIME_CONSUMED"
        "!=RESOURCE_CALLABLE!=PROVIDER_EXECUTED!=PREDICATE_PROVEN"
        "!=PRODUCTION_READY!=CUSTOMER_VALUE!=COMMERCIAL_READY"
    )

    INTELLIGENCE_CONTRACTS = (
        "FUSE-FORMATION-POWER-002",
        "FUSE-HIPB-001",
        "FUSE_AUTONOMOUS_IMPROVEMENT_LOOP_V1",
        "HYPERCUBE_CFBE",
    )
    EXECUTION_CONTRACTS = (
        "FCOA-OMEGA",
        "FUSE_UNIFIED_CAPABILITY_FABRIC_V1",
        "SOL62",
        "GENESIS",
        "FDOF",
        "SICF",
    )
    PROOF_CONTRACTS = (
        "PROOFOS",
        "REALITY_JUDGE",
        "OUTPUT_MIRROR_V3",
    )
    LEARNING_CONTRACTS = (
        "FAILURE_MEMORY",
        "ROUTE_MEMORY",
        "FEDERATION_LEARNING",
        "WORK_PLANE",
    )

    def __init__(self, registry: OmniSurfaceRegistry | None = None) -> None:
        self.registry = registry or build_default_registry()

    @staticmethod
    def _family_bindings(services: Mapping[str, object]) -> tuple[FamilyBinding, ...]:
        by_family: dict[str, list[str]] = {}
        for service_id, service in services.items():
            plane = getattr(service, "plane", None)
            family = getattr(plane, "value", str(plane or "UNCLASSIFIED"))
            by_family.setdefault(family, []).append(service_id)
        return tuple(
            FamilyBinding(
                family_id=family,
                service_ids=tuple(sorted(service_ids)),
                formation_propagated=True,
                intelligence_contracts=FormationInfinityProductionCompiler.INTELLIGENCE_CONTRACTS,
                execution_contracts=FormationInfinityProductionCompiler.EXECUTION_CONTRACTS,
                proof_contracts=FormationInfinityProductionCompiler.PROOF_CONTRACTS,
                learning_contracts=FormationInfinityProductionCompiler.LEARNING_CONTRACTS,
            )
            for family, service_ids in sorted(by_family.items())
        )

    def _resource_bindings(self) -> tuple[ResourceBinding, ...]:
        resources: list[ResourceBinding] = []
        for surface in self.registry.surfaces.values():
            provider = str(surface.provider)
            resource_class = (
                ResourceClass.INTERNAL.value
                if provider.upper() in {"FUSE", "FEDERATION", "LOCAL", "OWNER"}
                else ResourceClass.EXTERNAL.value
            )
            resources.append(
                ResourceBinding(
                    resource_id=surface.surface_id,
                    resource_class=resource_class,
                    provider=surface.provider,
                    product=surface.product,
                    capabilities=tuple(surface.capabilities),
                    protocols=tuple(surface.protocols),
                    provider_readback_required=surface.provider_readback_required,
                    authority_minted=False,
                    provider_execution_proven=False,
                )
            )
        return tuple(sorted(resources, key=lambda r: r.resource_id))

    @staticmethod
    def _agent_roles(
        predicates: Sequence[ProductionPredicate],
        families: Sequence[FamilyBinding],
    ) -> tuple[AgentRoleSpec, ...]:
        open_predicates = {
            p.predicate_id
            for p in predicates
            if p.state in {PredicateState.ACTIVE, PredicateState.HELD}
        }
        family_ids = {f.family_id for f in families}
        roles: list[AgentRoleSpec] = []
        for role_id, scope, budget in WORKFORCE_FAMILIES:
            # Logical slots are available estate-wide but only activated when there
            # is nonterminal product debt. This is not a claim of hidden running agents.
            if not open_predicates:
                continue
            roles.append(
                AgentRoleSpec(
                    role_id=role_id,
                    family="FORMATION_INFINITY_99",
                    scope=tuple(scope) + tuple(sorted(family_ids)),
                    effect_ceiling="A1_INTERNAL_UNLESS_SEPARATELY_AUTHORIZED",
                    data_labels=("MISSION_SCOPED","LEAST_PRIVILEGE","NO_RAW_SECRETS_BY_DEFAULT"),
                    budget_units=budget,
                )
            )
        if sum(role.budget_units for role in roles) > LOGICAL_AGENT_BUDGET:
            raise ValueError("FORMATION_INFINITY_AGENT_BUDGET_EXCEEDED")
        return tuple(roles)

    @staticmethod
    def _normalize_predicates(
        predicates: Iterable[ProductionPredicate],
    ) -> tuple[ProductionPredicate, ...]:
        supplied = {p.predicate_id: p.validate() for p in predicates}
        unknown = set(supplied) - set(PRODUCT_PREDICATE_IDS)
        if unknown:
            raise ValueError("FORMATION_INFINITY_UNKNOWN_PREDICATE:" + ",".join(sorted(unknown)))
        rows: list[ProductionPredicate] = []
        for idx, predicate_id in enumerate(PRODUCT_PREDICATE_IDS):
            rows.append(
                supplied.get(
                    predicate_id,
                    ProductionPredicate(
                        predicate_id=predicate_id,
                        state=PredicateState.ACTIVE,
                        priority=100 - idx,
                    ),
                )
            )
        return tuple(rows)

    def compile(
        self,
        *,
        mission_id: str,
        services: Mapping[str, object],
        predicates: Iterable[ProductionPredicate],
        next_work_limit: int = 5,
    ) -> FormationInfinityPlan:
        if not mission_id.strip():
            raise ValueError("FORMATION_INFINITY_MISSION_ID_REQUIRED")
        normalized = self._normalize_predicates(predicates)
        families = self._family_bindings(services)
        resources = self._resource_bindings()
        agents = self._agent_roles(normalized, families)

        open_rows = [
            p for p in normalized
            if p.state in {PredicateState.ACTIVE, PredicateState.HELD}
        ]
        open_rows.sort(key=lambda p: (-p.priority, p.predicate_id))
        next_ids = tuple(p.predicate_id for p in open_rows[:max(1, next_work_limit)])

        applicable = [p for p in normalized if p.state is not PredicateState.NOT_APPLICABLE]
        all_closed = bool(applicable) and all(p.state is PredicateState.CLOSED for p in applicable)
        commercial = all_closed and next(
            p for p in normalized if p.predicate_id == "COMMERCIAL_READY_VERIFIED"
        ).state is PredicateState.CLOSED

        stable = {
            "mission": mission_id,
            "families": [asdict(f) for f in families],
            "resources": [asdict(r) for r in resources],
            "predicates": [asdict(p) for p in normalized],
            "next": next_ids,
        }
        _ = _digest(stable)

        return FormationInfinityPlan(
            schema=SCHEMA,
            version=VERSION,
            contract_id=CONTRACT_ID,
            mission_id=mission_id,
            family_bindings=families,
            resource_bindings=resources,
            agent_roles=agents,
            predicates=normalized,
            next_predicate_ids=next_ids,
            logical_agent_budget=LOGICAL_AGENT_BUDGET,
            active_logical_agent_slots=sum(role.budget_units for role in agents),
            all_applicable_predicates_closed=all_closed,
            production_ready=all_closed,
            commercial_ready=commercial,
            external_effect_authorized=False,
            provider_execution_proven=False,
            creates_new_controller=False,
            creates_new_scheduler=False,
            creates_new_authority_root=False,
            truth_boundary=self.TRUTH_BOUNDARY,
        )


__all__ = [
    "AgentRoleSpec",
    "CONTRACT_ID",
    "FamilyBinding",
    "FormationInfinityPlan",
    "FormationInfinityProductionCompiler",
    "LOGICAL_AGENT_BUDGET",
    "PredicateState",
    "ProductionPredicate",
    "PRODUCT_PREDICATE_IDS",
    "ResourceBinding",
    "ResourceClass",
    "SCHEMA",
    "VERSION",
]
