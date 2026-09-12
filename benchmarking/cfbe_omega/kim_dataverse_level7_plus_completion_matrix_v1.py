from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class GateClass(str, Enum):
    SOURCE = "SOURCE"
    HOSTED = "HOSTED"
    PROVIDER = "PROVIDER"
    OBSERVED = "OBSERVED"
    VALUE = "VALUE"
    OWNER = "OWNER"


@dataclass(frozen=True)
class CompletionGate:
    gate_id: str
    gate_class: GateClass
    satisfied: bool
    blocking_level: int
    authority_required: bool = False


@dataclass(frozen=True)
class CompletionMatrix:
    highest_unblocked_level: int
    open_gates: tuple[str, ...]
    owner_gates: tuple[str, ...]
    safe_autopilot_gates: tuple[str, ...]


def compile_completion_matrix(gates: Sequence[CompletionGate]) -> CompletionMatrix:
    ids = [gate.gate_id for gate in gates]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate gate_id")
    open_gates = [gate for gate in gates if not gate.satisfied]
    highest = 8
    if open_gates:
        highest = min(gate.blocking_level for gate in open_gates) - 1
    owner = tuple(sorted(gate.gate_id for gate in open_gates if gate.authority_required or gate.gate_class == GateClass.OWNER))
    autopilot = tuple(sorted(gate.gate_id for gate in open_gates if gate.gate_id not in owner))
    return CompletionMatrix(max(4, highest), tuple(sorted(gate.gate_id for gate in open_gates)), owner, autopilot)
