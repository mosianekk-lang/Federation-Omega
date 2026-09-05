from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


_ALLOWED_COSTS = {"ZERO", "INCLUDED", "UNKNOWN", "PAID"}
_AUTONOMOUS_COSTS = {"ZERO", "INCLUDED"}
_ALLOWED_NODE_CLASSES = {"SOVEREIGN_SYNTHESIS", "DOMAIN_CELL", "SUBCELL"}
_ALLOWED_HEALTH = {"HEALTHY", "DEGRADED", "UNHEALTHY", "UNKNOWN"}
_ALLOWED_MATURITY = {"LOGICAL", "SHADOW_VALIDATED", "CANARY_VERIFIED", "OPERATIONAL_NODE", "HELD"}
_HARD_EVD_HOLDS = {
    "HOLD_ARCHITECTURE_EXPANSION",
    "HOLD_CRITICAL_REGRESSION",
    "HOLD_STALE_PROOF",
    "HOLD_UNKNOWN_MATERIAL_COST",
}


@dataclass(frozen=True)
class MeshNodeProfile:
    node_id: str
    node_class: str
    parent_node: str
    domain_tags: tuple[str, ...]
    failure_domain: str
    shard_key: str
    authority_ceiling: str
    source_current: bool = True
    health: str = "HEALTHY"
    maturity: str = "LOGICAL"
    cost_class: str = "INCLUDED"
    existing_authority: bool = True
    external_state: bool = True
    async_operation: bool = True
    independent_readback_available: bool = True
    local_observation_without_sovereign: bool = True
    runtime_proven: bool = False
    reversible: bool = True
    raw_secret_required: bool = False
    iam_change_required: bool = False
    consequential_effect_required: bool = False
    external_effect_required: bool = False
    owner_burden_score: float = 0.0
    reliability_score: float = 0.5
    value_score: float = 0.5
    information_gain_score: float = 0.5

    def validate(self) -> None:
        for name, value in (
            ("node_id", self.node_id),
            ("node_class", self.node_class),
            ("parent_node", self.parent_node),
            ("failure_domain", self.failure_domain),
            ("shard_key", self.shard_key),
            ("authority_ceiling", self.authority_ceiling),
        ):
            if not value:
                raise ValueError(f"{name} is required")
        if self.node_class not in _ALLOWED_NODE_CLASSES:
            raise ValueError("unknown node_class")
        if self.health not in _ALLOWED_HEALTH:
            raise ValueError("unknown health state")
        if self.maturity not in _ALLOWED_MATURITY:
            raise ValueError("unknown maturity state")
        if self.cost_class not in _ALLOWED_COSTS:
            raise ValueError("unknown cost class")
        for name, value in (
            ("owner_burden_score", self.owner_burden_score),
            ("reliability_score", self.reliability_score),
            ("value_score", self.value_score),
            ("information_gain_score", self.information_gain_score),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class MeshObjective:
    objective_id: str
    required_tags: tuple[str, ...]
    state_token: str
    require_runtime: bool = False
    provider_action_required: bool = False
    consequential_effect: bool = False
    iam_or_secret_change: bool = False
    external_effect: bool = False
    cost_class: str = "INCLUDED"
    preferred_failure_domain: str = ""
    excluded_node_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.objective_id:
            raise ValueError("objective_id is required")
        if not self.state_token:
            raise ValueError("state_token is required")
        if self.cost_class not in _ALLOWED_COSTS:
            raise ValueError("unknown objective cost class")


@dataclass(frozen=True)
class MeshRouteDecision:
    objective_id: str
    state_token: str
    selected_node_id: str
    eligible_node_ids: tuple[str, ...]
    excluded_node_ids: tuple[str, ...]
    status: str
    reason: str
    autonomous: bool
    owner_trigger_required: bool
    continue_unaffected_nodes: bool
    sovereign_required: bool
    preserves_state: bool
    authorizes_authority_inheritance: bool = False


@dataclass(frozen=True)
class NodeAutoscaleSignal:
    signal_id: str
    node_id: str
    pressure: float
    complexity: float
    change_rate: float
    opportunity_pressure: float
    information_gain: float
    value_density: float
    distinct_subdomains: int = 1
    duplicate_overlap: float = 0.0
    source_current: bool = True
    health: str = "HEALTHY"
    cost_class: str = "INCLUDED"
    existing_authority: bool = True
    reversible: bool = True
    independent_readback_available: bool = True
    external_state: bool = True
    consequential: bool = False
    iam_or_secret_change: bool = False
    destructive_change: bool = False
    external_effect: bool = False
    evd_verdict: str = "VALUE_DENSITY_STABLE_OR_IMPROVING"

    def validate(self) -> None:
        if not self.signal_id or not self.node_id:
            raise ValueError("signal_id and node_id are required")
        for name, value in (
            ("pressure", self.pressure),
            ("complexity", self.complexity),
            ("change_rate", self.change_rate),
            ("opportunity_pressure", self.opportunity_pressure),
            ("information_gain", self.information_gain),
            ("value_density", self.value_density),
            ("duplicate_overlap", self.duplicate_overlap),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.distinct_subdomains < 1:
            raise ValueError("distinct_subdomains must be positive")
        if self.cost_class not in _ALLOWED_COSTS:
            raise ValueError("unknown cost class")
        if self.health not in _ALLOWED_HEALTH:
            raise ValueError("unknown health state")


@dataclass(frozen=True)
class NodeAutoscaleDecision:
    signal_id: str
    node_id: str
    action: str
    target_maturity: str
    status: str
    reason: str
    autonomous: bool
    owner_trigger_required: bool
    continue_unaffected_nodes: bool
    preserves_history: bool = True
    authorizes_provider_resource_creation: bool = False
    authorizes_destructive_retirement: bool = False
    authorizes_authority_expansion: bool = False


def node_conformance_state(node: MeshNodeProfile) -> str:
    """Apply the thin constitutional gate that every CFBE cell must satisfy."""
    node.validate()
    if not node.source_current:
        return "HOLD_STALE_NODE_STATE"
    if not node.external_state:
        return "HOLD_EXTERNAL_STATE_REQUIRED"
    if not node.async_operation:
        return "HOLD_ASYNC_OPERATION_REQUIRED"
    if node.raw_secret_required:
        return "HOLD_RAW_SECRET_PROHIBITED"
    if node.iam_change_required or node.consequential_effect_required or node.external_effect_required:
        return "HOLD_AUTHORITY_BOUNDARY"
    if node.cost_class not in _AUTONOMOUS_COSTS:
        return "HOLD_COST_BOUNDARY"
    if not node.existing_authority:
        return "HOLD_EXISTING_AUTHORITY_REQUIRED"
    if not node.reversible:
        return "HOLD_REVERSIBILITY_REQUIRED"
    if not node.independent_readback_available:
        return "HOLD_READBACK_REQUIRED"
    return "NODE_CONFORMANT"


def can_continue_local_observation(node: MeshNodeProfile, *, sovereign_available: bool) -> bool:
    """A healthy logical cell may continue local observation when synthesis is down."""
    node.validate()
    if sovereign_available:
        return node.health != "UNHEALTHY" and node.source_current
    return bool(
        node.local_observation_without_sovereign
        and node.external_state
        and node.async_operation
        and node.source_current
        and node.health in {"HEALTHY", "DEGRADED"}
    )


def route_mesh_objective(objective: MeshObjective, nodes: Iterable[MeshNodeProfile]) -> MeshRouteDecision:
    """Select the strongest admissible cell without making the sovereign core a runtime SPOF."""
    objective.validate()
    node_list = list(nodes)
    excluded = set(objective.excluded_node_ids)

    if objective.consequential_effect or objective.iam_or_secret_change or objective.external_effect:
        return _gated_route(objective, node_list, "objective crosses consequential, IAM/secret, or external-effect boundary")
    if objective.cost_class not in _AUTONOMOUS_COSTS:
        return _gated_route(objective, node_list, "objective incremental cost is paid or unknown")

    scored: list[tuple[float, str, MeshNodeProfile]] = []
    ineligible: list[str] = []
    required_tags = set(objective.required_tags)
    for node in node_list:
        node.validate()
        if node.node_id in excluded:
            ineligible.append(node.node_id)
            continue
        if node_conformance_state(node) != "NODE_CONFORMANT":
            ineligible.append(node.node_id)
            continue
        if node.health not in {"HEALTHY", "DEGRADED"}:
            ineligible.append(node.node_id)
            continue
        if objective.require_runtime and not node.runtime_proven:
            ineligible.append(node.node_id)
            continue
        node_tags = set(node.domain_tags)
        tag_matches = len(required_tags.intersection(node_tags))
        if required_tags and tag_matches == 0:
            ineligible.append(node.node_id)
            continue

        tag_score = 1.0 if not required_tags else tag_matches / len(required_tags)
        runtime_score = 1.0 if node.runtime_proven else 0.35
        health_score = 1.0 if node.health == "HEALTHY" else 0.65
        failure_diversity = 1.0 if objective.preferred_failure_domain and node.failure_domain != objective.preferred_failure_domain else 0.5
        score = (
            0.32 * tag_score
            + 0.18 * node.value_score
            + 0.15 * node.reliability_score
            + 0.10 * node.information_gain_score
            + 0.10 * health_score
            + 0.08 * runtime_score
            + 0.07 * failure_diversity
            - 0.08 * node.owner_burden_score
        )
        scored.append((score, node.node_id, node))

    scored.sort(key=lambda item: (-item[0], item[1]))
    if not scored:
        return MeshRouteDecision(
            objective_id=objective.objective_id,
            state_token=objective.state_token,
            selected_node_id="",
            eligible_node_ids=(),
            excluded_node_ids=tuple(sorted(set(ineligible).union(excluded))),
            status="NO_ADMISSIBLE_NODE",
            reason="no node satisfies capability, health, conformance, runtime, cost, and authority requirements",
            autonomous=True,
            owner_trigger_required=False,
            continue_unaffected_nodes=True,
            sovereign_required=False,
            preserves_state=True,
        )

    selected = scored[0][2]
    return MeshRouteDecision(
        objective_id=objective.objective_id,
        state_token=objective.state_token,
        selected_node_id=selected.node_id,
        eligible_node_ids=tuple(item[1] for item in scored),
        excluded_node_ids=tuple(sorted(set(ineligible).union(excluded))),
        status="NODE_SELECTED",
        reason="selected by bounded capability/value/reliability/readback/failure-domain ranking",
        autonomous=True,
        owner_trigger_required=False,
        continue_unaffected_nodes=True,
        sovereign_required=False,
        preserves_state=True,
    )


def mesh_resilience_state(nodes: Iterable[MeshNodeProfile], *, sovereign_available: bool) -> str:
    """Classify whether the mesh can still observe locally without claiming effect execution."""
    node_list = list(nodes)
    if not node_list:
        return "MESH_EMPTY"
    continuing = [node.node_id for node in node_list if can_continue_local_observation(node, sovereign_available=sovereign_available)]
    if sovereign_available and continuing:
        return "MESH_SYNTHESIS_AND_LOCAL_OBSERVATION_AVAILABLE"
    if not sovereign_available and continuing:
        return "MESH_LOCAL_CONTINUITY_WITH_SOVEREIGN_LOSS"
    return "MESH_OBSERVATION_UNAVAILABLE"


def decide_node_autoscale(signal: NodeAutoscaleSignal) -> NodeAutoscaleDecision:
    """Right-size logical CFBE cells without authorizing paid/provider/destructive actions."""
    signal.validate()
    if not signal.source_current:
        return _autoscale_hold(signal, "HOLD_STALE_PROOF", "node pressure/value evidence is stale")
    if signal.evd_verdict in _HARD_EVD_HOLDS:
        return _autoscale_hold(signal, signal.evd_verdict, "engineering value-density gate is holding mesh expansion")
    if signal.health == "UNHEALTHY":
        return NodeAutoscaleDecision(
            signal_id=signal.signal_id,
            node_id=signal.node_id,
            action="DEMOTE_AND_REROUTE",
            target_maturity="HELD",
            status="AUTONOMOUS_NONDESTRUCTIVE_DEMOTION",
            reason="node health is unhealthy; isolate failure and continue unaffected nodes",
            autonomous=True,
            owner_trigger_required=False,
            continue_unaffected_nodes=True,
        )
    if signal.consequential or signal.iam_or_secret_change or signal.destructive_change or signal.external_effect:
        return _autoscale_owner_gate(signal, "mesh change crosses consequential/authority/destructive/external boundary")
    if signal.cost_class not in _AUTONOMOUS_COSTS:
        return _autoscale_owner_gate(signal, "mesh change has paid or unknown incremental cost")
    if not signal.existing_authority:
        return _autoscale_owner_gate(signal, "mesh change lacks existing authority")
    if not signal.reversible:
        return _autoscale_owner_gate(signal, "mesh change is not reversibly bounded")
    if not signal.external_state:
        return _autoscale_hold(signal, "HOLD_EXTERNAL_STATE_REQUIRED", "node state must remain external before split/form/promotion")
    if not signal.independent_readback_available:
        return _autoscale_hold(signal, "HOLD_READBACK_REQUIRED", "independent readback is unavailable")

    high_pressure = max(signal.pressure, signal.complexity, signal.change_rate, signal.opportunity_pressure) >= 0.75
    high_value_signal = signal.information_gain >= 0.60 or signal.value_density >= 0.60
    if high_pressure and signal.distinct_subdomains >= 2 and high_value_signal:
        return NodeAutoscaleDecision(
            signal_id=signal.signal_id,
            node_id=signal.node_id,
            action="SPLIT_LOGICAL_CELL",
            target_maturity="SHADOW_VALIDATED",
            status="AUTONOMOUS_CONTROL_SPLIT_ADMISSIBLE",
            reason="sustained pressure plus separable subdomains and value/information signal justify bounded split",
            autonomous=True,
            owner_trigger_required=False,
            continue_unaffected_nodes=True,
        )

    if signal.duplicate_overlap >= 0.75 and signal.value_density < 0.45 and signal.pressure < 0.45:
        return NodeAutoscaleDecision(
            signal_id=signal.signal_id,
            node_id=signal.node_id,
            action="MERGE_OR_DEMOTE_LOGICAL_CELL",
            target_maturity="LOGICAL",
            status="AUTONOMOUS_NONDESTRUCTIVE_CONSOLIDATION_ADMISSIBLE",
            reason="high duplication with low pressure/value favors logical consolidation after equivalence proof",
            autonomous=True,
            owner_trigger_required=False,
            continue_unaffected_nodes=True,
        )

    if high_pressure and high_value_signal:
        return NodeAutoscaleDecision(
            signal_id=signal.signal_id,
            node_id=signal.node_id,
            action="BURST_LOCAL_CADENCE",
            target_maturity="LOGICAL",
            status="AUTONOMOUS_CADENCE_SCALE_ADMISSIBLE",
            reason="local pressure/information gain warrants bounded cadence burst without creating a new node",
            autonomous=True,
            owner_trigger_required=False,
            continue_unaffected_nodes=True,
        )

    if max(signal.pressure, signal.change_rate, signal.opportunity_pressure) < 0.20 and signal.information_gain < 0.20:
        return NodeAutoscaleDecision(
            signal_id=signal.signal_id,
            node_id=signal.node_id,
            action="THROTTLE_LOCAL_CADENCE",
            target_maturity="LOGICAL",
            status="AUTONOMOUS_CADENCE_SCALE_ADMISSIBLE",
            reason="quiet low-information node may throttle while freshness SLA is preserved",
            autonomous=True,
            owner_trigger_required=False,
            continue_unaffected_nodes=True,
        )

    return NodeAutoscaleDecision(
        signal_id=signal.signal_id,
        node_id=signal.node_id,
        action="NO_TOPOLOGY_CHANGE",
        target_maturity="LOGICAL",
        status="MESH_RIGHT_SIZED",
        reason="current pressure, information gain, value density and duplication do not justify topology change",
        autonomous=True,
        owner_trigger_required=False,
        continue_unaffected_nodes=True,
    )


def promotion_gate(node: MeshNodeProfile, *, shadow_passed: bool, canary_passed: bool, measured_value_positive: bool) -> str:
    """Node runtime maturity never inherits from source/control-plane presence."""
    node.validate()
    if node_conformance_state(node) != "NODE_CONFORMANT":
        return "PROMOTION_HELD_NONCONFORMANT"
    if not shadow_passed:
        return "LOGICAL"
    if not canary_passed:
        return "SHADOW_VALIDATED"
    if not node.runtime_proven:
        return "CANARY_VERIFIED"
    if not measured_value_positive:
        return "CANARY_VERIFIED_VALUE_PENDING"
    return "OPERATIONAL_NODE"


def _gated_route(objective: MeshObjective, nodes: list[MeshNodeProfile], reason: str) -> MeshRouteDecision:
    return MeshRouteDecision(
        objective_id=objective.objective_id,
        state_token=objective.state_token,
        selected_node_id="",
        eligible_node_ids=(),
        excluded_node_ids=tuple(sorted(node.node_id for node in nodes)),
        status="OWNER_OR_PROVIDER_TRIGGER_REQUIRED",
        reason=reason,
        autonomous=False,
        owner_trigger_required=True,
        continue_unaffected_nodes=True,
        sovereign_required=False,
        preserves_state=True,
    )


def _autoscale_hold(signal: NodeAutoscaleSignal, status: str, reason: str) -> NodeAutoscaleDecision:
    return NodeAutoscaleDecision(
        signal_id=signal.signal_id,
        node_id=signal.node_id,
        action="HOLD_AND_REEVALUATE",
        target_maturity="HELD",
        status=status,
        reason=reason,
        autonomous=True,
        owner_trigger_required=False,
        continue_unaffected_nodes=True,
    )


def _autoscale_owner_gate(signal: NodeAutoscaleSignal, reason: str) -> NodeAutoscaleDecision:
    return NodeAutoscaleDecision(
        signal_id=signal.signal_id,
        node_id=signal.node_id,
        action="OWNER_OR_PROVIDER_TRIGGER_REQUIRED",
        target_maturity="HELD",
        status="OWNER_TRIGGER_REQUIRED",
        reason=reason,
        autonomous=False,
        owner_trigger_required=True,
        continue_unaffected_nodes=True,
    )
