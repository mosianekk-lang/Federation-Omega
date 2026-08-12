from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence


class WorkState(str, Enum):
    READY = "READY"
    ACTIVE = "ACTIVE"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True)
class TwinRole:
    name: str
    role: str
    sequence: int
    authority_ceiling: str
    capabilities: tuple[str, ...]
    proof_ownership: tuple[str, ...]
    handoff_to: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkOrder:
    work_id: str
    project_id: str
    objective: str
    primary_twin: str
    collaborators: tuple[str, ...]
    required_proofs: tuple[str, ...]
    state: WorkState = WorkState.READY
    external_authority_required: bool = False
    evidence_target: str | None = None


@dataclass(frozen=True)
class ActivatedWork:
    work_id: str
    project_id: str
    primary_twin: str
    collaborators: tuple[str, ...]
    state: WorkState
    objective: str
    required_proofs: tuple[str, ...]
    evidence_target: str | None
    truth_boundary: str


PROOF_ROUTING: Mapping[str, tuple[str, ...]] = {
    "source": ("Forge", "Bubbles"),
    "tests": ("Pulse", "Forge"),
    "runtime": ("Forge", "Patch"),
    "provider_canary_contract": ("Sparks", "Sentinel", "Ledger"),
    "provider_execution": ("Sparks", "Ledger"),
    "provider_readback": ("Ledger", "Sparks"),
    "deployment_receipt": ("Sparks", "Ledger"),
    "health": ("Patch", "Sparks"),
    "persistence": ("Sparks", "Patch"),
    "rollback": ("Patch", "Sparks"),
    "observability": ("Patch", "Sparks"),
    "user_demo": ("Prism", "Showcase", "Forge"),
    "case_study": ("Showcase", "Beacon", "Ledger"),
    "integration": ("Bridge", "Forge", "Sentinel"),
    "research": ("Scout", "Pulse", "Bubbles"),
    "security": ("Sentinel", "Patch", "Ledger"),
    "product": ("Beacon", "Prism", "Showcase"),
}


