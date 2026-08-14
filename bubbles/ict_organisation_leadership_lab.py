from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Iterable, Sequence


@dataclass(frozen=True)
class ICTRole:
    role_id: str
    title: str
    capability: str
    fte: float
    criticality: int
    required_skills: tuple[str, ...]
    incumbent_skills: tuple[str, ...] = ()
    successor_ready: bool = False
    source_model: str = "INSOURCE"


@dataclass(frozen=True)
class ServiceDemand:
    service_id: str
    name: str
    annual_hours: float
    criticality: int
    required_capabilities: tuple[str, ...]


@dataclass(frozen=True)
class SourcingOption:
    capability: str
    option: str
    annual_cost: float
    dependency_risk: int
    knowledge_retention: int
    recovery_readiness: int


class ICTOrganisationLeadershipLab:
    """Synthetic proof lab for senior ICT people and organisation leadership.

    The lab models a higher-education ICT organisation using synthetic roles,
    service demand and sourcing options. It tests spans/capacity, capability
    coverage, succession risk, skills gaps and insource/outsource decisions.

    It does not establish that Kim personally led the represented headcount,
    budget, performance-management process or workforce decisions.
    """

    SCHEMA = "BUBBLES-ICT-ORGANISATION-LEADERSHIP-LAB-V1"

    def __init__(self, *, productive_hours_per_fte: float = 1_450.0) -> None:
        if productive_hours_per_fte <= 0:
            raise ValueError("productive_hours_per_fte must be positive")
        self.productive_hours_per_fte = float(productive_hours_per_fte)

    @staticmethod
    def _bounded_score(value: int, name: str) -> None:
        if not 0 <= value <= 100:
            raise ValueError(f"{name} must be between 0 and 100")

    @classmethod
    def _validate_role(cls, role: ICTRole) -> None:
        if not role.role_id.strip() or not role.title.strip() or not role.capability.strip():
            raise ValueError("role identity, title and capability are required")
        if role.fte <= 0:
            raise ValueError("role fte must be positive")
        cls._bounded_score(role.criticality, "role criticality")
        if not role.required_skills:
            raise ValueError("role requires at least one skill")
        if role.source_model not in {"INSOURCE", "OUTSOURCE", "HYBRID"}:
            raise ValueError("unsupported source model")

    @classmethod
    def _validate_demand(cls, demand: ServiceDemand) -> None:
        if not demand.service_id.strip() or not demand.name.strip():
            raise ValueError("service identity and name are required")
        if demand.annual_hours < 0:
            raise ValueError("annual_hours must be non-negative")
        cls._bounded_score(demand.criticality, "service criticality")
        if not demand.required_capabilities:
            raise ValueError("service requires at least one capability")

    @classmethod
    def _validate_sourcing(cls, option: SourcingOption) -> None:
        if option.option not in {"INSOURCE", "OUTSOURCE", "HYBRID"}:
            raise ValueError("unsupported sourcing option")
        if option.annual_cost < 0:
            raise ValueError("annual_cost must be non-negative")
        cls._bounded_score(option.dependency_risk, "dependency risk")
        cls._bounded_score(option.knowledge_retention, "knowledge retention")
        cls._bounded_score(option.recovery_readiness, "recovery readiness")

    def capacity_by_capability(self, roles: Sequence[ICTRole]) -> dict[str, float]:
        capacity: dict[str, float] = {}
        for role in roles:
            self._validate_role(role)
            capacity[role.capability] = capacity.get(role.capability, 0.0) + role.fte * self.productive_hours_per_fte
        return {key: round(value, 2) for key, value in sorted(capacity.items())}

    @staticmethod
    def demand_by_capability(demands: Sequence[ServiceDemand]) -> dict[str, float]:
        demand_map: dict[str, float] = {}
        for demand in demands:
            ICTOrganisationLeadershipLab._validate_demand(demand)
            share = demand.annual_hours / len(demand.required_capabilities)
            for capability in demand.required_capabilities:
                demand_map[capability] = demand_map.get(capability, 0.0) + share
        return {key: round(value, 2) for key, value in sorted(demand_map.items())}

    def capacity_gaps(self, roles: Sequence[ICTRole], demands: Sequence[ServiceDemand]) -> dict[str, dict[str, float | str]]:
        capacity = self.capacity_by_capability(roles)
        demand = self.demand_by_capability(demands)
        capabilities = sorted(set(capacity) | set(demand))
        result: dict[str, dict[str, float | str]] = {}
        for capability in capabilities:
            available = capacity.get(capability, 0.0)
            required = demand.get(capability, 0.0)
            gap = available - required
            result[capability] = {
                "capacity_hours": round(available, 2),
                "demand_hours": round(required, 2),
                "surplus_gap_hours": round(gap, 2),
                "state": "CAPACITY_GAP" if gap < 0 else "COVERED",
            }
        return result

    @staticmethod
    def skill_gaps(roles: Sequence[ICTRole]) -> dict[str, tuple[str, ...]]:
        gaps: dict[str, tuple[str, ...]] = {}
        for role in roles:
            ICTOrganisationLeadershipLab._validate_role(role)
            missing = tuple(sorted(set(role.required_skills) - set(role.incumbent_skills)))
            if missing:
                gaps[role.role_id] = missing
        return gaps

    @staticmethod
    def succession_risks(roles: Sequence[ICTRole], *, threshold: int = 70) -> tuple[str, ...]:
        risks: list[str] = []
        for role in roles:
            ICTOrganisationLeadershipLab._validate_role(role)
            if role.criticality >= threshold and not role.successor_ready:
                risks.append(role.role_id)
        return tuple(sorted(risks))

    @staticmethod
    def sourcing_score(option: SourcingOption) -> float:
        ICTOrganisationLeadershipLab._validate_sourcing(option)
        resilience = 0.35 * option.recovery_readiness + 0.30 * option.knowledge_retention
        risk_penalty = 0.35 * option.dependency_risk
        return round(max(0.0, min(100.0, 50.0 + resilience - risk_penalty)), 2)

    def choose_sourcing(self, options: Sequence[SourcingOption]) -> dict[str, object]:
        if not options:
            raise ValueError("at least one sourcing option is required")
        for option in options:
            self._validate_sourcing(option)
        capabilities = {option.capability for option in options}
        if len(capabilities) != 1:
            raise ValueError("sourcing comparison must cover one capability")
        ranked = sorted(
            options,
            key=lambda item: (-self.sourcing_score(item), item.annual_cost, item.option),
        )
        winner = ranked[0]
        return {
            "capability": winner.capability,
            "recommended_model": winner.option,
            "score": self.sourcing_score(winner),
            "annual_cost": winner.annual_cost,
            "decision_boundary": "Synthetic decision support only; procurement authority and real vendor selection require separate evidence and governance.",
        }

    def assess_organisation(
        self,
        roles: Sequence[ICTRole],
        demands: Sequence[ServiceDemand],
        sourcing_options: Iterable[SourcingOption] = (),
    ) -> dict[str, object]:
        if not roles:
            raise ValueError("at least one ICT role is required")
        if not demands:
            raise ValueError("at least one service demand is required")
        capacity = self.capacity_gaps(roles, demands)
        skills = self.skill_gaps(roles)
        succession = self.succession_risks(roles)
        sourcing = tuple(sourcing_options)
        sourcing_decision = self.choose_sourcing(sourcing) if sourcing else None
        payload: dict[str, object] = {
            "schema": self.SCHEMA,
            "proof_state": "LOCAL_DEMONSTRATION_VERIFIED",
            "roles": [asdict(role) for role in roles],
            "services": [asdict(demand) for demand in demands],
            "capacity": capacity,
            "skill_gaps": {key: list(value) for key, value in skills.items()},
            "succession_risks": list(succession),
            "sourcing_decision": sourcing_decision,
            "truth_boundary": (
                "Synthetic/local organisational-design proof only. It is not evidence that Kim personally led the modelled headcount, "
                "workforce planning, performance management, procurement or succession decisions. CV/interview use requires separate Kim evidence and Ledger approval."
            ),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["receipt_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return payload

    @staticmethod
    def safe_claim() -> str:
        return (
            "Designed and deterministically tested a synthetic higher-education ICT organisation model covering capacity, skills, succession risk and insource/outsource decision support."
        )

    @staticmethod
    def forbidden_claims() -> tuple[str, ...]:
        return (
            "managed the modelled university ICT headcount",
            "personally owned the modelled workforce budget",
            "executed real staff succession decisions",
            "performed real procurement or outsourcing decisions",
            "proved workforce performance improvement",
            "held CIO people authority through this lab",
        )


def synthetic_reference_roles() -> tuple[ICTRole, ...]:
    return (
        ICTRole("R-SVC", "Service Delivery Lead", "service_delivery", 2.0, 85, ("itil", "problem_management", "stakeholder_management"), ("itil", "stakeholder_management"), True),
        ICTRole("R-INF", "Infrastructure & Cloud Lead", "infrastructure", 2.0, 95, ("network", "cloud", "backup", "dr"), ("network", "backup"), False),
        ICTRole("R-APP", "Enterprise Applications Lead", "applications", 2.0, 90, ("erp", "integration", "data"), ("erp", "integration"), False),
        ICTRole("R-CYB", "Cybersecurity Lead", "cybersecurity", 1.5, 100, ("iam", "incident_response", "risk"), ("iam", "risk"), True),
        ICTRole("R-DATA", "Data & BI Lead", "data", 1.5, 75, ("data_governance", "bi", "lineage"), ("bi",), False),
    )


def synthetic_reference_demands() -> tuple[ServiceDemand, ...]:
    return (
        ServiceDemand("S-REG", "Registration and student lifecycle", 3_000, 100, ("applications", "infrastructure", "service_delivery")),
        ServiceDemand("S-LMS", "Digital learning platforms", 2_000, 95, ("applications", "infrastructure", "service_delivery")),
        ServiceDemand("S-CYB", "Cybersecurity operations", 1_600, 100, ("cybersecurity", "infrastructure")),
        ServiceDemand("S-BI", "Institutional reporting", 1_300, 80, ("data", "applications")),
    )


def synthetic_reference_sourcing_options() -> tuple[SourcingOption, ...]:
    return (
        SourcingOption("cloud_operations", "INSOURCE", 1_800_000, 25, 90, 80),
        SourcingOption("cloud_operations", "OUTSOURCE", 1_300_000, 70, 40, 75),
        SourcingOption("cloud_operations", "HYBRID", 1_500_000, 40, 75, 90),
    )
