from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

try:
    from .sol_62_frontier_primitives import ConstraintError, FenceError, digest
    from .sol_62_runtime import Sol62Runtime
except ImportError:
    from sol_62_frontier_primitives import ConstraintError, FenceError, digest
    from sol_62_runtime import Sol62Runtime


FDOF_VERSION = "1.0.0"
AUTHORITY_ORDER = {
    "A0_READ_ONLY": 0,
    "A1_INTERNAL": 1,
    "A2_BOUNDED_PROVIDER": 2,
    "A3_CONSEQUENTIAL": 3,
}
COST_ORDER = {
    "C0_INCLUDED_FREE": 0,
    "C1_MICRO_SERVERLESS": 1,
    "C2_CONTROLLED_PAID": 2,
    "C3_EXPENSIVE_COMPUTE": 3,
}
HEALTH_VALUES = {"HEALTHY", "DEGRADED", "FAILED", "UNKNOWN", "NOT_APPLICABLE"}
PROVIDER_STATES = {"AVAILABLE", "DEGRADED", "DOWN", "QUARANTINED", "UNKNOWN"}


@dataclass(frozen=True)
class ExecutorSpec:
    executor_id: str
    provider: str
    capabilities: tuple[str, ...]
    target_prefixes: tuple[str, ...]
    authority_ceiling: str = "A1_INTERNAL"
    cost_class: str = "C0_INCLUDED_FREE"
    readback_modes: tuple[str, ...] = ()
    rollback_modes: tuple[str, ...] = ()
    max_parallel: int = 1
    version: int = 1
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HealthObservation:
    observation_id: str
    executor_id: str
    observed_at_epoch: int
    ttl_seconds: int
    process: str
    authentication: str
    target_access: str
    semantic_capability: str
    readback: str
    capacity_available: int
    provider_state: str = "AVAILABLE"
    proof_id: str = ""
    evidence_class: str = "DETERMINISTIC"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteRequest:
    route_id: str
    mission_id: str
    transition_id: str
    operation: str
    target: str
    required_capabilities: tuple[str, ...]
    authority_ceiling: str = "A1_INTERNAL"
    allowed_cost_classes: tuple[str, ...] = ("C0_INCLUDED_FREE",)
    require_readback: bool = True
    require_rollback: bool = False
    consequential: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FactClaim:
    claim_id: str
    subject: str
    dimension: str
    value: Any
    source_kind: str
    observed_at_epoch: int
    source_version: str
    target: str = ""
    proof_id: str = ""
    confidence: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


