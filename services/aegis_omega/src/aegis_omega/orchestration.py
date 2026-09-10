from __future__ import annotations

"""AEGIS-Ω mission orchestration profile.

This module binds four already-proven Federation concepts into one bounded AEGIS
control profile without creating a second authority or truth plane:

* SOL 6.2: verified state-transition semantics, idempotency, authority fencing,
  provider readback, proof-before-closure and fail-closed recovery.
* Formation Engine: preserve objective strength and form competing route families.
* Alpha→Omega: compile the selected route into a complete, testable solution path.
* SLOS/AI-bot swarm: conflict-aware bounded parallelism for NO_EFFECT/READ_ONLY
  lanes only. Provider and mutating lanes remain serialized and proof-gated.

The "AI bots" represented here are logical worker roles. This module does not
claim hidden agents, provider authority, paid model calls or background execution.
"""

from dataclasses import asdict, dataclass
from enum import Enum
import asyncio
import hashlib
import json
import math
from typing import Any, Awaitable, Callable, Mapping, Sequence


SCHEMA = "AEGIS_SOL62_ALPHA_OMEGA_ORCHESTRATION_V1"
ALGORITHM = "FORMATION_ROUTE_TOURNAMENT__SOL62_TRANSITIONS__BOUNDED_BOT_SWARM_V1"


class OrchestrationError(RuntimeError):
    pass


class AuthorityBoundaryError(OrchestrationError):
    pass


class EffectClass(str, Enum):
    NO_EFFECT = "NO_EFFECT"
    READ_ONLY = "READ_ONLY"
    PROVIDER_CALL = "PROVIDER_CALL"
    MUTATING = "MUTATING"


class RouteFamily(str, Enum):
    REUSE_OPTIMISE = "REUSE_OPTIMISE"
    COMPOSE_EXTEND = "COMPOSE_EXTEND"
    MATERIAL_NEW = "MATERIAL_NEW"
    REVERSIBLE_EXPERIMENT = "REVERSIBLE_EXPERIMENT"


class BotRole(str, Enum):
    HARVEST = "HARVEST_BOT"
    EVIDENCE = "EVIDENCE_BOT"
    RED_TEAM = "RED_TEAM_BOT"
    TEST = "TEST_BOT"
    PRIVACY = "PRIVACY_BOT"
    PROVIDER = "PROVIDER_BOT"
    BENCHMARK = "BENCHMARK_BOT"
    SYNTHESIS = "SYNTHESIS_BOT"
    FDOF = "FDOF_BOT"


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    route_id: str
    family: RouteFamily
    description: str
    expected_value: float
    information_gain: float
    proof_quality: float
    reversibility: float
    owner_burden: float
    cost: float
    risk: float
    time_to_proof: float
    reuse: float

    def validate(self) -> "RouteCandidate":
        if not self.route_id.strip() or not self.description.strip():
            raise ValueError("AEGIS_ROUTE_IDENTITY_REQUIRED")
        for field_name in (
            "expected_value", "information_gain", "proof_quality", "reversibility",
            "owner_burden", "cost", "risk", "time_to_proof", "reuse",
        ):
            value = float(getattr(self, field_name))
            if not 0.0 <= value <= 1.0 or not math.isfinite(value):
                raise ValueError(f"AEGIS_ROUTE_METRIC_OUT_OF_RANGE:{field_name}")
        return self

    @property
    def score(self) -> float:
        return (
            2.30 * self.expected_value
            + 1.70 * self.information_gain
            + 2.20 * self.proof_quality
            + 1.25 * self.reversibility
            + 1.40 * self.reuse
            - 0.90 * self.owner_burden
            - 0.70 * self.cost
            - 1.70 * self.risk
            - 0.75 * self.time_to_proof
        )


