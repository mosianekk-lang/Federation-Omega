"""Governed, invocation-driven upgrade decisions for RealityGuard and adapters.

The engine is deliberately not a background daemon and never edits source code.
An integrated host invokes it at a material cycle boundary, then obtains and
consumes a separate Formation permit before any selected executor may patch.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .capability import CapabilityRegistry, canonical_json
from .prebuild import manifest_snapshot_hash
from .schema import InputError


class CycleKind(str, Enum):
    BUILD = "BUILD"
    FAILURE = "FAILURE"
    RECOVERY = "RECOVERY"
    DEPLOYMENT = "DEPLOYMENT"
    CANARY = "CANARY"


class UpgradeDecisionCode(str, Enum):
    NO_UPGRADE_REQUIRED = "NO_UPGRADE_REQUIRED"
    OBSERVE = "OBSERVE"
    PATCH_EXISTING = "PATCH_EXISTING"
    CREATE_CANDIDATE = "CREATE_CANDIDATE"
    BLOCK_DUPLICATE_UPGRADE = "BLOCK_DUPLICATE_UPGRADE"
    BLOCK_UNSAFE_UPGRADE = "BLOCK_UNSAFE_UPGRADE"


@dataclass(frozen=True)
class UpgradeDecision:
    schema_version: str
    decision_id: str
    decision: UpgradeDecisionCode
    cycle_id: str
    cycle_kind: CycleKind
    system_id: str
    automatic_assessment_invoked: bool
    invocation_mode: str
    existing_target_id: str
    selected_capability_ids: tuple[str, ...]
    capability_gaps: tuple[str, ...]
    preserved_capabilities: tuple[str, ...]
    capability_losses: tuple[str, ...]
    false_positive_risk: str
    environment_attested: bool
    environment_scope: str
    inventory_verified: bool
    inventory_manifest_hash: str
    correction_debt_invalidated: tuple[str, ...]
    correction_repair_order: tuple[str, ...]
    learning_fingerprint: str
    learning_state: str
    forward_test_required: bool
    formation_permit_required: bool
    automatic_execution_authorized: bool
    promotion_authorized: bool
    external_execution_claimed: bool
    authority_expansion: bool
    recurring_cost: float
    manual_user_tasks: tuple[str, ...]
    owner_action_required: bool
    reasons: tuple[str, ...]
    required_evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["decision"] = self.decision.value
        value["cycle_kind"] = self.cycle_kind.value
        for key in (
            "selected_capability_ids", "capability_gaps", "preserved_capabilities",
            "capability_losses", "correction_debt_invalidated", "correction_repair_order",
            "manual_user_tasks", "reasons", "required_evidence",
        ):
            value[key] = list(value[key])
        return value


def _strings(raw: Any, field: str, *, required: bool = False) -> tuple[str, ...]:
    if raw is None and not required:
        return ()
    if not isinstance(raw, list) or (required and not raw):
        raise InputError(f"{field} must be {'a non-empty' if required else 'an'} string array")
    if not all(isinstance(item, str) and item.strip() for item in raw):
        raise InputError(f"{field} must be {'a non-empty' if required else 'an'} string array")
    return tuple(sorted(set(item.strip() for item in raw)))


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{field} must be a non-empty string")
    return value.strip()


def _authority_rank(value: str) -> int:
    levels = {"A0": 0, "A1": 1, "A2": 2, "A3": 3, "A4": 4, "A5": 5}
    try:
        return levels[value.upper()]
    except KeyError as exc:
        raise InputError("candidate.authority_class and governance.maximum_authority must be A0-A5") from exc


def _correction_debt(
    dependencies: Any, changed_source_ids: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    if dependencies is None:
        dependencies = []
    if not isinstance(dependencies, list):
        raise InputError("dependencies must be an array")
    graph: dict[str, tuple[str, ...]] = {}
    for index, raw in enumerate(dependencies):
        if not isinstance(raw, dict):
            raise InputError(f"dependencies[{index}] must be an object")
        artifact_id = _required_text(raw, "artifact_id")
        if artifact_id in graph:
            raise InputError(f"duplicate dependency artifact_id: {artifact_id}")
        graph[artifact_id] = _strings(raw.get("depends_on", []), f"dependencies[{index}].depends_on")

    affected = set(changed_source_ids)
    levels: dict[str, int] = {item: 0 for item in changed_source_ids}
    changed = True
    while changed:
        changed = False
        for artifact_id, upstream in graph.items():
            parents = set(upstream).intersection(affected)
            if parents and artifact_id not in affected:
                affected.add(artifact_id)
                levels[artifact_id] = max(levels.get(parent, 0) for parent in parents) + 1
                changed = True

    dependents = affected - set(changed_source_ids)
    # A cycle inside the affected dependency closure cannot produce a safe order.
    indegree = {item: 0 for item in affected}
    children: dict[str, set[str]] = {item: set() for item in affected}
    for artifact_id in affected:
        for parent in graph.get(artifact_id, ()):
            if parent in affected:
                indegree[artifact_id] += 1
                children[parent].add(artifact_id)
    queue = sorted(item for item, degree in indegree.items() if degree == 0)
    ordered: list[str] = []
    while queue:
        current = queue.pop(0)
        ordered.append(current)
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
                queue.sort()
    cyclic = len(ordered) != len(affected)
    repair = tuple(item for item in ordered if item in dependents)
    return tuple(sorted(dependents)), repair, cyclic


class GovernedUpgradeEngine:
    """Select the smallest safe upgrade route at one material cycle boundary."""

    schema_version = "realityguard.upgrade.v1"
    invocation_mode = "HOST_INVOKED_AT_MATERIAL_CYCLE_BOUNDARY"

    def evaluate(self, payload: dict[str, Any], capability_manifest: dict[str, Any]) -> UpgradeDecision:
        if not isinstance(payload, dict):
            raise InputError("upgrade request must be an object")
        cycle = payload.get("cycle")
        environment = payload.get("environment")
        inventory = payload.get("inventory")
        candidate = payload.get("candidate")
        governance = payload.get("governance")
        if not all(isinstance(value, dict) for value in (cycle, environment, inventory, candidate, governance)):
            raise InputError("cycle, environment, inventory, candidate and governance must be objects")

        cycle_id = _required_text(cycle, "cycle_id")
        system_id = _required_text(cycle, "system_id")
        try:
            cycle_kind = CycleKind[_required_text(cycle, "kind").upper()]
        except KeyError as exc:
            raise InputError("cycle.kind must be BUILD, FAILURE, RECOVERY, DEPLOYMENT or CANARY") from exc
        claim = _required_text(cycle, "claim")
        observed_fruit = _required_text(cycle, "observed_fruit")
        desired_outcome = _required_text(cycle, "desired_outcome")
        metric = _required_text(cycle, "metric")
        changed_sources = _strings(cycle.get("changed_source_ids", []), "cycle.changed_source_ids")

        manifest_hash = manifest_snapshot_hash(capability_manifest)
        sources = _strings(inventory.get("sources", []), "inventory.sources")
        inventory_verified = all((
            inventory.get("enumerated") is True,
            inventory.get("inspected_to_end") is True,
            inventory.get("snapshot_current") is True,
            bool(sources),
            inventory.get("snapshot_hash") == manifest_hash,
        ))
        evidence_refs = _strings(environment.get("evidence_refs", []), "environment.evidence_refs")
        environment_id = _required_text(environment, "environment_id")
        environment_scope = _required_text(environment, "scope")
        environment_attested = all((
            environment.get("attested") is True,
            environment.get("current") is True,
            bool(evidence_refs),
        ))

        component_id = _required_text(candidate, "component_id")
        existing_target_id = str(candidate.get("existing_target_id", "")).strip()
        is_new = candidate.get("is_new_component") is True
        provides = _strings(candidate.get("provides"), "candidate.provides", required=True)
        preserves = _strings(candidate.get("preserve_capabilities"), "candidate.preserve_capabilities", required=True)
        removed = _strings(candidate.get("removed_capabilities", []), "candidate.removed_capabilities")
        regression_tests = _strings(candidate.get("regression_tests", []), "candidate.regression_tests")
        healthy_tests = _strings(candidate.get("healthy_case_tests", []), "candidate.healthy_case_tests")
        rollback = str(candidate.get("rollback", "")).strip()
        authority = _required_text(candidate, "authority_class").upper()
        maximum_authority = _required_text(governance, "maximum_authority").upper()
        recurring_cost = float(candidate.get("recurring_cost", 0))
        manual_tasks = _strings(candidate.get("manual_user_tasks", []), "candidate.manual_user_tasks")

        registry = CapabilityRegistry.from_dict(capability_manifest)
        selection = registry.select(
            tuple(sorted(set(provides).union(preserves))),
            available_authority=maximum_authority,
            allow_external_effects=governance.get("external_execution_authorized") is True,
            maximum_recurring_cost=float(governance.get("maximum_recurring_cost", 0)),
        )
        selected_ids = tuple(item.capability_id for item in selection.selected)
        target_exists = existing_target_id in {item.capability_id for item in registry.capabilities}
        target_selected = existing_target_id in selected_ids
        covered_after = set(selection.covered).union(provides)
        losses = tuple(sorted(set(preserves).intersection(removed).union(set(preserves) - covered_after)))

        invalidated, repair_order, correction_cycle = _correction_debt(
            payload.get("dependencies"), changed_sources
        )
        recurrence = int(cycle.get("recurrence_count", 1))
        severity = str(cycle.get("severity", "MEDIUM")).upper()
        contradiction = cycle.get("claim_fruit_contradiction") is True
        metric_breached = cycle.get("metric_breached") is True
        unsafe_route = cycle.get("unsafe_route_active") is True
        material = cycle.get("material") is True
        strong_trigger = severity in {"HIGH", "CRITICAL"} or recurrence >= 2 or contradiction or metric_breached

        reasons: list[str] = []
        required_evidence: tuple[str, ...] = ()
        decision = UpgradeDecisionCode.OBSERVE
        if not material:
            decision = UpgradeDecisionCode.NO_UPGRADE_REQUIRED
            reasons.append("The event is not marked material; no upgrade path is opened.")
        elif not inventory_verified or not environment_attested:
            reasons.append("Current finite inventory and target-environment attestation are required before upgrade routing.")
            required_evidence = ("current_inventory", "environment_attestation")
        elif any((
            _authority_rank(authority) > _authority_rank(maximum_authority),
            recurring_cost > float(governance.get("maximum_recurring_cost", 0)),
            bool(manual_tasks) and governance.get("manual_user_tasks_allowed") is not True,
            candidate.get("background_daemon") is True,
            candidate.get("foundation_model_modification") is True,
            candidate.get("external_effects") is True and governance.get("external_execution_authorized") is not True,
            bool(losses),
            correction_cycle,
        )):
            decision = UpgradeDecisionCode.BLOCK_UNSAFE_UPGRADE
            reasons.append("The candidate violates authority, cost, burden, environment, capability-preservation or correction-order controls.")
            if losses:
                reasons.append("Protected capabilities would be lost: " + ", ".join(losses))
            if correction_cycle:
                reasons.append("The affected dependency graph contains a cycle and has no safe repair order.")
        elif not strong_trigger:
            reasons.append("One bounded observation is insufficient for automatic patching; recurrence, severity, contradiction or a metric breach is required.")
        elif not regression_tests or not healthy_tests or not rollback:
            reasons.append("A patch route requires failure regression tests, healthy-case tests and rollback evidence.")
            required_evidence = ("original_failure_test", "healthy_case_test", "rollback")
        elif is_new and selection.covered and not selection.gaps:
            decision = UpgradeDecisionCode.BLOCK_DUPLICATE_UPGRADE
            reasons.append("Current capabilities already cover the proposed scope; creating a parallel component is blocked.")
        elif not is_new and target_exists and target_selected:
            decision = UpgradeDecisionCode.PATCH_EXISTING
            reasons.append("Patch the selected existing component within the evidenced scope and propagate correction debt before promotion.")
        elif is_new and selection.gaps and set(provides) == set(selection.gaps):
            decision = UpgradeDecisionCode.CREATE_CANDIDATE
            reasons.append("No current component covers the exact residual scope; a bounded candidate may enter the governed competency lifecycle.")
        elif not is_new and not target_exists:
            decision = UpgradeDecisionCode.BLOCK_UNSAFE_UPGRADE
            reasons.append("The requested existing target is absent from the current capability inventory.")
        else:
            decision = UpgradeDecisionCode.BLOCK_DUPLICATE_UPGRADE
            reasons.append("Reuse or compose the selected current capabilities; the proposed route is not the smallest valid change.")

        identity = {
            "cycle": cycle_id,
            "system": system_id,
            "environment": environment_id,
            "manifest": manifest_hash,
            "component": component_id,
            "decision": decision.value,
        }
        learning = {
            "claim": claim,
            "fruit": observed_fruit,
            "desired": desired_outcome,
            "metric": metric,
            "system": system_id,
            "failure": str(cycle.get("failure_code", "UNCLASSIFIED")),
        }
        actionable = decision in {UpgradeDecisionCode.PATCH_EXISTING, UpgradeDecisionCode.CREATE_CANDIDATE}
        return UpgradeDecision(
            schema_version=self.schema_version,
            decision_id="rgu-" + hashlib.sha256(canonical_json(identity).encode()).hexdigest()[:20],
            decision=decision,
            cycle_id=cycle_id,
            cycle_kind=cycle_kind,
            system_id=system_id,
            automatic_assessment_invoked=material,
            invocation_mode=self.invocation_mode,
            existing_target_id=existing_target_id,
            selected_capability_ids=selected_ids,
            capability_gaps=selection.gaps,
            preserved_capabilities=preserves,
            capability_losses=losses,
            false_positive_risk="BLOCKED" if decision == UpgradeDecisionCode.BLOCK_UNSAFE_UPGRADE else "CONTROLLED",
            environment_attested=environment_attested,
            environment_scope=environment_scope,
            inventory_verified=inventory_verified,
            inventory_manifest_hash=manifest_hash,
            correction_debt_invalidated=invalidated,
            correction_repair_order=repair_order,
            learning_fingerprint="rgl-" + hashlib.sha256(canonical_json(learning).encode()).hexdigest()[:20],
            learning_state="DESIGNED" if actionable else "DETECTED",
            forward_test_required=actionable,
            formation_permit_required=actionable,
            automatic_execution_authorized=False,
            promotion_authorized=False,
            external_execution_claimed=False,
            authority_expansion=False,
            recurring_cost=0,
            manual_user_tasks=(),
            owner_action_required=False,
            reasons=tuple(reasons),
            required_evidence=required_evidence,
        )