class FederationDistributedOperatingFabric:
    """Provider-neutral Federation coordination layer over SOL 6.2.

    This class deliberately does not create provider authority. It registers
    executor contracts, consumes fresh health/readback evidence, routes work,
    preserves competing claims, and delegates mission/effect/lease/proof
    mechanics to the existing SOL 6.2 runtime.
    """

    def __init__(self, runtime: Sol62Runtime) -> None:
        self.runtime = runtime
        self.control = runtime.control
        self._register_schemas()

    def _register_schemas(self) -> None:
        self.control.register_schema(
            "fdof.executor",
            1,
            {
                "required": [
                    "executor_id",
                    "provider",
                    "capabilities",
                    "target_prefixes",
                    "authority_ceiling",
                    "cost_class",
                    "version",
                ],
                "authority_inheritance": False,
                "runtime_inheritance": False,
            },
        )
        self.control.register_schema(
            "fdof.health",
            1,
            {
                "required": [
                    "observation_id",
                    "executor_id",
                    "observed_at_epoch",
                    "ttl_seconds",
                    "process",
                    "authentication",
                    "target_access",
                    "semantic_capability",
                    "readback",
                    "capacity_available",
                ],
                "freshness_required": True,
            },
        )
        self.control.register_schema(
            "fdof.claim",
            1,
            {
                "required": [
                    "claim_id",
                    "subject",
                    "dimension",
                    "value",
                    "source_kind",
                    "observed_at_epoch",
                    "source_version",
                ],
                "last_write_wins": False,
                "dimension_specific_resolution": True,
            },
        )
        self.control.register_schema(
            "fdof.route_decision",
            1,
            {
                "required": ["route_id", "executor_id", "score", "health_state"],
                "fresh_health_required": True,
                "proof_or_authority_not_inherited": True,
            },
        )

    @staticmethod
    def _put_or_revise(
        control: Any,
        namespace: str,
        key: str,
        body: Mapping[str, Any],
        *,
        semantic_version: int,
    ) -> dict[str, Any]:
        current = control.get_state(namespace, key)
        candidate = dict(body)
        if current is None:
            version = control.cas_put(namespace, key, candidate, expected_version=0)
            return {"value": candidate, "version": version}
        if digest(current["value"]) == digest(candidate):
            return current
        prior_semantic = int(current["value"].get("version", 1))
        if int(semantic_version) <= prior_semantic:
            raise ConstraintError("REVISION_REQUIRES_HIGHER_SEMANTIC_VERSION")
        version = control.cas_put(
            namespace,
            key,
            candidate,
            expected_version=int(current["version"]),
        )
        return {"value": candidate, "version": version}

    def register_executor(self, spec: ExecutorSpec) -> dict[str, Any]:
        if not spec.executor_id or not spec.provider:
            raise ConstraintError("EXECUTOR_ID_AND_PROVIDER_REQUIRED")
        if not spec.capabilities or not spec.target_prefixes:
            raise ConstraintError("EXECUTOR_CAPABILITY_AND_TARGET_REQUIRED")
        if spec.authority_ceiling not in AUTHORITY_ORDER:
            raise ConstraintError("INVALID_AUTHORITY_CEILING")
        if spec.cost_class not in COST_ORDER:
            raise ConstraintError("INVALID_COST_CLASS")
        if spec.max_parallel < 1:
            raise ConstraintError("INVALID_EXECUTOR_CAPACITY")
        if spec.version < 1:
            raise ConstraintError("INVALID_EXECUTOR_VERSION")
        body = dataclasses.asdict(spec)
        stored = self._put_or_revise(
            self.control,
            "fdof.executor",
            spec.executor_id,
            body,
            semantic_version=spec.version,
        )
        self.control.append_event(spec.executor_id, "FDOF_EXECUTOR_REGISTERED", body)
        return stored

    def record_health(self, observation: HealthObservation) -> dict[str, Any]:
        if not self.control.get_state("fdof.executor", observation.executor_id):
            raise ConstraintError("EXECUTOR_NOT_REGISTERED")
        if observation.ttl_seconds < 1:
            raise ConstraintError("HEALTH_TTL_INVALID")
        if observation.capacity_available < 0:
            raise ConstraintError("CAPACITY_INVALID")
        dimensions = (
            observation.process,
            observation.authentication,
            observation.target_access,
            observation.semantic_capability,
            observation.readback,
        )
        if any(value not in HEALTH_VALUES for value in dimensions):
            raise ConstraintError("INVALID_HEALTH_DIMENSION")
        if observation.provider_state not in PROVIDER_STATES:
            raise ConstraintError("INVALID_PROVIDER_STATE")
        body = dataclasses.asdict(observation)
        current = self.control.get_state("fdof.executor_health", observation.executor_id)
        if current is not None:
            prior = int(current["value"]["observed_at_epoch"])
            if int(observation.observed_at_epoch) < prior:
                raise ConstraintError("HEALTH_OBSERVATION_TIME_REGRESSION")
            version = self.control.cas_put(
                "fdof.executor_health",
                observation.executor_id,
                body,
                expected_version=int(current["version"]),
            )
        else:
            version = self.control.cas_put(
                "fdof.executor_health", observation.executor_id, body, expected_version=0
            )
        self.control.append_event(
            observation.executor_id,
            "FDOF_HEALTH_OBSERVED",
            {
                "observation_id": observation.observation_id,
                "observed_at_epoch": observation.observed_at_epoch,
                "proof_id": observation.proof_id,
                "evidence_class": observation.evidence_class,
            },
        )
        return {"value": body, "version": version}

    def health_state(self, executor_id: str, *, now_epoch: int | None = None) -> dict[str, Any]:
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        executor = self.control.get_state("fdof.executor", executor_id)
        if executor is None:
            raise KeyError(executor_id)
        health = self.control.get_state("fdof.executor_health", executor_id)
        if health is None:
            return {"executor_id": executor_id, "state": "UNKNOWN", "reasons": ["NO_HEALTH_OBSERVATION"]}
        value = health["value"]
        reasons: list[str] = []
        age = now_epoch - int(value["observed_at_epoch"])
        if age < -300:
            reasons.append("HEALTH_FROM_FUTURE")
        if age > int(value["ttl_seconds"]):
            return {"executor_id": executor_id, "state": "STALE", "age_seconds": age, "reasons": ["HEALTH_TTL_EXPIRED"]}
        if value["provider_state"] == "QUARANTINED":
            return {"executor_id": executor_id, "state": "QUARANTINED", "age_seconds": age, "reasons": ["PROVIDER_QUARANTINED"]}
        if value["provider_state"] == "DOWN" or value["process"] == "FAILED":
            return {"executor_id": executor_id, "state": "DOWN", "age_seconds": age, "reasons": ["PROCESS_OR_PROVIDER_DOWN"]}
        if value["authentication"] == "FAILED":
            return {"executor_id": executor_id, "state": "AUTHORITY_LOST", "age_seconds": age, "reasons": ["AUTHENTICATION_FAILED"]}
        required = [
            value["process"],
            value["authentication"],
            value["target_access"],
            value["semantic_capability"],
            value["readback"],
        ]
        if value["capacity_available"] <= 0:
            reasons.append("NO_CAPACITY")
        if any(item in {"FAILED", "UNKNOWN"} for item in required):
            reasons.append("REQUIRED_DIMENSION_NOT_HEALTHY")
        if any(item == "DEGRADED" for item in required) or value["provider_state"] == "DEGRADED":
            reasons.append("DEGRADED_DIMENSION")
        if reasons:
            return {"executor_id": executor_id, "state": "DEGRADED", "age_seconds": age, "reasons": reasons}
        return {"executor_id": executor_id, "state": "HEALTHY", "age_seconds": age, "reasons": []}

    @staticmethod
    def _target_matches(target: str, prefixes: Sequence[str]) -> bool:
        return any(target.startswith(prefix) for prefix in prefixes)

    def _route_score(self, executor: Mapping[str, Any], health: Mapping[str, Any], request: RouteRequest) -> int:
        score = 0
        if health["state"] == "HEALTHY":
            score += 100
        elif health["state"] == "DEGRADED":
            score += 40
        if executor["cost_class"] == "C0_INCLUDED_FREE":
            score += 30
        elif executor["cost_class"] == "C1_MICRO_SERVERLESS":
            score += 15
        if request.require_readback and executor.get("readback_modes"):
            score += 20
        if request.require_rollback and executor.get("rollback_modes"):
            score += 20
        score += min(20, max((len(prefix) for prefix in executor["target_prefixes"] if request.target.startswith(prefix)), default=0))
        score += min(20, 5 * len(set(request.required_capabilities) & set(executor["capabilities"])))
        return score

    def route(self, request: RouteRequest, *, now_epoch: int | None = None) -> dict[str, Any]:
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        if request.authority_ceiling not in AUTHORITY_ORDER:
            raise ConstraintError("INVALID_REQUEST_AUTHORITY_CEILING")
        if not request.allowed_cost_classes:
            raise ConstraintError("NO_ALLOWED_COST_CLASS")
        if any(cost not in COST_ORDER for cost in request.allowed_cost_classes):
            raise ConstraintError("INVALID_ALLOWED_COST_CLASS")
        candidates: list[dict[str, Any]] = []
        rows = self.control.db.execute(
            "SELECT item_key,value_json FROM state WHERE namespace='fdof.executor' ORDER BY item_key"
        ).fetchall()
        import json

        for row in rows:
            executor = json.loads(row["value_json"])
            if not set(request.required_capabilities) <= set(executor["capabilities"]):
                continue
            if not self._target_matches(request.target, executor["target_prefixes"]):
                continue
            if AUTHORITY_ORDER[executor["authority_ceiling"]] < AUTHORITY_ORDER[request.authority_ceiling]:
                continue
            if executor["cost_class"] not in set(request.allowed_cost_classes):
                continue
            if request.require_readback and not executor.get("readback_modes"):
                continue
            if (request.require_rollback or request.consequential) and not executor.get("rollback_modes"):
                continue
            health = self.health_state(executor["executor_id"], now_epoch=now_epoch)
            if health["state"] != "HEALTHY":
                continue
            score = self._route_score(executor, health, request)
            candidates.append({"executor": executor, "health": health, "score": score})
        candidates.sort(key=lambda item: (-item["score"], item["executor"]["executor_id"]))
        if not candidates:
            raise ConstraintError("NO_VERIFIED_EXECUTOR_ROUTE")
        winner = candidates[0]
        decision = {
            "route_id": request.route_id,
            "mission_id": request.mission_id,
            "transition_id": request.transition_id,
            "operation": request.operation,
            "target": request.target,
            "executor_id": winner["executor"]["executor_id"],
            "provider": winner["executor"]["provider"],
            "score": winner["score"],
            "health_state": winner["health"]["state"],
            "candidate_count": len(candidates),
            "request_sha256": digest(dataclasses.asdict(request)),
        }
        current = self.control.get_state("fdof.route_decision", request.route_id)
        if current is None:
            version = self.control.cas_put("fdof.route_decision", request.route_id, decision, expected_version=0)
        elif digest(current["value"]) == digest(decision):
            version = int(current["version"])
        else:
            raise FenceError("ROUTE_DECISION_ALREADY_BOUND")
        self.control.append_event(request.mission_id, "FDOF_ROUTE_SELECTED", decision)
        return {**decision, "version": version}

    def acquire_transition_lease(
        self,
        transition_id: str,
        executor_id: str,
        *,
        ttl_seconds: int,
        now_epoch: int,
    ) -> dict[str, Any]:
        if self.health_state(executor_id, now_epoch=now_epoch)["state"] != "HEALTHY":
            raise ConstraintError("EXECUTOR_NOT_HEALTHY_AT_LEASE_TIME")
        return self.runtime.acquire_execution_fence(
            transition_id, executor_id, ttl_seconds=ttl_seconds, now_epoch=now_epoch
        )

    def record_claim(self, claim: FactClaim) -> dict[str, Any]:
        if not claim.claim_id or not claim.subject or not claim.dimension:
            raise ConstraintError("CLAIM_ID_SUBJECT_DIMENSION_REQUIRED")
        if not 0.0 <= float(claim.confidence) <= 1.0:
            raise ConstraintError("CLAIM_CONFIDENCE_OUT_OF_RANGE")
        body = dataclasses.asdict(claim)
        current = self.control.get_state("fdof.claim", claim.claim_id)
        if current is not None:
            if digest(current["value"]) != digest(body):
                raise ConstraintError("CLAIM_ID_COLLISION")
            return current
        version = self.control.cas_put("fdof.claim", claim.claim_id, body, expected_version=0)
        self.control.append_event(claim.subject, "FDOF_FACT_CLAIM_RECORDED", {"claim_id": claim.claim_id, "dimension": claim.dimension})
        return {"value": body, "version": version}

    @staticmethod
    def _claim_precedence(dimension: str, source_kind: str) -> int:
        runtime_dimensions = {
            "runtime",
            "deployment",
            "health",
            "effect",
            "readback",
            "provider_authority",
        }
        governance_dimensions = {
            "owner_intent",
            "governance",
            "generation_anchor",
            "reserved_authority",
        }
        source_dimensions = {"source", "implementation", "configuration"}
        if dimension in runtime_dimensions:
            order = {
                "PROVIDER_NATIVE": 100,
                "INDEPENDENT_READBACK": 95,
                "HOSTED_RUNTIME": 80,
                "DETERMINISTIC_TEST": 60,
                "SOURCE": 40,
                "POLICY": 30,
                "OWNER_DIRECTIVE": 20,
                "HISTORICAL": 10,
            }
        elif dimension in governance_dimensions:
            order = {
                "OWNER_DIRECTIVE": 100,
                "POLICY": 90,
                "INDEPENDENT_READBACK": 70,
                "PROVIDER_NATIVE": 60,
                "SOURCE": 50,
                "HOSTED_RUNTIME": 40,
                "DETERMINISTIC_TEST": 30,
                "HISTORICAL": 10,
            }
        elif dimension in source_dimensions:
            order = {
                "SIGNED_SOURCE": 100,
                "SOURCE": 90,
                "INDEPENDENT_READBACK": 70,
                "PROVIDER_NATIVE": 60,
                "HOSTED_RUNTIME": 50,
                "POLICY": 40,
                "OWNER_DIRECTIVE": 30,
                "HISTORICAL": 10,
            }
        else:
            order = {
                "INDEPENDENT_READBACK": 90,
                "PROVIDER_NATIVE": 90,
                "SIGNED_SOURCE": 80,
                "HOSTED_RUNTIME": 70,
                "DETERMINISTIC_TEST": 60,
                "POLICY": 50,
                "OWNER_DIRECTIVE": 50,
                "SOURCE": 40,
                "HISTORICAL": 10,
            }
        return order.get(source_kind, 0)

    def resolve_claims(
        self,
        subject: str,
        dimension: str,
        *,
        now_epoch: int | None = None,
        max_age_seconds: int | None = None,
    ) -> dict[str, Any]:
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        import json

        rows = self.control.db.execute(
            "SELECT item_key,value_json FROM state WHERE namespace='fdof.claim' ORDER BY item_key"
        ).fetchall()
        candidates: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        for row in rows:
            claim = json.loads(row["value_json"])
            if claim["subject"] != subject or claim["dimension"] != dimension:
                continue
            age = now_epoch - int(claim["observed_at_epoch"])
            if max_age_seconds is not None and age > int(max_age_seconds):
                excluded.append({"claim_id": claim["claim_id"], "reason": "STALE", "age_seconds": age})
                continue
            if age < -300:
                excluded.append({"claim_id": claim["claim_id"], "reason": "FROM_FUTURE", "age_seconds": age})
                continue
            precedence = self._claim_precedence(dimension, claim["source_kind"])
            candidates.append({
                "claim": claim,
                "precedence": precedence,
                "age_seconds": age,
            })
        if not candidates:
            return {"resolved": False, "subject": subject, "dimension": dimension, "winner": None, "contenders": [], "excluded": excluded}
        candidates.sort(
            key=lambda item: (
                -item["precedence"],
                -float(item["claim"].get("confidence", 1.0)),
                -int(item["claim"]["observed_at_epoch"]),
                item["claim"]["claim_id"],
            )
        )
        winner = candidates[0]
        result = {
            "resolved": True,
            "subject": subject,
            "dimension": dimension,
            "winner": winner["claim"],
            "winner_precedence": winner["precedence"],
            "contenders": [item["claim"] for item in candidates[1:]],
            "excluded": excluded,
        }
        result["resolution_sha256"] = digest(result)
        return result

    def status(self, *, now_epoch: int | None = None) -> dict[str, Any]:
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        import json

        executors = []
        for row in self.control.db.execute(
            "SELECT item_key,value_json FROM state WHERE namespace='fdof.executor' ORDER BY item_key"
        ).fetchall():
            spec = json.loads(row["value_json"])
            health = self.health_state(spec["executor_id"], now_epoch=now_epoch)
            executors.append({
                "executor_id": spec["executor_id"],
                "provider": spec["provider"],
                "health": health["state"],
                "authority_ceiling": spec["authority_ceiling"],
                "cost_class": spec["cost_class"],
            })
        return {
            "fdof_version": FDOF_VERSION,
            "sol62_integrity": self.runtime.verify_integrity(),
            "executors": executors,
            "healthy_executors": sum(1 for item in executors if item["health"] == "HEALTHY"),
            "proof_boundary": "SOURCE_AND_DETERMINISTIC_RUNTIME_ONLY_UNTIL_PROVIDER_NATIVE_EXECUTOR_READBACK_EXISTS",
        }