@dataclass(frozen=True, slots=True)
class WorkLane:
    lane_id: str
    transition_id: str
    bot_role: BotRole
    objective: str
    effect_class: EffectClass
    conflict_domains: tuple[str, ...]
    route_ids: tuple[str, ...]
    expected_value: float
    uncertainty_reduction: float
    critical_path: float
    estimated_latency: float
    estimated_cost: float
    risk: float
    idempotency_key: str
    expected_readback: str
    reversible: bool = True

    def validate(self) -> "WorkLane":
        if not self.lane_id.strip() or not self.transition_id.strip():
            raise ValueError("AEGIS_LANE_IDENTITY_REQUIRED")
        if not self.idempotency_key.strip():
            raise ValueError("AEGIS_LANE_IDEMPOTENCY_REQUIRED")
        if not self.expected_readback.strip():
            raise ValueError("AEGIS_LANE_READBACK_REQUIRED")
        if len(set(self.conflict_domains)) != len(self.conflict_domains):
            raise ValueError("AEGIS_DUPLICATE_CONFLICT_DOMAIN")
        if len(set(self.route_ids)) != len(self.route_ids):
            raise ValueError("AEGIS_DUPLICATE_ROUTE_ID")
        for name in ("expected_value", "uncertainty_reduction", "risk"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"AEGIS_LANE_METRIC_OUT_OF_RANGE:{name}")
        for name in ("critical_path", "estimated_latency", "estimated_cost"):
            if float(getattr(self, name)) < 0.0:
                raise ValueError(f"AEGIS_LANE_METRIC_NEGATIVE:{name}")
        return self

    @property
    def value_of_information(self) -> float:
        latency = max(self.estimated_latency, 0.001)
        return self.uncertainty_reduction / latency

    @property
    def priority(self) -> float:
        return (
            2.50 * self.expected_value
            + 1.75 * self.value_of_information
            + math.log1p(self.critical_path)
            - 1.50 * self.risk
            - 0.20 * self.estimated_cost
        )


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    provider_authority_verified: bool = False
    provider_identity_current: bool = False
    cost_authorized: bool = False
    privacy_cleared: bool = True
    mutation_authorized: bool = False
    fdof_lease_owned: bool = False
    stable_promotion_authorized: bool = False


@dataclass(frozen=True, slots=True)
class MissionPlan:
    schema: str
    algorithm: str
    mission_id: str
    selected_route_id: str
    route_ranking: tuple[tuple[str, float], ...]
    parallel_lanes: tuple[WorkLane, ...]
    serial_lanes: tuple[WorkLane, ...]
    held_lanes: tuple[tuple[str, str], ...]
    sol62_invariants: tuple[str, ...]
    provider_effect_authorized: bool
    stable_promotion_authorized: bool
    plan_sha256: str


@dataclass(frozen=True, slots=True)
class BotLaneResult:
    lane_id: str
    transition_id: str
    bot_role: str
    status: str
    semantic_verified: bool
    proof_valid: bool
    evidence_ref: str
    error: str = ""


@dataclass(frozen=True, slots=True)
class BotSwarmReceipt:
    schema: str
    mission_id: str
    plan_sha256: str
    parallel_lane_count: int
    passed_lane_count: int
    failed_lane_count: int
    provider_effect_observed: bool
    stable_promotion_authorized: bool
    results: tuple[BotLaneResult, ...]
    receipt_sha256: str


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _route_payload(route: RouteCandidate) -> dict[str, Any]:
    return {**asdict(route), "family": route.family.value, "score": round(route.score, 12)}


def _lane_payload(lane: WorkLane) -> dict[str, Any]:
    return {**asdict(lane), "bot_role": lane.bot_role.value, "effect_class": lane.effect_class.value, "priority": round(lane.priority, 12)}


class FormationRouteTournament:
    REQUIRED_FAMILIES = frozenset(RouteFamily)

    @classmethod
    def rank(cls, routes: Sequence[RouteCandidate]) -> tuple[RouteCandidate, ...]:
        if len({r.route_id for r in routes}) != len(routes):
            raise ValueError("AEGIS_ROUTE_IDS_MUST_BE_UNIQUE")
        validated = tuple(route.validate() for route in routes)
        observed = {route.family for route in validated}
        if not cls.REQUIRED_FAMILIES.issubset(observed):
            missing = sorted(item.value for item in cls.REQUIRED_FAMILIES - observed)
            raise ValueError("AEGIS_FORMATION_ROUTE_FAMILIES_MISSING:" + ",".join(missing))
        return tuple(sorted(validated, key=lambda item: (-item.score, item.route_id)))


