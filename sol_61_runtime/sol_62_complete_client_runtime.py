from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Mapping, Protocol, Sequence

try:
    from .sol_62_frontier_primitives import (
        AuthorityError,
        ConstraintError,
        ProofEnvelope,
        ProofError,
        digest,
    )
    from .sol_62_runtime import ExecutionIntent, MissionSpec, TransitionSpec
    from .sol_62_strict_runtime import Sol62StrictRuntime
    from .sol_62_sovereign_plane_binding import Sol62SovereignPlaneBinding
    from .sol_62_intelligence_amplifier import CognitionProfile, compile_intelligence_plan
except ImportError:
    from sol_62_frontier_primitives import (
        AuthorityError,
        ConstraintError,
        ProofEnvelope,
        ProofError,
        digest,
    )
    from sol_62_runtime import ExecutionIntent, MissionSpec, TransitionSpec
    from sol_62_strict_runtime import Sol62StrictRuntime
    from sol_62_sovereign_plane_binding import Sol62SovereignPlaneBinding
    from sol_62_intelligence_amplifier import CognitionProfile, compile_intelligence_plan


SCHEMA = "SOL_6_2_COMPLETE_FUSE_CLIENT_RUNTIME_V1"
VERSION = "1.1.0"

ROUTE_LOCAL_CODES = frozenset(
    {
        "CONTEXT_LIMIT",
        "MAX_WEIGHTED_TOKENS",
        "CONVERSATION_TOO_LONG",
        "RATE_LIMIT",
        "QUOTA_EXHAUSTED",
        "RESOURCE_EXHAUSTED",
        "MODEL_UNAVAILABLE",
        "TOOL_UNAVAILABLE",
        "UI_UNAVAILABLE",
        "PROVIDER_TIMEOUT",
        "NETWORK_TRANSIENT",
        "SERVICE_UNAVAILABLE",
        "CAPACITY",
        "PROVIDER_RESTRICTION",
    }
)
AUTHORITY_CODES = frozenset(
    {
        "AUTHORITY_REQUIRED",
        "APPROVAL_REQUIRED",
        "PERMISSION_DENIED",
        "AUTHENTICATION_REQUIRED",
        "IAM_REQUIRED",
        "OWNER_EFFECT_APPROVAL_REQUIRED",
    }
)
PRIVACY_CODES = frozenset({"PRIVACY_BOUNDARY", "DATA_RESIDENCY_BOUNDARY", "SECRET_BOUNDARY"})
LEGAL_CODES = frozenset({"LEGAL_BOUNDARY", "COMPLIANCE_BOUNDARY", "LICENSE_BOUNDARY"})
SAFETY_CODES = frozenset({"SAFETY_BOUNDARY", "RISK_BOUNDARY", "POLICY_BOUNDARY"})


class ConstraintDisposition(str, Enum):
    ROUTE_LOCAL = "ROUTE_LOCAL"
    AUTHORITY_GATE = "AUTHORITY_GATE"
    PRIVACY_GATE = "PRIVACY_GATE"
    LEGAL_GATE = "LEGAL_GATE"
    SAFETY_GATE = "SAFETY_GATE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ProviderConstraint:
    code: str
    disposition: ConstraintDisposition
    mission_terminal: bool
    goal_mutation_allowed: bool
    retry_requires_changed_route: bool


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    route_id: str
    provider: str
    capabilities: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()
    current: bool = True
    callable: bool = True
    authorized: bool = True
    privacy_ok: bool = True
    priority: int = 50
    cost_class: str = "UNKNOWN"
    failure_domain: str = "UNSPECIFIED"


@dataclass(frozen=True, slots=True)
class TransitionBinding:
    transition_id: str
    payload: Mapping[str, Any]
    expected_readback: Mapping[str, Any]
    semantics: str = "IDEMPOTENT"
    actor: str = "sol62-client-runtime"
    rollback_required: bool = False
    mode: str = "AUTO"
    requested_models: tuple[str, ...] = ()
    requested_sources: tuple[str, ...] = ()
    requested_agents: tuple[str, ...] = ()
    effect_class: str = "READ_ONLY"
    proof_id: str = ""


@dataclass(frozen=True, slots=True)
class ClientRuntimePolicy:
    max_attempts_per_wake: int = 8
    max_total_attempts: int = 128
    negative_cache_seconds: int = 300
    retry_delay_seconds: int = 30
    fence_ttl_seconds: int = 120
    auto_harvest: bool = True
    auto_build: bool = True
    auto_reroute: bool = True
    auto_retry: bool = True
    continue_until_verified: bool = True


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    mission_id: str
    transition_id: str
    effect_id: str
    route: RouteCandidate
    binding: TransitionBinding
    objective: str


@dataclass(frozen=True, slots=True)
class ExecutionResponse:
    success: bool
    dispatch_started: bool = False
    provider_ref: str = ""
    readback: Mapping[str, Any] = field(default_factory=dict)
    constraint_code: str = ""
    message: str = ""
    proof_evidence: Any = None
    evidence_class: str = "GATEWAY_READBACK"
    proof_issuer: str = "FUSE"
    signature_ref: str = ""
    attestation_verified: bool = False
    scope: str = "FUSE_CLIENT"


@dataclass(frozen=True, slots=True)
class HarvestOutcome:
    routes: tuple[RouteCandidate, ...] = ()
    transitions: tuple[TransitionSpec, ...] = ()
    bindings: tuple[TransitionBinding, ...] = ()
    build_required: bool = False
    build_packet: Mapping[str, Any] = field(default_factory=dict)
    reason: str = ""


