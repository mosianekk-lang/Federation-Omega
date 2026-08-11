from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

class Stage(str, Enum):
    INTAKE = "INTAKE"
    DISCOVERY = "DISCOVERY"
    DECOMPOSITION = "DECOMPOSITION"
    ARCHITECTURE = "ARCHITECTURE"
    BUILD = "BUILD"
    TEST = "TEST"
    DEPLOY = "DEPLOY"
    VERIFY = "VERIFY"
    OPERATE = "OPERATE"
    MAINTAIN = "MAINTAIN"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"

@dataclass
class Concept:
    title: str
    description: str
    users: list[str] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    preferred_surfaces: list[str] = field(default_factory=list)

@dataclass
class WorkPacket:
    packet_id: str
    stage: Stage
    objective: str
    inputs: list[str]
    outputs: list[str]
    proof_gate: str
    authority: str = "A0"
    status: str = "PENDING"
    dependencies: list[str] = field(default_factory=list)

@dataclass
class BuildPlan:
    concept: Concept
    packets: list[WorkPacket]
    architecture: dict[str, Any]
    deployment_routes: list[dict[str, Any]]
    maintenance_plan: dict[str, Any]
    truth_boundary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