class Sol62AlphaOmegaPlanner:
    SOL62_INVARIANTS = (
        "TARGET_STATE_PLUS_PROOF_COMPLETION", "REQUEST_HASH_IDEMPOTENCY", "FENCED_EXECUTION",
        "ACTION_BOUND_ONE_USE_AUTHORITY", "SEMANTIC_AND_ATTESTATION_PROOF", "RISK_PROPORTIONAL_SIMULATION",
        "FAIL_CLOSED_RECOVERY", "PROVIDER_READBACK_BEFORE_CLOSURE", "NO_MATURITY_INHERITANCE",
    )

    @classmethod
    def _provider_lane_reason(cls, lane: WorkLane, auth: AuthorizationContext) -> str | None:
        if not auth.provider_authority_verified or not auth.provider_identity_current:
            return "PROVIDER_AUTHORITY_OR_IDENTITY_UNVERIFIED"
        if not auth.privacy_cleared:
            return "PRIVACY_GATE_HELD"
        if not auth.cost_authorized:
            return "COST_GATE_HELD"
        if lane.effect_class is EffectClass.MUTATING:
            if not auth.mutation_authorized:
                return "MUTATION_AUTHORITY_HELD"
            if not auth.fdof_lease_owned:
                return "FDOF_FENCE_NOT_OWNED"
        return None

    @classmethod
    def plan(cls, *, mission_id: str, routes: Sequence[RouteCandidate], lanes: Sequence[WorkLane], auth: AuthorizationContext | None = None, max_parallel_lanes: int = 8) -> MissionPlan:
        auth = auth or AuthorizationContext()
        ranking = FormationRouteTournament.rank(routes)
        selected = ranking[0]
        valid_lanes = tuple(lane.validate() for lane in lanes if selected.route_id in lane.route_ids)
        safe = []
        serial = []
        held = []
        used_domains: set[str] = set()
        for lane in sorted(valid_lanes, key=lambda item: (-item.priority, item.lane_id)):
            if lane.effect_class in {EffectClass.PROVIDER_CALL, EffectClass.MUTATING}:
                reason = cls._provider_lane_reason(lane, auth)
                if reason:
                    held.append((lane.lane_id, reason))
                else:
                    serial.append(lane)
                continue
            domains = set(lane.conflict_domains)
            if domains & used_domains:
                held.append((lane.lane_id, "CONFLICT_DOMAIN_BUSY"))
                continue
            if len(safe) >= max_parallel_lanes:
                held.append((lane.lane_id, "PARALLEL_CAP_REACHED"))
                continue
            safe.append(lane)
            used_domains |= domains
        body = {
            "schema": SCHEMA, "algorithm": ALGORITHM, "mission_id": mission_id,
            "selected_route_id": selected.route_id,
            "route_ranking": [(route.route_id, round(route.score, 12)) for route in ranking],
            "parallel_lanes": [_lane_payload(lane) for lane in safe],
            "serial_lanes": [_lane_payload(lane) for lane in serial],
            "held_lanes": held, "sol62_invariants": list(cls.SOL62_INVARIANTS),
            "provider_effect_authorized": bool(serial), "stable_promotion_authorized": auth.stable_promotion_authorized,
        }
        return MissionPlan(
            schema=SCHEMA, algorithm=ALGORITHM, mission_id=mission_id, selected_route_id=selected.route_id,
            route_ranking=tuple(body["route_ranking"]), parallel_lanes=tuple(safe), serial_lanes=tuple(serial),
            held_lanes=tuple(held), sol62_invariants=cls.SOL62_INVARIANTS,
            provider_effect_authorized=bool(serial), stable_promotion_authorized=auth.stable_promotion_authorized,
            plan_sha256=_stable_hash(body),
        )