class ExecutionAdapter(Protocol):
    async def execute(self, request: ExecutionRequest) -> ExecutionResponse: ...


class CapabilityHarvester(Protocol):
    async def harvest(
        self,
        *,
        mission_id: str,
        transition_id: str | None,
        objective: str,
        reason: str,
    ) -> HarvestOutcome: ...


AuthorityLeaseResolver = Callable[[str, Mapping[str, Any]], str | None]


def classify_provider_constraint(code: str, message: str = "") -> ProviderConstraint:
    normalized = (code or "").strip().upper()
    text = (message or "").upper()
    if normalized in ROUTE_LOCAL_CODES or any(
        marker in text
        for marker in (
            "CONTEXT LIMIT",
            "MAX WEIGHTED TOKENS",
            "RATE LIMIT",
            "QUOTA",
            "RESOURCE EXHAUSTED",
            "MODEL UNAVAILABLE",
            "TOOL UNAVAILABLE",
            "SERVICE UNAVAILABLE",
        )
    ):
        return ProviderConstraint(
            normalized or "PROVIDER_RESTRICTION",
            ConstraintDisposition.ROUTE_LOCAL,
            mission_terminal=False,
            goal_mutation_allowed=False,
            retry_requires_changed_route=True,
        )
    if normalized in AUTHORITY_CODES or any(marker in text for marker in ("PERMISSION DENIED", "APPROVAL REQUIRED", "AUTHORITY REQUIRED")):
        disposition = ConstraintDisposition.AUTHORITY_GATE
    elif normalized in PRIVACY_CODES:
        disposition = ConstraintDisposition.PRIVACY_GATE
    elif normalized in LEGAL_CODES:
        disposition = ConstraintDisposition.LEGAL_GATE
    elif normalized in SAFETY_CODES:
        disposition = ConstraintDisposition.SAFETY_GATE
    else:
        disposition = ConstraintDisposition.UNKNOWN
    return ProviderConstraint(
        normalized or "UNKNOWN_PROVIDER_FAILURE",
        disposition,
        mission_terminal=False,
        goal_mutation_allowed=False,
        retry_requires_changed_route=disposition == ConstraintDisposition.UNKNOWN,
    )