class BubblesEngineeringCell:
    """Coordinated, proof-bound delivery cell around the Bubbles architect twin.

    This class does not pretend that named twins are background workers. It is a
    deterministic work-routing and accountability model: every role has explicit
    capabilities, proof ownership, work orders, authority ceilings and handoffs.
    External provider effects remain blocked until an authorised execution surface
    and independent readback exist.
    """

    authority_ceiling = "A1_INTERNAL"

    def __init__(self, roster: Sequence[TwinRole], work_orders: Sequence[WorkOrder]) -> None:
        self.roster = tuple(sorted(roster, key=lambda item: item.sequence))
        self.work_orders = tuple(work_orders)
        names = [item.name for item in self.roster]
        sequences = [item.sequence for item in self.roster]
        if len(names) != len(set(names)):
            raise ValueError("Twin names must be unique")
        if len(sequences) != len(set(sequences)):
            raise ValueError("Twin sequence values must be unique")
        if not self.roster or self.roster[0].name != "Bubbles":
            raise ValueError("Bubbles must lead the engineering cell")
        known = set(names)
        for order in self.work_orders:
            if order.primary_twin not in known:
                raise ValueError(f"Unknown primary twin: {order.primary_twin}")
            unknown_collaborators = set(order.collaborators).difference(known)
            if unknown_collaborators:
                raise ValueError(f"Unknown collaborators: {sorted(unknown_collaborators)}")

    def role(self, name: str) -> TwinRole:
        for item in self.roster:
            if item.name == name:
                return item
        raise KeyError(name)

    def preferred_sequence(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.roster)

    def route_gap(self, proof_gap: str) -> tuple[str, ...]:
        if proof_gap not in PROOF_ROUTING:
            raise KeyError(proof_gap)
        available = {item.name for item in self.roster}
        return tuple(name for name in PROOF_ROUTING[proof_gap] if name in available)

    def activate(self, order: WorkOrder) -> ActivatedWork:
        state = order.state
        if state == WorkState.READY:
            state = WorkState.BLOCKED_EXTERNAL if order.external_authority_required else WorkState.ACTIVE
        if state == WorkState.ACTIVE and order.external_authority_required:
            state = WorkState.BLOCKED_EXTERNAL
        return ActivatedWork(
            work_id=order.work_id,
            project_id=order.project_id,
            primary_twin=order.primary_twin,
            collaborators=order.collaborators,
            state=state,
            objective=order.objective,
            required_proofs=order.required_proofs,
            evidence_target=order.evidence_target,
            truth_boundary=(
                "ACTIVE means executable internal work is admitted now; it does not imply asynchronous "
                "background execution. BLOCKED_EXTERNAL means provider/legal/credential authority is genuinely "
                "required and no provider effect is claimed."
            ),
        )

    def activate_all(self) -> tuple[ActivatedWork, ...]:
        return tuple(self.activate(order) for order in self.work_orders)

    def workload_for(self, twin_name: str) -> tuple[ActivatedWork, ...]:
        self.role(twin_name)
        return tuple(
            item
            for item in self.activate_all()
            if item.primary_twin == twin_name or twin_name in item.collaborators
        )

    def accountability_report(self) -> dict[str, object]:
        activated = self.activate_all()
        workloads = {name: len(self.workload_for(name)) for name in self.preferred_sequence()}
        unassigned = [name for name, count in workloads.items() if count == 0]
        states = {state.value: sum(1 for item in activated if item.state == state) for state in WorkState}
        return {
            "cell": "Bubbles Applied AI Engineering Cell",
            "authority_ceiling": self.authority_ceiling,
            "preferred_sequence": list(self.preferred_sequence()),
            "role_count": len(self.roster),
            "work_order_count": len(activated),
            "state_counts": states,
            "workloads": workloads,
            "unassigned_roles": unassigned,
            "ready_for_operation": not unassigned,
            "truth_boundary": (
                "The engineering cell is an executable routing/accountability model. It creates no provider "
                "authority and makes no claim of background autonomous execution."
            ),
        }

    def next_internal_work(self) -> tuple[ActivatedWork, ...]:
        return tuple(item for item in self.activate_all() if item.state == WorkState.ACTIVE)

    def externally_blocked_work(self) -> tuple[ActivatedWork, ...]:
        return tuple(item for item in self.activate_all() if item.state == WorkState.BLOCKED_EXTERNAL)


def build_roles(records: Iterable[Mapping[str, object]]) -> tuple[TwinRole, ...]:
    roles = []
    for record in records:
        roles.append(
            TwinRole(
                name=str(record["name"]),
                role=str(record["role"]),
                sequence=int(record["sequence"]),
                authority_ceiling=str(record.get("authority_ceiling", "A1_INTERNAL")),
                capabilities=tuple(str(item) for item in record.get("capabilities", [])),
                proof_ownership=tuple(str(item) for item in record.get("proof_ownership", [])),
                handoff_to=tuple(str(item) for item in record.get("handoff_to", [])),
            )
        )
    return tuple(roles)


def build_work_orders(records: Iterable[Mapping[str, object]]) -> tuple[WorkOrder, ...]:
    orders = []
    for record in records:
        orders.append(
            WorkOrder(
                work_id=str(record["work_id"]),
                project_id=str(record["project_id"]),
                objective=str(record["objective"]),
                primary_twin=str(record["primary_twin"]),
                collaborators=tuple(str(item) for item in record.get("collaborators", [])),
                required_proofs=tuple(str(item) for item in record.get("required_proofs", [])),
                state=WorkState(str(record.get("state", WorkState.READY.value))),
                external_authority_required=bool(record.get("external_authority_required", False)),
                evidence_target=(str(record["evidence_target"]) if record.get("evidence_target") else None),
            )
        )
    return tuple(orders)