class SafeBotSwarmExecutor:
    @staticmethod
    async def _run_lane(lane: WorkLane, handler: Callable[[WorkLane], Awaitable[Mapping[str, Any]]]) -> BotLaneResult:
        try:
            result = dict(await handler(lane))
            semantic = result.get("semantic_verified") is True
            proof = result.get("proof_valid") is True
            provider_effect = result.get("provider_effect_performed") is True
            if provider_effect:
                raise AuthorityBoundaryError("SAFE_BOT_SWARM_PROVIDER_EFFECT_FORBIDDEN")
            status = "SUCCESS" if semantic and proof else "FAILURE"
            return BotLaneResult(lane.lane_id, lane.transition_id, lane.bot_role.value, status, semantic, proof, str(result.get("evidence_ref", "")))
        except Exception as exc:
            return BotLaneResult(lane.lane_id, lane.transition_id, lane.bot_role.value, "FAILURE", False, False, "", f"{type(exc).__name__}:{exc}")

    @classmethod
    async def execute(cls, plan: MissionPlan, handlers: Mapping[str, Callable[[WorkLane], Awaitable[Mapping[str, Any]]]]) -> BotSwarmReceipt:
        if plan.serial_lanes:
            raise AuthorityBoundaryError("SAFE_BOT_SWARM_CANNOT_EXECUTE_SERIAL_PROVIDER_LANES")
        for lane in plan.parallel_lanes:
            if lane.effect_class not in {EffectClass.NO_EFFECT, EffectClass.READ_ONLY}:
                raise AuthorityBoundaryError(f"UNSAFE_PARALLEL_EFFECT_CLASS:{lane.lane_id}")
            if lane.lane_id not in handlers:
                raise OrchestrationError(f"MISSING_BOT_HANDLER:{lane.lane_id}")
        tasks = [cls._run_lane(lane, handlers[lane.lane_id]) for lane in plan.parallel_lanes]
        results = tuple(await asyncio.gather(*tasks))
        passed = sum(item.status == "SUCCESS" for item in results)
        failed = len(results) - passed
        body = {"schema": SCHEMA, "mission_id": plan.mission_id, "plan_sha256": plan.plan_sha256,
                "parallel_lane_count": len(plan.parallel_lanes), "passed_lane_count": passed, "failed_lane_count": failed,
                "provider_effect_observed": False, "stable_promotion_authorized": False, "results": [asdict(item) for item in results]}
        return BotSwarmReceipt(SCHEMA, plan.mission_id, plan.plan_sha256, len(plan.parallel_lanes), passed, failed, False, False, results, _stable_hash(body))


def aegis_current_mission_plan(auth: AuthorizationContext | None = None) -> MissionPlan:
    routes = (
        RouteCandidate("reuse-federation-sol62", RouteFamily.REUSE_OPTIMISE, "Reuse SOL 6.2, existing WIF, Cloud Run, Firestore and proof fabrics with minimal AEGIS adapters.", 0.88, 0.70, 0.92, 0.90, 0.08, 0.10, 0.12, 0.25, 0.98),
        RouteCandidate("compose-sol62-formation-slos-fuse", RouteFamily.COMPOSE_EXTEND, "Compose SOL 6.2 transactional proof with Formation/Alpha→Omega route tournament, SLOS bounded parallelism and FUSE adapters.", 0.98, 0.92, 0.97, 0.90, 0.07, 0.14, 0.10, 0.23, 0.96),
        RouteCandidate("clean-slate-aegis-control-plane", RouteFamily.MATERIAL_NEW, "Build a separate always-on AEGIS authority/runtime plane.", 0.72, 0.80, 0.58, 0.55, 0.30, 0.52, 0.62, 0.62, 0.12),
        RouteCandidate("reversible-local-orchestration-court", RouteFamily.REVERSIBLE_EXPERIMENT, "Run a no-effect local SOL62/Formation/SLOS bot-swarm qualification before provider admission.", 0.76, 0.94, 0.91, 1.00, 0.02, 0.03, 0.03, 0.08, 0.90),
    )
    common = ("compose-sol62-formation-slos-fuse", "reversible-local-orchestration-court")
    lanes = (
        WorkLane("cfbe-harvest", "tr-harvest", BotRole.HARVEST, "Extend current defensive market capability harvest and evidence map.", EffectClass.READ_ONLY, ("market-evidence",), common, 0.92, 0.86, 0.70, 0.25, 0.02, 0.05, "aegis:harvest:v1", "harvest ledger + source/provenance readback"),
        WorkLane("red-team", "tr-red-team", BotRole.RED_TEAM, "Attack false-completion, privacy, poisoning, drift and authority assumptions.", EffectClass.NO_EFFECT, ("red-team-court",), common, 0.95, 0.90, 0.90, 0.30, 0.01, 0.04, "aegis:redteam:v1", "adversarial court receipt"),
        WorkLane("proof-court", "tr-proof", BotRole.TEST, "Run deterministic regression, secret, persistence and rollback contracts.", EffectClass.NO_EFFECT, ("test-court",), common, 0.98, 0.75, 1.00, 0.35, 0.01, 0.03, "aegis:proofcourt:v1", "all required local test gates + immutable receipt"),
        WorkLane("privacy-review", "tr-privacy", BotRole.PRIVACY, "Verify telemetry minimization, consent and no covert-collection regressions.", EffectClass.NO_EFFECT, ("privacy-court",), common, 0.96, 0.82, 0.85, 0.28, 0.01, 0.03, "aegis:privacy:v1", "privacy court receipt"),
        WorkLane("fuse-adapter", "tr-fuse", BotRole.SYNTHESIS, "Compile provider-neutral FUSE interoperability contract without effect authority.", EffectClass.NO_EFFECT, ("fuse-contract",), common, 0.90, 0.70, 0.55, 0.24, 0.01, 0.05, "aegis:fuse-adapter:v1", "adapter schema + deterministic contract tests"),
        WorkLane("fdof-currentness", "tr-fdof", BotRole.FDOF, "Read current repository fence/main state before any source mutation.", EffectClass.READ_ONLY, ("fdof-state",), common, 0.99, 0.95, 1.00, 0.12, 0.00, 0.01, "aegis:fdof-currentness:v1", "fresh main + lease state readback"),
        WorkLane("blind-10x-court", "tr-10x", BotRole.BENCHMARK, "Run comparable blind benchmark only when baseline datasets are present.", EffectClass.NO_EFFECT, ("benchmark-court",), common, 0.88, 0.92, 0.65, 0.40, 0.03, 0.06, "aegis:10x:v1", "matched baseline + quality-floor receipt"),
        WorkLane("gemini-semantic-canary", "tr-gemini", BotRole.PROVIDER, "Run bounded synthetic Gemini semantic-assist canary after provider/cost/privacy proof.", EffectClass.PROVIDER_CALL, ("gemini-provider",), ("compose-sol62-formation-slos-fuse",), 0.76, 0.86, 0.45, 0.45, 0.08, 0.12, "aegis:gemini:semantic:v1", "model/request/usage/latency + semantic verification receipt"),
        WorkLane("source-admission", "tr-source", BotRole.EVIDENCE, "Admit exact AEGIS source through one lawful FDOF-fenced PR epoch.", EffectClass.MUTATING, ("github-source", "fdof-repository-critical-section"), ("compose-sol62-formation-slos-fuse",), 0.99, 0.85, 1.00, 0.55, 0.01, 0.10, "aegis:source-admission:v1", "exact-head Airlock/Bubbles/Leak + signed-main readback"),
        WorkLane("gcp-private-canary", "tr-gcp", BotRole.PROVIDER, "Deploy private zero-traffic AEGIS canary and prove cross-revision persistence + rollback.", EffectClass.MUTATING, ("gcp-aegis-service", "artifact-registry", "secret-manager"), ("compose-sol62-formation-slos-fuse",), 1.00, 0.95, 1.00, 0.70, 0.10, 0.12, "aegis:gcp-canary:v1", "provider-native identity/private-IAM/secret/persistence/rollback receipt"),
    )
    return Sol62AlphaOmegaPlanner.plan(mission_id="AEGIS-OMEGA-PRODUCTION", routes=routes, lanes=lanes, auth=auth, max_parallel_lanes=8)