class Sol62CompleteClientRuntime:
    """Owner-facing autonomous client/runtime projection over the canonical SOL 6.2 truth spine.

    This class adds client sessions, route portfolios, capability-gap harvesting,
    bounded changed-route retries and durable continuation state. It does not
    introduce another mission database, scheduler, proof root or authority plane.
    """

    def __init__(
        self,
        runtime: Sol62StrictRuntime,
        *,
        policy: ClientRuntimePolicy | None = None,
        sovereign_plane: Sol62SovereignPlaneBinding | None = None,
    ) -> None:
        self.runtime = runtime
        self.policy = policy or ClientRuntimePolicy()
        self.sovereign_plane = sovereign_plane or Sol62SovereignPlaneBinding()
        self._register_client_schemas()

    def _register_client_schemas(self) -> None:
        self.runtime.control.register_schema(
            "sol62.client.runtime",
            1,
            {
                "schema": SCHEMA,
                "truth_root": "SOL_6_2",
                "provider_specific_limits": "ROUTE_LOCAL_UNLESS_HARD_GATE",
                "completion": "SOL62_VERIFIED_REALITY_ONLY",
                "orchestration_plane": self.sovereign_plane.contract.plane_id,
                "estate_resolution_service": self.sovereign_plane.contract.estate_resolution_service,
                "route_portfolio_policy": self.sovereign_plane.contract.route_portfolio_policy,
                "resident_executor": self.sovereign_plane.contract.resident_executor,
            },
        )

    def _put(self, namespace: str, key: str, value: Mapping[str, Any]) -> dict[str, Any]:
        body = dict(value)
        current = self.runtime.control.get_state(namespace, key)
        expected = int(current["version"]) if current else 0
        version = self.runtime.control.cas_put(namespace, key, body, expected_version=expected)
        return {"value": body, "version": version}

    def _get(self, namespace: str, key: str) -> dict[str, Any] | None:
        return self.runtime.control.get_state(namespace, key)

    def _rows(self, namespace: str) -> list[dict[str, Any]]:
        rows = self.runtime.control.db.execute(
            "SELECT item_key,value_json,version,updated_at FROM state WHERE namespace=? ORDER BY item_key",
            (namespace,),
        ).fetchall()
        import json
        return [
            {
                "key": row["item_key"],
                "value": json.loads(row["value_json"]),
                "version": int(row["version"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def _derive_cognition_profile(
        self,
        mission_id: str,
        transition_id: str | None = None,
    ) -> CognitionProfile:
        mission_row = self._get("sol62.mission", mission_id)
        client_row = self._get("sol62.client.mission", mission_id)
        if not mission_row or not client_row:
            raise ConstraintError("SOL62_MISSION_NOT_REGISTERED")

        mission = mission_row["value"]
        client = client_row["value"]
        objective = str(mission.get("objective", ""))
        constraints = tuple(mission.get("constraints", ()))
        proof_ids = tuple(client.get("proof_ids", ()))
        total_attempts = int(client.get("total_attempts", 0))
        last_reason = str(client.get("last_reason", "")).upper()

        transition = {}
        binding = None
        if transition_id:
            row = self._get("sol62.transition", transition_id)
            transition = dict(row["value"]) if row else {}
            binding = self._binding(transition_id)

        risk_class = str(transition.get("risk_class", "LOW")).upper()
        consequential = bool(transition.get("consequential", False))
        stakes = 0.92 if consequential or risk_class in {"HIGH", "CRITICAL", "R4", "R5"} else 0.62
        reversibility = 0.30 if consequential else 0.82
        if binding and binding.rollback_required:
            reversibility = max(reversibility, 0.52)

        complexity = min(
            1.0,
            0.38
            + min(0.28, len(objective) / 12000.0)
            + min(0.22, len(constraints) * 0.04)
            + (0.12 if transition_id else 0.0),
        )
        evidence_gap = max(0.18, 0.86 - 0.14 * len(proof_ids))
        uncertainty = max(0.22, 0.78 - 0.10 * len(proof_ids))
        novelty = 0.78 if any(
            marker in last_reason
            for marker in ("BUILD", "NO_QUALIFIED_ROUTE", "UNBOUND", "EXHAUSTED", "MISSING")
        ) else 0.48
        if total_attempts >= 3:
            novelty = max(novelty, 0.68)
            uncertainty = max(uncertainty, 0.66)

        failure_domains = {
            str(row["value"].get("failure_domain", ""))
            for row in self._rows("sol62.client.route")
            if row["value"].get("current", True)
            and row["value"].get("callable", True)
            and row["value"].get("failure_domain")
        }

        return CognitionProfile(
            complexity=round(complexity, 6),
            stakes=round(stakes, 6),
            uncertainty=round(uncertainty, 6),
            novelty=round(novelty, 6),
            evidence_gap=round(evidence_gap, 6),
            time_pressure=0.0,
            reversibility=round(reversibility, 6),
            multi_domain=len(failure_domains) >= 2,
        )

    def refresh_intelligence_plan(
        self,
        mission_id: str,
        *,
        transition_id: str | None = None,
    ) -> dict[str, Any]:
        profile = self._derive_cognition_profile(mission_id, transition_id)
        plan = compile_intelligence_plan(profile)
        body = {
            "schema": "SOL62_INTELLIGENCE_PLAN_V1",
            "mission_id": mission_id,
            "transition_id": transition_id or "",
            "profile": dataclasses.asdict(profile),
            "plan_id": plan.plan_id,
            "mode": plan.mode.value,
            "reasoning_budget": plan.reasoning_budget,
            "max_parallel_strategies": plan.max_parallel_strategies,
            "selected_strategies": [
                dataclasses.asdict(item) for item in plan.selected_strategies
            ],
            "required_checks": list(plan.required_checks),
            "stop_conditions": list(plan.stop_conditions),
            "uncertainty_reporting_required": plan.uncertainty_reporting_required,
            "independent_verifier_required": plan.independent_verifier_required,
            "authority_expansion": False,
            "provider_effect_authorized": False,
            "goal_mutation_allowed": False,
            "truth_root_replacement_allowed": False,
        }
        key = f"{mission_id}|{transition_id or 'MISSION'}"
        previous = self._get("sol62.client.intelligence_plan", key)
        stored = self._put("sol62.client.intelligence_plan", key, body)
        if not previous or previous["value"].get("plan_id") != plan.plan_id:
            self.runtime.control.append_event(
                mission_id,
                "SOL62_INTELLIGENCE_PLAN_REFRESHED",
                {
                    "transition_id": transition_id or "",
                    "plan_id": plan.plan_id,
                    "mode": plan.mode.value,
                    "reasoning_budget": plan.reasoning_budget,
                    "authority_expansion": False,
                },
            )
        return stored

    def create_client_session(
        self,
        session_id: str,
        *,
        owner_subject: str,
        client_kind: str = "FUSE_WEB",
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        if not session_id or not owner_subject:
            raise ConstraintError("CLIENT_SESSION_ID_AND_OWNER_REQUIRED")
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        existing = self._get("sol62.client.session", session_id)
        body = {
            "schema": SCHEMA,
            "session_id": session_id,
            "owner_subject": owner_subject,
            "client_kind": client_kind,
            "created_epoch": existing["value"]["created_epoch"] if existing else now_epoch,
            "last_seen_epoch": now_epoch,
            "provider_credentials_in_client": False,
            "chat_is_detachable": True,
            "orchestration_plane": self.sovereign_plane.contract.plane_id,
        }
        stored = self._put("sol62.client.session", session_id, body)
        self.runtime.control.append_event(session_id, "SOL62_CLIENT_SESSION_BOUND", body)
        return stored

    def bind_mission(
        self,
        mission_id: str,
        *,
        owner_subject: str,
        session_id: str = "",
        satisfied_constraints: Sequence[str] = (),
    ) -> dict[str, Any]:
        mission = self._get("sol62.mission", mission_id)
        if not mission:
            raise ConstraintError("SOL62_MISSION_NOT_REGISTERED")
        existing = self._get("sol62.client.mission", mission_id)
        body = {
            "schema": SCHEMA,
            "mission_id": mission_id,
            "owner_subject": owner_subject,
            "session_id": session_id,
            "state": "ACTIVE",
            "proof_ids": list(existing["value"].get("proof_ids", [])) if existing else [],
            "satisfied_constraints": sorted(set(satisfied_constraints) | set(existing["value"].get("satisfied_constraints", []) if existing else [])),
            "total_attempts": int(existing["value"].get("total_attempts", 0)) if existing else 0,
            "next_retry_epoch": int(existing["value"].get("next_retry_epoch", 0)) if existing else 0,
            "last_reason": existing["value"].get("last_reason", "") if existing else "",
            "goal_mutation_by_provider_forbidden": True,
            "continue_until_verified": self.policy.continue_until_verified,
            "sovereign_plane": self.sovereign_plane.mission_envelope(
                mission_id=mission_id,
                objective=str(mission["value"]["objective"]),
                owner_subject=owner_subject,
                session_id=session_id,
            ),
        }
        stored = self._put("sol62.client.mission", mission_id, body)
        self.runtime.control.append_event(
            mission_id,
            "SOL62_CLIENT_MISSION_BOUND",
            {
                "owner_subject": owner_subject,
                "session_id": session_id,
                "orchestration_plane": self.sovereign_plane.contract.plane_id,
            },
        )
        self.runtime.control.append_event(
            mission_id,
            "SOL62_SOVEREIGN_MISSION_ATTACHED",
            {
                "plane_id": self.sovereign_plane.contract.plane_id,
                "truth_root": "SOL_6_2",
                "resident_executor": self.sovereign_plane.contract.resident_executor,
                "authority_expansion": False,
            },
        )
        self.refresh_intelligence_plan(mission_id)
        return stored

    def bind_transition(self, binding: TransitionBinding) -> dict[str, Any]:
        if not self._get("sol62.transition", binding.transition_id):
            raise ConstraintError("TRANSITION_NOT_REGISTERED")
        body = dataclasses.asdict(binding)
        stored = self._put("sol62.client.transition_binding", binding.transition_id, body)
        self.runtime.control.append_event(binding.transition_id, "SOL62_CLIENT_TRANSITION_BOUND", {"binding_sha256": digest(body)})
        return stored

    def register_route(self, route: RouteCandidate) -> dict[str, Any]:
        if not route.route_id or not route.provider:
            raise ConstraintError("ROUTE_ID_AND_PROVIDER_REQUIRED")
        body = dataclasses.asdict(route)
        stored = self._put("sol62.client.route", route.route_id, body)
        self.runtime.control.append_event(route.route_id, "SOL62_CLIENT_ROUTE_REGISTERED", {"route_sha256": digest(body)})
        return stored

    def mission_status(self, mission_id: str, *, now_epoch: int | None = None) -> dict[str, Any]:
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        client = self._get("sol62.client.mission", mission_id)
        if not client:
            raise KeyError(mission_id)
        proof_ids = tuple(client["value"].get("proof_ids", ()))
        constraints = set(client["value"].get("satisfied_constraints", ()))
        closure = self.runtime.evaluate_mission(
            mission_id,
            proof_ids=proof_ids,
            now_epoch=now_epoch,
            satisfied_constraints=constraints,
        )
        intelligence_row = self._get("sol62.client.intelligence_plan", f"{mission_id}|MISSION")
        intelligence_plan = dict(intelligence_row["value"]) if intelligence_row else {}
        return {
            "schema": SCHEMA,
            "mission_id": mission_id,
            "client": dict(client["value"]),
            "mission_state": dict(self.runtime.mission_state(mission_id)["value"]),
            "closure": closure,
            "integrity": self.runtime.verify_integrity(),
            "sovereign_plane": self.sovereign_plane.status(),
            "intelligence_plan": intelligence_plan,
        }

    def _binding(self, transition_id: str) -> TransitionBinding | None:
        row = self._get("sol62.client.transition_binding", transition_id)
        if not row:
            return None
        body = row["value"]
        return TransitionBinding(
            transition_id=body["transition_id"],
            payload=dict(body.get("payload", {})),
            expected_readback=dict(body.get("expected_readback", {})),
            semantics=body.get("semantics", "IDEMPOTENT"),
            actor=body.get("actor", "sol62-client-runtime"),
            rollback_required=bool(body.get("rollback_required", False)),
            mode=body.get("mode", "AUTO"),
            requested_models=tuple(body.get("requested_models", ())),
            requested_sources=tuple(body.get("requested_sources", ())),
            requested_agents=tuple(body.get("requested_agents", ())),
            effect_class=body.get("effect_class", "READ_ONLY"),
            proof_id=body.get("proof_id", ""),
        )

    def _route(self, body: Mapping[str, Any]) -> RouteCandidate:
        return RouteCandidate(
            route_id=body["route_id"],
            provider=body["provider"],
            capabilities=tuple(body.get("capabilities", ())),
            operations=tuple(body.get("operations", ())),
            current=bool(body.get("current", True)),
            callable=bool(body.get("callable", True)),
            authorized=bool(body.get("authorized", True)),
            privacy_ok=bool(body.get("privacy_ok", True)),
            priority=int(body.get("priority", 50)),
            cost_class=body.get("cost_class", "UNKNOWN"),
            failure_domain=body.get("failure_domain", "UNSPECIFIED"),
        )

    def _negative_cache_key(self, mission_id: str, transition_id: str, route_id: str) -> str:
        return f"{mission_id}|{transition_id}|{route_id}"

    def _negative_cache_active(self, mission_id: str, transition_id: str, route_id: str, now_epoch: int) -> bool:
        row = self._get("sol62.client.negative_route", self._negative_cache_key(mission_id, transition_id, route_id))
        return bool(row and int(row["value"].get("until_epoch", 0)) > now_epoch)

    def _negative_cache(
        self,
        mission_id: str,
        transition_id: str,
        route_id: str,
        *,
        code: str,
        now_epoch: int,
    ) -> None:
        key = self._negative_cache_key(mission_id, transition_id, route_id)
        self._put(
            "sol62.client.negative_route",
            key,
            {
                "mission_id": mission_id,
                "transition_id": transition_id,
                "route_id": route_id,
                "code": code,
                "until_epoch": now_epoch + self.policy.negative_cache_seconds,
                "retry_requires_changed_state": True,
            },
        )
        self.runtime.control.append_event(
            mission_id,
            "SOL62_CLIENT_ROUTE_NEGATIVE_CACHED",
            {"transition_id": transition_id, "route_id": route_id, "code": code},
        )

    def eligible_routes(self, mission_id: str, transition_id: str, *, now_epoch: int) -> list[RouteCandidate]:
        transition = self._get("sol62.transition", transition_id)
        if not transition:
            raise KeyError(transition_id)
        operation = transition["value"]["operation"]
        routes: list[RouteCandidate] = []
        for row in self._rows("sol62.client.route"):
            route = self._route(row["value"])
            if not (route.current and route.callable and route.authorized and route.privacy_ok):
                continue
            if route.operations and operation not in route.operations and "*" not in route.operations:
                continue
            if self._negative_cache_active(mission_id, transition_id, route.route_id, now_epoch):
                continue
            routes.append(route)
        ordered, receipt = self.sovereign_plane.order_routes(
            routes,
            mission_id=mission_id,
            transition_id=transition_id,
            operation=operation,
        )
        self._put(
            "sol62.client.route_election",
            f"{mission_id}|{transition_id}",
            receipt,
        )
        self.runtime.control.append_event(
            mission_id,
            "SOL62_SOVEREIGN_ROUTE_ELECTED",
            {
                "transition_id": transition_id,
                "plane_id": receipt["plane_id"],
                "mode": receipt["mode"],
                "ordered_route_ids": receipt["ordered_route_ids"],
                "authority_expansion": False,
            },
        )
        return ordered

    def _update_client_mission(self, mission_id: str, **changes: Any) -> dict[str, Any]:
        row = self._get("sol62.client.mission", mission_id)
        if not row:
            raise KeyError(mission_id)
        body = dict(row["value"])
        body.update(changes)
        return self._put("sol62.client.mission", mission_id, body)

    def _record_attempt(
        self,
        mission_id: str,
        transition_id: str,
        route_id: str,
        *,
        attempt_no: int,
        state: str,
        detail: Mapping[str, Any],
        now_epoch: int,
    ) -> str:
        key = f"{mission_id}|{transition_id}|{attempt_no:06d}"
        body = {
            "mission_id": mission_id,
            "transition_id": transition_id,
            "route_id": route_id,
            "attempt_no": attempt_no,
            "state": state,
            "detail": dict(detail),
            "at_epoch": now_epoch,
        }
        self._put("sol62.client.attempt", key, body)
        self.runtime.control.append_event(mission_id, "SOL62_CLIENT_ATTEMPT_" + state, body)
        return key

    def _inflight_for_mission(self, mission_id: str) -> list[dict[str, Any]]:
        inflight = []
        for item in self.runtime.recover_inflight_effects():
            intent = self._get("sol62.effect_intent", item["effect_id"])
            if not intent:
                continue
            transition = self._get("sol62.transition", intent["value"]["transition_id"])
            if transition and transition["value"]["mission_id"] == mission_id:
                inflight.append(item)
        return inflight

    async def _apply_harvest(
        self,
        harvester: CapabilityHarvester | None,
        *,
        mission_id: str,
        transition_id: str | None,
        objective: str,
        reason: str,
    ) -> HarvestOutcome:
        gap_key = f"{mission_id}|{transition_id or 'MISSION'}|{digest({'reason': reason})[:12]}"
        self._put(
            "sol62.client.capability_gap",
            gap_key,
            {
                "mission_id": mission_id,
                "transition_id": transition_id,
                "reason": reason,
                "state": "HARVEST_REQUIRED",
            },
        )
        self.runtime.control.append_event(
            mission_id,
            "SOL62_CLIENT_CAPABILITY_GAP",
            {"transition_id": transition_id, "reason": reason},
        )
        if harvester is None or not self.policy.auto_harvest:
            return HarvestOutcome(reason="HARVESTER_UNBOUND")
        outcome = await harvester.harvest(
            mission_id=mission_id,
            transition_id=transition_id,
            objective=objective,
            reason=reason,
        )
        for route in outcome.routes:
            self.register_route(route)
        for transition in outcome.transitions:
            self.runtime.register_transition(transition)
        for binding in outcome.bindings:
            self.bind_transition(binding)
        self._put(
            "sol62.client.capability_gap",
            gap_key,
            {
                "mission_id": mission_id,
                "transition_id": transition_id,
                "reason": reason,
                "state": "HARVESTED" if (outcome.routes or outcome.transitions or outcome.bindings) else "OPEN",
                "build_required": outcome.build_required,
                "build_packet": dict(outcome.build_packet),
            },
        )
        return outcome

    async def _execute_once(
        self,
        *,
        mission_id: str,
        transition_id: str,
        route: RouteCandidate,
        binding: TransitionBinding,
        adapter: ExecutionAdapter,
        gateway_request: Mapping[str, Any],
        identity_claims: Mapping[str, Any],
        worker: str,
        now_epoch: int,
        authority_lease_resolver: AuthorityLeaseResolver | None,
    ) -> dict[str, Any]:
        client = self._get("sol62.client.mission", mission_id)
        if not client:
            raise KeyError(mission_id)
        attempt_no = int(client["value"].get("total_attempts", 0)) + 1
        if attempt_no > self.policy.max_total_attempts:
            return {"state": "HELD_ATTEMPT_BUDGET", "attempt_no": attempt_no}

        transition = self._get("sol62.transition", transition_id)["value"]
        mission = self._get("sol62.mission", mission_id)["value"]
        effect_id = "sol62-client-" + digest(
            {
                "mission_id": mission_id,
                "transition_id": transition_id,
                "route_id": route.route_id,
                "attempt_no": attempt_no,
            }
        )[:24]
        idem = "SOL62-CLIENT:" + digest(
            {
                "mission_id": mission_id,
                "transition_id": transition_id,
                "route_id": route.route_id,
                "attempt_no": attempt_no,
                "payload": dict(binding.payload),
            }
        )
        self._update_client_mission(
            mission_id,
            total_attempts=attempt_no,
            state="RUNNING",
            last_reason="",
            next_retry_epoch=0,
        )
        self._record_attempt(
            mission_id,
            transition_id,
            route.route_id,
            attempt_no=attempt_no,
            state="PREPARING",
            detail={"effect_id": effect_id},
            now_epoch=now_epoch,
        )

        intent = ExecutionIntent(
            effect_id,
            transition_id,
            route.provider,
            dict(binding.payload),
            binding.semantics,
            idem,
            binding.actor,
            transition["source_version"],
            dict(binding.expected_readback),
            binding.rollback_required,
        )
        self.runtime.prepare_execution(
            intent,
            gateway_request=gateway_request,
            identity_claims=identity_claims,
            now_epoch=now_epoch,
        )
        fence = self.runtime.acquire_execution_fence(
            transition_id,
            worker,
            ttl_seconds=self.policy.fence_ttl_seconds,
            now_epoch=now_epoch,
        )
        authority_lease_id = None
        if bool(transition.get("consequential")):
            if authority_lease_resolver is None:
                self._update_client_mission(mission_id, state="HELD_AUTHORITY", last_reason="ACTION_BOUND_AUTHORITY_REQUIRED")
                return {"state": "HELD_GATE", "reason": "ACTION_BOUND_AUTHORITY_REQUIRED"}
            authority_lease_id = authority_lease_resolver(transition_id, transition)
            if not authority_lease_id:
                self._update_client_mission(mission_id, state="HELD_AUTHORITY", last_reason="ACTION_BOUND_AUTHORITY_REQUIRED")
                return {"state": "HELD_GATE", "reason": "ACTION_BOUND_AUTHORITY_REQUIRED"}

        self.runtime.authorize_dispatch(
            effect_id,
            authority_lease_id=authority_lease_id,
            actor=binding.actor,
            source_version=transition["source_version"],
            now_epoch=now_epoch,
            worker=worker,
            lease_epoch=fence["epoch"],
            fencing_token=fence["fencing_token"],
        )

        request = ExecutionRequest(
            mission_id=mission_id,
            transition_id=transition_id,
            effect_id=effect_id,
            route=route,
            binding=binding,
            objective=mission["objective"],
        )
        try:
            response = await adapter.execute(request)
        except Exception as exc:
            self._record_attempt(
                mission_id,
                transition_id,
                route.route_id,
                attempt_no=attempt_no,
                state="UNKNOWN_EFFECT",
                detail={"effect_id": effect_id, "error_class": type(exc).__name__, "error_sha256": digest(str(exc))},
                now_epoch=now_epoch,
            )
            self._update_client_mission(
                mission_id,
                state="WAITING_READBACK",
                last_reason="ADAPTER_EXCEPTION_EFFECT_STATE_UNKNOWN",
                next_retry_epoch=now_epoch + self.policy.retry_delay_seconds,
            )
            return {"state": "WAITING_READBACK", "reason": "ADAPTER_EXCEPTION_EFFECT_STATE_UNKNOWN"}

        if not response.success:
            constraint = classify_provider_constraint(response.constraint_code, response.message)
            if not response.dispatch_started:
                self.runtime.control.transition_effect(
                    effect_id,
                    expected_state="DISPATCHING",
                    next_state="CANCELLED",
                    result={
                        "constraint_code": constraint.code,
                        "disposition": constraint.disposition.value,
                    },
                )
                self._record_attempt(
                    mission_id,
                    transition_id,
                    route.route_id,
                    attempt_no=attempt_no,
                    state="REJECTED_PRE_DISPATCH",
                    detail={"constraint": dataclasses.asdict(constraint)},
                    now_epoch=now_epoch,
                )
                if constraint.disposition == ConstraintDisposition.ROUTE_LOCAL and self.policy.auto_reroute:
                    self._negative_cache(
                        mission_id,
                        transition_id,
                        route.route_id,
                        code=constraint.code,
                        now_epoch=now_epoch,
                    )
                    return {"state": "RETRY_CHANGED_ROUTE", "constraint": dataclasses.asdict(constraint)}
                self._update_client_mission(
                    mission_id,
                    state="HELD_GATE",
                    last_reason=constraint.code,
                    next_retry_epoch=0,
                )
                return {"state": "HELD_GATE", "constraint": dataclasses.asdict(constraint)}

            if response.provider_ref:
                self.runtime.mark_dispatched(effect_id, provider_ref=response.provider_ref)
            if response.readback and response.provider_ref:
                self.runtime.observe_effect(effect_id, readback=response.readback)
            self._record_attempt(
                mission_id,
                transition_id,
                route.route_id,
                attempt_no=attempt_no,
                state="WAITING_READBACK",
                detail={"constraint_code": response.constraint_code, "provider_ref": response.provider_ref},
                now_epoch=now_epoch,
            )
            self._update_client_mission(
                mission_id,
                state="WAITING_READBACK",
                last_reason=response.constraint_code or "PROVIDER_EFFECT_STATE_UNKNOWN",
                next_retry_epoch=now_epoch + self.policy.retry_delay_seconds,
            )
            return {"state": "WAITING_READBACK", "reason": response.constraint_code or "PROVIDER_EFFECT_STATE_UNKNOWN"}

        if not response.provider_ref:
            raise ConstraintError("SUCCESS_RESPONSE_REQUIRES_PROVIDER_REFERENCE")
        self.runtime.mark_dispatched(effect_id, provider_ref=response.provider_ref)
        observed = self.runtime.observe_effect(effect_id, readback=response.readback)
        if not observed["match"]:
            self._update_client_mission(
                mission_id,
                state="WAITING_READBACK",
                last_reason="READBACK_MISMATCH",
                next_retry_epoch=now_epoch + self.policy.retry_delay_seconds,
            )
            return {"state": "WAITING_READBACK", "reason": "READBACK_MISMATCH"}

        proof_ids = list(client["value"].get("proof_ids", ()))
        if response.proof_evidence is not None:
            proof_id = binding.proof_id or (
                "sol62-client-proof-" + digest(
                    {
                        "mission_id": mission_id,
                        "transition_id": transition_id,
                        "effect_id": effect_id,
                        "provider_ref": response.provider_ref,
                    }
                )[:24]
            )
            attributes = {
                "effect_id": effect_id,
                "readback_sha256": digest(response.readback),
                "route_id": route.route_id,
            }
            envelope = ProofEnvelope.from_evidence(
                proof_id=proof_id,
                subject=f"transition:{transition_id}",
                target=transition["target"],
                operation=transition["operation"],
                issuer=response.proof_issuer,
                source_version=transition["source_version"],
                evidence=response.proof_evidence,
                provider_correlation_id=response.provider_ref,
                signature_ref=response.signature_ref,
                evidence_class=response.evidence_class,
                scope=response.scope,
                attributes=attributes,
            )
            self.runtime.register_verified_proof(
                envelope,
                response.proof_evidence,
                semantic_verifier=lambda p, e: digest(e) == p.evidence_sha256,
                now_epoch=now_epoch,
                attestation_verifier=(
                    (lambda p, e: bool(response.attestation_verified))
                    if response.evidence_class in {"PROVIDER_NATIVE", "PROVIDER_LIVE", "PROVIDER_READBACK", "PROVIDER_ATTESTED"}
                    else None
                ),
            )
            if proof_id not in proof_ids:
                proof_ids.append(proof_id)

        committed = self.runtime.verify_effect_and_commit(
            effect_id,
            proof_ids=proof_ids,
            now_epoch=now_epoch,
            satisfied_constraints=set(client["value"].get("satisfied_constraints", ())),
        )
        self._update_client_mission(
            mission_id,
            proof_ids=proof_ids,
            state="ACTIVE",
            last_reason="TRANSITION_VERIFIED",
            next_retry_epoch=0,
        )
        self._record_attempt(
            mission_id,
            transition_id,
            route.route_id,
            attempt_no=attempt_no,
            state="VERIFIED",
            detail={"effect_id": effect_id, "provider_ref": response.provider_ref, "event_hash": committed["event_hash"]},
            now_epoch=now_epoch,
        )
        return {"state": "VERIFIED_STEP", "commit": committed}

    async def wake_until_terminal(
        self,
        mission_id: str,
        *,
        adapter: ExecutionAdapter,
        gateway_request: Mapping[str, Any],
        identity_claims: Mapping[str, Any],
        worker: str,
        now_epoch: int | None = None,
        harvester: CapabilityHarvester | None = None,
        authority_lease_resolver: AuthorityLeaseResolver | None = None,
        max_steps: int | None = None,
    ) -> dict[str, Any]:
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        max_steps = self.policy.max_attempts_per_wake if max_steps is None else min(int(max_steps), self.policy.max_attempts_per_wake)
        if max_steps < 1:
            raise ValueError("MAX_STEPS_INVALID")
        client = self._get("sol62.client.mission", mission_id)
        if not client:
            raise ConstraintError("CLIENT_MISSION_NOT_BOUND")
        mission = self._get("sol62.mission", mission_id)["value"]

        for _ in range(max_steps):
            client = self._get("sol62.client.mission", mission_id)
            proof_ids = tuple(client["value"].get("proof_ids", ()))
            constraints = set(client["value"].get("satisfied_constraints", ()))
            closure = self.runtime.evaluate_mission(
                mission_id,
                proof_ids=proof_ids,
                now_epoch=now_epoch,
                satisfied_constraints=constraints,
            )
            if closure["state"] == "VERIFIED_REALITY":
                self._update_client_mission(
                    mission_id,
                    state="VERIFIED_REALITY",
                    last_reason="TARGET_STATE_PLUS_PROOF_VERIFIED",
                    next_retry_epoch=0,
                )
                return {"state": "VERIFIED_REALITY", "closure": closure}

            inflight = self._inflight_for_mission(mission_id)
            if inflight:
                self._update_client_mission(
                    mission_id,
                    state="WAITING_READBACK",
                    last_reason="INFLIGHT_EFFECT_REQUIRES_RECONCILIATION",
                    next_retry_epoch=now_epoch + self.policy.retry_delay_seconds,
                )
                return {"state": "WAITING_READBACK", "inflight": inflight}

            ready = self.runtime.ready_transitions(
                mission_id,
                satisfied_constraints=constraints,
                capacity=1,
            )
            if not ready:
                outcome = await self._apply_harvest(
                    harvester,
                    mission_id=mission_id,
                    transition_id=None,
                    objective=mission["objective"],
                    reason="NO_READY_TRANSITION",
                )
                if outcome.transitions or outcome.bindings:
                    continue
                state = "WAITING_BUILD" if outcome.build_required else "WAITING_DEPENDENCY"
                self._update_client_mission(
                    mission_id,
                    state=state,
                    last_reason=outcome.reason or "NO_READY_TRANSITION",
                    next_retry_epoch=now_epoch + self.policy.retry_delay_seconds,
                )
                return {
                    "state": state,
                    "build_required": outcome.build_required,
                    "build_packet": dict(outcome.build_packet),
                    "resume_packet": self.resume_packet(mission_id, reason=state),
                }

            transition_id = ready[0]
            self.refresh_intelligence_plan(mission_id, transition_id=transition_id)
            binding = self._binding(transition_id)
            if binding is None:
                outcome = await self._apply_harvest(
                    harvester,
                    mission_id=mission_id,
                    transition_id=transition_id,
                    objective=mission["objective"],
                    reason="TRANSITION_EXECUTION_BINDING_MISSING",
                )
                if outcome.bindings:
                    continue
                self._update_client_mission(
                    mission_id,
                    state="WAITING_BUILD",
                    last_reason="TRANSITION_EXECUTION_BINDING_MISSING",
                    next_retry_epoch=now_epoch + self.policy.retry_delay_seconds,
                )
                return {
                    "state": "WAITING_BUILD",
                    "build_required": True,
                    "build_packet": dict(outcome.build_packet),
                    "resume_packet": self.resume_packet(mission_id, reason="WAITING_BUILD"),
                }

            routes = self.eligible_routes(mission_id, transition_id, now_epoch=now_epoch)
            if not routes:
                outcome = await self._apply_harvest(
                    harvester,
                    mission_id=mission_id,
                    transition_id=transition_id,
                    objective=mission["objective"],
                    reason="NO_QUALIFIED_ROUTE",
                )
                if outcome.routes:
                    continue
                state = "WAITING_BUILD" if outcome.build_required else "WAITING_ROUTE"
                self._update_client_mission(
                    mission_id,
                    state=state,
                    last_reason=outcome.reason or "NO_QUALIFIED_ROUTE",
                    next_retry_epoch=now_epoch + self.policy.retry_delay_seconds,
                )
                return {
                    "state": state,
                    "build_required": outcome.build_required,
                    "build_packet": dict(outcome.build_packet),
                    "resume_packet": self.resume_packet(mission_id, reason=state),
                }

            verified = False
            for route in routes:
                result = await self._execute_once(
                    mission_id=mission_id,
                    transition_id=transition_id,
                    route=route,
                    binding=binding,
                    adapter=adapter,
                    gateway_request=gateway_request,
                    identity_claims=identity_claims,
                    worker=worker,
                    now_epoch=now_epoch,
                    authority_lease_resolver=authority_lease_resolver,
                )
                if result["state"] == "VERIFIED_STEP":
                    verified = True
                    break
                if result["state"] == "RETRY_CHANGED_ROUTE" and self.policy.auto_retry:
                    continue
                return {**result, "resume_packet": self.resume_packet(mission_id, reason=result["state"])}
            if verified:
                continue

            outcome = await self._apply_harvest(
                harvester,
                mission_id=mission_id,
                transition_id=transition_id,
                objective=mission["objective"],
                reason="QUALIFIED_ROUTES_EXHAUSTED",
            )
            state = "WAITING_BUILD" if outcome.build_required else "WAITING_ROUTE"
            self._update_client_mission(
                mission_id,
                state=state,
                last_reason=outcome.reason or "QUALIFIED_ROUTES_EXHAUSTED",
                next_retry_epoch=now_epoch + self.policy.retry_delay_seconds,
            )
            return {
                "state": state,
                "build_required": outcome.build_required,
                "build_packet": dict(outcome.build_packet),
                "resume_packet": self.resume_packet(mission_id, reason=state),
            }

        self._update_client_mission(
            mission_id,
            state="RETRY_SCHEDULED",
            last_reason="WAKE_STEP_BUDGET_EXHAUSTED",
            next_retry_epoch=now_epoch + self.policy.retry_delay_seconds,
        )
        return {
            "state": "RETRY_SCHEDULED",
            "resume_packet": self.resume_packet(mission_id, reason="RETRY_SCHEDULED"),
        }

    def resume_packet(self, mission_id: str, *, reason: str) -> dict[str, Any]:
        client = self._get("sol62.client.mission", mission_id)
        if not client:
            raise KeyError(mission_id)
        return {
            "schema": "SOL62_CLIENT_RESUME_PACKET_V1",
            "task_type": "SOL62_CLIENT_WAKE",
            "mission_id": mission_id,
            "reason": reason,
            "next_retry_epoch": int(client["value"].get("next_retry_epoch", 0)),
            "goal_mutation_allowed": False,
            "retry_requires_state_readback": True,
            "completion_predicate": "SOL62_VERIFIED_REALITY",
            "orchestration_plane": self.sovereign_plane.contract.plane_id,
            "estate_resolution_service": self.sovereign_plane.contract.estate_resolution_service,
            "route_portfolio_policy": self.sovereign_plane.contract.route_portfolio_policy,
            "truth_root": "SOL_6_2",
            "resident_executor": self.sovereign_plane.contract.resident_executor,
        }
