"""Additive CFBE Build Intelligence adapter for the existing FUSE proof spine.

This module is deliberately not a scheduler, executor, authority root, or proof
plane. It compiles a content-addressed estate graph into the already-admitted
WorkUnit, RouteProfile, and TopologyTask contracts. Execution and authority
remain with the existing AutonomicMissionSpine and its admission/readback courts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from federation.cfbe_chat_hyperperformance_v1 import EffectClass, RouteProfile, WorkUnit
from federation.execution_topology_compiler_v1 import TopologyTask

SCHEMA = "CFBE-BUILD-INTELLIGENCE-ADAPTER-V1"
VERSION = "0.1.1"
_SHA256_RE = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


def _sha256(value: str, *, field_name: str) -> str:
    match = _SHA256_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"{field_name}_SHA256_REQUIRED")
    return "sha256:" + match.group(1)


class EstateKind(str, Enum):
    REPOSITORY = "REPOSITORY"
    DEPENDENCY = "DEPENDENCY"
    TEST = "TEST"
    ARTIFACT = "ARTIFACT"
    DEPLOYMENT = "DEPLOYMENT"
    POLICY = "POLICY"


class ExecutorKind(str, Enum):
    LOCAL = "local"
    GITHUB = "github"
    REMOTE_CAS = "remote_cas"
    REMOTE_EXECUTION = "remote_execution"


@dataclass(frozen=True, slots=True)
class EstateNode:
    node_id: str
    kind: EstateKind
    locator: str
    content_sha256: str
    dependencies: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> "EstateNode":
        if not self.node_id.strip() or not self.locator.strip():
            raise ValueError("ESTATE_NODE_IDENTITY_REQUIRED")
        _sha256(self.content_sha256, field_name="ESTATE_CONTENT")
        if self.node_id in self.dependencies:
            raise ValueError("ESTATE_SELF_DEPENDENCY")
        return self


@dataclass(frozen=True, slots=True)
class EstateGraph:
    nodes: tuple[EstateNode, ...]
    source_epoch_sha256: str

    def validate(self) -> "EstateGraph":
        _sha256(self.source_epoch_sha256, field_name="SOURCE_EPOCH")
        by_id: dict[str, EstateNode] = {}
        for node in self.nodes:
            node.validate()
            if node.node_id in by_id:
                raise ValueError("DUPLICATE_ESTATE_NODE")
            by_id[node.node_id] = node
        for node in self.nodes:
            missing = sorted(set(node.dependencies) - set(by_id))
            if missing:
                raise ValueError("MISSING_ESTATE_DEPENDENCY:" + ",".join(missing))
        remaining = set(by_id)
        completed: set[str] = set()
        while remaining:
            ready = {item for item in remaining if set(by_id[item].dependencies) <= completed}
            if not ready:
                raise ValueError("CYCLIC_ESTATE_GRAPH")
            completed.update(ready)
            remaining.difference_update(ready)
        return self

    @property
    def graph_digest(self) -> str:
        self.validate()
        return _digest({
            "source_epoch": _sha256(self.source_epoch_sha256, field_name="SOURCE_EPOCH"),
            "nodes": [
                {
                    "node_id": n.node_id,
                    "kind": n.kind.value,
                    "locator": n.locator,
                    "content_sha256": _sha256(n.content_sha256, field_name="ESTATE_CONTENT"),
                    "dependencies": sorted(n.dependencies),
                    "metadata": dict(n.metadata),
                }
                for n in sorted(self.nodes, key=lambda item: item.node_id)
            ],
        })


@dataclass(frozen=True, slots=True)
class BuildAction:
    action_id: str
    estate_node_id: str
    operation: str
    command: tuple[str, ...]
    input_sha256: Mapping[str, str]
    dependencies: tuple[str, ...] = ()
    surface: str = "local"
    capability_id: str = "deterministic_build"
    effect_class: EffectClass = EffectClass.READ_ONLY
    mutation_domain: str = ""
    executor_kinds: tuple[ExecutorKind, ...] = (ExecutorKind.LOCAL,)
    outputs: tuple[str, ...] = ()
    estimated_ms: int = 1000
    priority: int = 50
    value_weight: float = 1.0
    privacy_class: str = "P1_INTERNAL"

    def validate(self) -> "BuildAction":
        if not all((self.action_id.strip(), self.estate_node_id.strip(), self.operation.strip(), self.command)):
            raise ValueError("BUILD_ACTION_IDENTITY_REQUIRED")
        if self.estimated_ms < 0:
            raise ValueError("BUILD_ACTION_ESTIMATE_INVALID")
        if not self.executor_kinds:
            raise ValueError("BUILD_ACTION_EXECUTOR_REQUIRED")
        try:
            surface_kind = ExecutorKind(self.surface)
        except ValueError as exc:
            raise ValueError("BUILD_ACTION_SURFACE_EXECUTOR_KIND_INVALID") from exc
        if surface_kind not in self.executor_kinds:
            raise ValueError("BUILD_ACTION_EXECUTOR_SURFACE_MISMATCH")
        if self.effect_class is not EffectClass.READ_ONLY and not self.mutation_domain.strip():
            raise ValueError("MUTATING_ACTION_REQUIRES_MUTATION_DOMAIN")
        for value in self.input_sha256.values():
            _sha256(value, field_name="BUILD_INPUT")
        return self

    @property
    def input_fingerprint(self) -> str:
        self.validate()
        return _digest({
            "estate_node_id": self.estate_node_id,
            "operation": self.operation,
            "command": self.command,
            "inputs": {key: _sha256(value, field_name="BUILD_INPUT") for key, value in sorted(self.input_sha256.items())},
            "outputs": self.outputs,
            "executors": [item.value for item in self.executor_kinds],
        })


@dataclass(frozen=True, slots=True)
class ExecutorBinding:
    binding_id: str
    kind: ExecutorKind
    surface: str
    observed_contract_sha256: str
    proof_refs: tuple[str, ...]
    available: bool
    fresh: bool
    direct: bool = True
    success_rate: float = 1.0
    semantic_readback_rate: float = 1.0
    p95_ms: int = 1000
    unit_cost: float = 0.0
    circuit_open: bool = False

    def to_route_profile(self) -> RouteProfile:
        if not self.binding_id.strip() or not self.surface.strip():
            raise ValueError("EXECUTOR_BINDING_IDENTITY_REQUIRED")
        _sha256(self.observed_contract_sha256, field_name="EXECUTOR_CONTRACT")
        if (self.available or self.fresh) and not self.proof_refs:
            raise ValueError("EXECUTOR_BINDING_PROOF_REQUIRED")
        route = RouteProfile(
            route_id=self.binding_id,
            surface=self.surface,
            available=self.available,
            fresh=self.fresh,
            direct=self.direct,
            success_rate=self.success_rate,
            semantic_readback_rate=self.semantic_readback_rate,
            p95_ms=self.p95_ms,
            unit_cost=self.unit_cost,
            circuit_open=self.circuit_open,
            proof_refs=self.proof_refs,
        )
        route.validate()
        return route


@dataclass(frozen=True, slots=True)
class CreativeFreedomEnvelope:
    invariants: frozenset[str] = frozenset()
    protected_paths: frozenset[str] = frozenset()
    defaults: Mapping[str, Any] = field(default_factory=dict)
    suggestions: Mapping[str, Any] = field(default_factory=dict)

    def validate_changes(
        self,
        changed_paths: Iterable[str],
        *,
        requested_overrides: Iterable[str] = (),
        owner_override_receipt_sha256: str = "",
    ) -> None:
        overrides = set(requested_overrides)
        invariant_attempts = self.invariants & overrides
        if invariant_attempts:
            raise PermissionError("INVARIANT_NOT_OVERRIDABLE:" + ",".join(sorted(invariant_attempts)))
        protected = (set(changed_paths) & self.protected_paths) - overrides
        if protected:
            raise PermissionError("PROTECTED_CREATIVE_PATH:" + ",".join(sorted(protected)))
        if overrides:
            _sha256(owner_override_receipt_sha256, field_name="OWNER_OVERRIDE_RECEIPT")


@dataclass(frozen=True, slots=True)
class BuildAdapterReceipt:
    source_epoch_sha256: str
    estate_graph_digest: str
    work_unit_ids: tuple[str, ...]
    work_unit_semantic_keys: tuple[str, ...]
    topology_task_count: int
    route_ids: tuple[str, ...]
    authority_granted: bool
    receipt_digest: str


class BuildIntelligenceAdapter:
    """Compile build intelligence into existing Federation execution contracts."""

    def compile(
        self,
        *,
        estate: EstateGraph,
        actions: Sequence[BuildAction],
        executor_bindings: Sequence[ExecutorBinding],
    ) -> tuple[tuple[WorkUnit, ...], tuple[TopologyTask, ...], tuple[RouteProfile, ...], BuildAdapterReceipt]:
        estate.validate()
        estate_ids = {node.node_id for node in estate.nodes}
        action_ids: set[str] = set()
        for action in actions:
            action.validate()
            if action.action_id in action_ids:
                raise ValueError("DUPLICATE_BUILD_ACTION")
            action_ids.add(action.action_id)
            if action.estate_node_id not in estate_ids:
                raise ValueError("ACTION_ESTATE_NODE_NOT_FOUND:" + action.estate_node_id)
        for action in actions:
            missing = sorted(set(action.dependencies) - action_ids)
            if missing:
                raise ValueError("MISSING_BUILD_ACTION_DEPENDENCY:" + ",".join(missing))
        by_action = {action.action_id: action for action in actions}
        remaining = set(by_action)
        completed: set[str] = set()
        while remaining:
            ready = {item for item in remaining if set(by_action[item].dependencies) <= completed}
            if not ready:
                raise ValueError("CYCLIC_BUILD_ACTION_GRAPH")
            completed.update(ready)
            remaining.difference_update(ready)

        units: list[WorkUnit] = []
        tasks: list[TopologyTask] = []
        for action in actions:
            unit = WorkUnit(
                unit_id=action.action_id,
                surface=action.surface,
                operation=action.operation,
                input_fingerprint=_digest({
                    "source_epoch": _sha256(estate.source_epoch_sha256, field_name="SOURCE_EPOCH"),
                    "estate_graph": estate.graph_digest,
                    "action": action.input_fingerprint,
                }),
                deps=action.dependencies,
                effect_class=action.effect_class,
                batch_key=action.estate_node_id,
                cacheable=action.effect_class is not EffectClass.EXTERNAL_EFFECT,
                freshness_key=estate.source_epoch_sha256,
                estimated_ms=action.estimated_ms,
                priority=action.priority,
                value_weight=action.value_weight,
                privacy_class=action.privacy_class,
                owner_only=False,
            )
            unit.validate()
            task = TopologyTask(unit=unit, capability_id=action.capability_id, mutation_domain=action.mutation_domain)
            task.validate()
            units.append(unit)
            tasks.append(task)

        routes = tuple(binding.to_route_profile() for binding in executor_bindings)
        if len({item.route_id for item in routes}) != len(routes):
            raise ValueError("DUPLICATE_EXECUTOR_BINDING")
        work_unit_material = [
            {
                "unit_id": item.unit_id,
                "surface": item.surface,
                "operation": item.operation,
                "input_fingerprint": item.input_fingerprint,
                "deps": list(item.deps),
                "effect_class": item.effect_class.value,
                "batch_key": item.batch_key,
                "cacheable": item.cacheable,
                "freshness_key": item.freshness_key,
                "estimated_ms": item.estimated_ms,
                "priority": item.priority,
                "value_weight": item.value_weight,
                "privacy_class": item.privacy_class,
                "owner_only": item.owner_only,
                "semantic_key": item.semantic_key,
            }
            for item in units
        ]
        topology_material = [
            {
                "unit_id": item.unit.unit_id,
                "capability_id": item.capability_id,
                "mutation_domain": item.mutation_domain,
            }
            for item in tasks
        ]
        route_material = [
            {
                "binding_id": binding.binding_id,
                "kind": binding.kind.value,
                "surface": binding.surface,
                "observed_contract_sha256": _sha256(
                    binding.observed_contract_sha256, field_name="EXECUTOR_CONTRACT"
                ),
                "proof_refs": list(binding.proof_refs),
                "available": binding.available,
                "fresh": binding.fresh,
                "direct": binding.direct,
                "success_rate": binding.success_rate,
                "semantic_readback_rate": binding.semantic_readback_rate,
                "p95_ms": binding.p95_ms,
                "unit_cost": binding.unit_cost,
                "circuit_open": binding.circuit_open,
            }
            for binding in executor_bindings
        ]
        receipt_material = {
            "schema": SCHEMA,
            "version": VERSION,
            "source_epoch": _sha256(estate.source_epoch_sha256, field_name="SOURCE_EPOCH"),
            "estate_graph": estate.graph_digest,
            "work_units": work_unit_material,
            "topology_tasks": topology_material,
            "executor_bindings": route_material,
            "authority_granted": False,
        }
        receipt = BuildAdapterReceipt(
            source_epoch_sha256=_sha256(estate.source_epoch_sha256, field_name="SOURCE_EPOCH"),
            estate_graph_digest=estate.graph_digest,
            work_unit_ids=tuple(item.unit_id for item in units),
            work_unit_semantic_keys=tuple(item.semantic_key for item in units),
            topology_task_count=len(tasks),
            route_ids=tuple(item.route_id for item in routes),
            authority_granted=False,
            receipt_digest=_digest(receipt_material),
        )
        return tuple(units), tuple(tasks), routes, receipt


__all__ = [
    "SCHEMA", "VERSION", "EstateKind", "ExecutorKind", "EstateNode", "EstateGraph",
    "BuildAction", "ExecutorBinding", "CreativeFreedomEnvelope", "BuildAdapterReceipt",
    "BuildIntelligenceAdapter",
]