def mission_plan_public_dict(plan: MissionPlan) -> dict[str, Any]:
    return {
        "schema": plan.schema, "algorithm": plan.algorithm, "mission_id": plan.mission_id,
        "selected_route_id": plan.selected_route_id, "route_ranking": [list(item) for item in plan.route_ranking],
        "parallel_lanes": [{"lane_id": lane.lane_id, "transition_id": lane.transition_id, "bot_role": lane.bot_role.value, "objective": lane.objective, "effect_class": lane.effect_class.value, "expected_readback": lane.expected_readback} for lane in plan.parallel_lanes],
        "serial_lanes": [{"lane_id": lane.lane_id, "transition_id": lane.transition_id, "bot_role": lane.bot_role.value, "objective": lane.objective, "effect_class": lane.effect_class.value, "expected_readback": lane.expected_readback} for lane in plan.serial_lanes],
        "held_lanes": [list(item) for item in plan.held_lanes], "sol62_invariants": list(plan.sol62_invariants),
        "provider_effect_authorized": plan.provider_effect_authorized, "stable_promotion_authorized": plan.stable_promotion_authorized,
        "plan_sha256": plan.plan_sha256, "ai_bots_are_logical_roles": True, "hidden_background_execution_claimed": False,
    }


__all__ = ["ALGORITHM", "SCHEMA", "AuthorityBoundaryError", "AuthorizationContext", "BotLaneResult", "BotRole", "BotSwarmReceipt", "EffectClass", "FormationRouteTournament", "MissionPlan", "OrchestrationError", "RouteCandidate", "RouteFamily", "SafeBotSwarmExecutor", "Sol62AlphaOmegaPlanner", "WorkLane", "aegis_current_mission_plan", "mission_plan_public_dict"]
