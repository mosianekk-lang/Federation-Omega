"""Whole-directive execution without authority or safeguard bypass.

The controller treats a blocked route as local to one directive element. Other
independent elements remain schedulable. A run may only be declared complete
when every requested element is proven, explicitly inapplicable, or superseded
by a later user correction.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum


class ElementState(StrEnum):
    OPEN = "OPEN"
    EXECUTABLE = "EXECUTABLE"
    RUNNING = "RUNNING"
    PROVEN = "PROVEN"
    INAPPLICABLE = "INAPPLICABLE"
    BLOCKED_EXTERNAL_TRUST = "BLOCKED_EXTERNAL_TRUST"
    ROUTE_EXHAUSTED = "ROUTE_EXHAUSTED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


TERMINAL_COMPLETE_STATES = {
    ElementState.PROVEN,
    ElementState.INAPPLICABLE,
    ElementState.SUPERSEDED,
}


@dataclass(frozen=True)
class DirectiveElement:
    element_id: str
    description: str
    sequence: int
    dependencies: tuple[str, ...] = ()
    authority_class: str = "A0"
    external_effect: bool = False
    completion_criteria: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionRoute:
    route_id: str
    element_id: str
    authority_class: str
    available: bool = True
    safe: bool = True
    cost: float = 0.0
    user_burden: float = 0.0
    prerequisites: tuple[str, ...] = ()
    bypasses_safeguard: bool = False
    description: str = ""


@dataclass(frozen=True)
class ElementRecord:
    element: DirectiveElement
    state: ElementState = ElementState.OPEN
    selected_route_id: str | None = None
    proof_ids: tuple[str, ...] = ()
    reason: str | None = None
    next_trigger: str | None = None
    touched: bool = False
    attempted_route_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CoverageDecision:
    element_id: str
    state: ElementState
    touched: bool
    proof_ids: tuple[str, ...]
    reason: str | None
    next_trigger: str | None


@dataclass(frozen=True)
class ClosureReceipt:
    complete: bool
    claim_allowed: bool
    directive_fingerprint: str
    decisions: tuple[CoverageDecision, ...]
    open_element_ids: tuple[str, ...]
    blocked_element_ids: tuple[str, ...]
    unexplained_element_ids: tuple[str, ...]
    manual_user_tasks: tuple[str, ...] = ()


class RouteExpander:
    """Select the lowest-burden lawful route; never manufacture authority."""

    @staticmethod
    def eligible(
        routes: Iterable[ExecutionRoute],
        *,
        authorized_classes: set[str],
        satisfied_prerequisites: set[str],
        maximum_cost: float = 0.0,
        maximum_user_burden: float = 0.0,
    ) -> tuple[ExecutionRoute, ...]:
        lawful = [
            route
            for route in routes
            if route.available
            and route.safe
            and not route.bypasses_safeguard
            and route.authority_class in authorized_classes
            and route.cost <= maximum_cost
            and route.user_burden <= maximum_user_burden
            and set(route.prerequisites) <= satisfied_prerequisites
        ]
        return tuple(
            sorted(
                lawful,
                key=lambda route: (
                    route.user_burden,
                    route.cost,
                    len(route.prerequisites),
                    route.route_id,
                ),
            )
        )

    @staticmethod
    def missing_prerequisites(
        routes: Iterable[ExecutionRoute], satisfied_prerequisites: set[str]
    ) -> tuple[str, ...]:
        missing: set[str] = set()
        for route in routes:
            if route.available and route.safe and not route.bypasses_safeguard:
                missing.update(set(route.prerequisites) - satisfied_prerequisites)
        return tuple(sorted(missing))


class OrchestrationCompletenessController:
    """Plan and close every directive element with local blocker isolation."""

    def __init__(self) -> None:
        self._records: dict[str, ElementRecord] = {}
        self._routes: dict[str, list[ExecutionRoute]] = {}

    def add(self, element: DirectiveElement) -> ElementRecord:
        if not element.element_id or not element.description.strip():
            raise ValueError("Directive elements require an id and description")
        if element.element_id in self._records:
            raise ValueError("Directive element already exists")
        record = ElementRecord(element=element)
        self._records[element.element_id] = record
        self._routes[element.element_id] = []
        return record

    def add_route(self, route: ExecutionRoute) -> None:
        if route.element_id not in self._records:
            raise ValueError("Route references an unknown directive element")
        if route.cost < 0 or route.user_burden < 0:
            raise ValueError("Route cost and user burden cannot be negative")
        if any(existing.route_id == route.route_id for existing in self._routes[route.element_id]):
            raise ValueError("Route id already exists for directive element")
        self._routes[route.element_id].append(route)

    def _dependencies_satisfied(self, record: ElementRecord) -> bool:
        for dependency in record.element.dependencies:
            dependent = self._records.get(dependency)
            if dependent is None:
                raise ValueError(f"Unknown dependency: {dependency}")
            if dependent.state not in TERMINAL_COMPLETE_STATES:
                return False
        return True

    def plan_ready(
        self,
        *,
        authorized_classes: set[str],
        satisfied_prerequisites: set[str],
        maximum_cost: float = 0.0,
        maximum_user_burden: float = 0.0,
    ) -> tuple[ExecutionRoute, ...]:
        """Return every dependency-ready lawful route, not merely the first lane."""
        ready: list[ExecutionRoute] = []
        for element_id in self._ordered_ids():
            record = self._records[element_id]
            if record.state in TERMINAL_COMPLETE_STATES | {ElementState.RUNNING}:
                continue
            if not self._dependencies_satisfied(record):
                if record.state is not ElementState.OPEN:
                    self._records[element_id] = replace(record, state=ElementState.OPEN)
                continue
            routes = self._routes[element_id]
            eligible = RouteExpander.eligible(
                routes,
                authorized_classes=authorized_classes,
                satisfied_prerequisites=satisfied_prerequisites,
                maximum_cost=maximum_cost,
                maximum_user_burden=maximum_user_burden,
            )
            if eligible:
                selected = eligible[0]
                self._records[element_id] = replace(
                    record,
                    state=ElementState.EXECUTABLE,
                    selected_route_id=selected.route_id,
                    reason=None,
                    next_trigger=None,
                )
                ready.append(selected)
                continue
            missing = RouteExpander.missing_prerequisites(routes, satisfied_prerequisites)
            if missing:
                self._records[element_id] = replace(
                    record,
                    state=ElementState.BLOCKED_EXTERNAL_TRUST,
                    reason="Missing route prerequisites: " + ", ".join(missing),
                    next_trigger="resume_when:" + ",".join(missing),
                )
            else:
                self._records[element_id] = replace(
                    record,
                    state=ElementState.ROUTE_EXHAUSTED,
                    reason="No available lawful route within authority, cost, and burden bounds",
                    next_trigger="resume_when:route_registry_or_authority_changes",
                )
        return tuple(ready)

    def start(self, element_id: str, route_id: str) -> ElementRecord:
        record = self._records[element_id]
        if record.state is not ElementState.EXECUTABLE or record.selected_route_id != route_id:
            raise ValueError("Only the selected executable route can start")
        updated = replace(
            record,
            state=ElementState.RUNNING,
            touched=True,
            attempted_route_ids=tuple(sorted(set(record.attempted_route_ids + (route_id,)))),
        )
        self._records[element_id] = updated
        return updated

    def prove(self, element_id: str, *, proof_ids: tuple[str, ...]) -> ElementRecord:
        if not proof_ids:
            raise ValueError("Proven completion requires proof")
        record = self._records[element_id]
        if record.state not in {ElementState.RUNNING, ElementState.EXECUTABLE}:
            raise ValueError("Only an executable or running element can be proven")
        updated = replace(
            record,
            state=ElementState.PROVEN,
            proof_ids=tuple(sorted(set(proof_ids))),
            reason=None,
            next_trigger=None,
            touched=True,
        )
        self._records[element_id] = updated
        return updated

    def fail(self, element_id: str, *, reason: str, next_trigger: str) -> ElementRecord:
        if not reason or not next_trigger:
            raise ValueError("Failure requires a reason and automatic continuation trigger")
        record = self._records[element_id]
        updated = replace(
            record,
            state=ElementState.FAILED,
            reason=reason,
            next_trigger=next_trigger,
            touched=True,
        )
        self._records[element_id] = updated
        return updated

    def mark_inapplicable(self, element_id: str, *, reason: str, proof_ids: tuple[str, ...]) -> ElementRecord:
        if not reason or not proof_ids:
            raise ValueError("Inapplicability requires reason and proof")
        record = self._records[element_id]
        updated = replace(
            record,
            state=ElementState.INAPPLICABLE,
            reason=reason,
            proof_ids=tuple(sorted(set(proof_ids))),
            touched=True,
        )
        self._records[element_id] = updated
        return updated

    def supersede(self, element_id: str, *, reason: str, correction_proof_id: str) -> ElementRecord:
        if not reason or not correction_proof_id:
            raise ValueError("Supersession requires the user correction proof")
        record = self._records[element_id]
        updated = replace(
            record,
            state=ElementState.SUPERSEDED,
            reason=reason,
            proof_ids=(correction_proof_id,),
            touched=True,
        )
        self._records[element_id] = updated
        return updated

    def _ordered_ids(self) -> tuple[str, ...]:
        return tuple(
            item.element.element_id
            for item in sorted(
                self._records.values(), key=lambda record: (record.element.sequence, record.element.element_id)
            )
        )

    def records(self) -> tuple[ElementRecord, ...]:
        return tuple(self._records[element_id] for element_id in self._ordered_ids())

    def can_finalize(self) -> bool:
        return bool(self._records) and all(
            record.state in TERMINAL_COMPLETE_STATES for record in self._records.values()
        )

    def directive_fingerprint(self) -> str:
        payload = [
            {
                "id": record.element.element_id,
                "description": " ".join(record.element.description.split()),
                "sequence": record.element.sequence,
                "dependencies": sorted(record.element.dependencies),
                "authority": record.element.authority_class,
                "external_effect": record.element.external_effect,
                "criteria": sorted(record.element.completion_criteria),
            }
            for record in self.records()
        ]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    def closure_receipt(self) -> ClosureReceipt:
        decisions = tuple(
            CoverageDecision(
                element_id=record.element.element_id,
                state=record.state,
                touched=record.touched,
                proof_ids=record.proof_ids,
                reason=record.reason,
                next_trigger=record.next_trigger,
            )
            for record in self.records()
        )
        open_ids = tuple(
            decision.element_id
            for decision in decisions
            if decision.state not in TERMINAL_COMPLETE_STATES
        )
        blocked_ids = tuple(
            decision.element_id
            for decision in decisions
            if decision.state
            in {
                ElementState.BLOCKED_EXTERNAL_TRUST,
                ElementState.ROUTE_EXHAUSTED,
                ElementState.FAILED,
            }
        )
        unexplained_ids = tuple(
            decision.element_id
            for decision in decisions
            if not decision.touched
            and decision.state not in {ElementState.BLOCKED_EXTERNAL_TRUST, ElementState.ROUTE_EXHAUSTED}
        )
        complete = self.can_finalize()
        return ClosureReceipt(
            complete=complete,
            claim_allowed=complete and not unexplained_ids,
            directive_fingerprint=self.directive_fingerprint(),
            decisions=decisions,
            open_element_ids=open_ids,
            blocked_element_ids=blocked_ids,
            unexplained_element_ids=unexplained_ids,
        )


class AntiDilutionGate:
    """Reject summaries or plans that silently omit requested elements."""

    @staticmethod
    def validate(
        receipt: ClosureReceipt,
        *,
        represented_element_ids: Iterable[str],
        completion_claimed: bool,
    ) -> tuple[bool, tuple[str, ...]]:
        represented = set(represented_element_ids)
        required = {decision.element_id for decision in receipt.decisions}
        issues: list[str] = []
        for missing in sorted(required - represented):
            issues.append("OMITTED_DIRECTIVE_ELEMENT:" + missing)
        for unknown in sorted(represented - required):
            issues.append("UNKNOWN_DIRECTIVE_ELEMENT:" + unknown)
        if completion_claimed and not receipt.claim_allowed:
            issues.append("FALSE_COMPLETION_CLAIM")
        if receipt.manual_user_tasks:
            issues.append("MANUAL_USER_BURDEN_PRESENT")
        return not issues, tuple(issues)
