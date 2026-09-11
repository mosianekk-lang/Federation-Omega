from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class OutcomeState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    EVALUATING = "evaluating"
    NEEDS_REVISION = "needs_revision"
    SATISFIED = "satisfied"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class Outcome:
    outcome_id: str
    description: str
    max_iterations: int
    iteration: int = 0
    state: OutcomeState = OutcomeState.PENDING
    explanation: str = ""


class OutcomeEvaluator:
    def __init__(self) -> None:
        self._items: Dict[str, Outcome] = {}

    def define(self, outcome_id: str, description: str, *, max_iterations: int = 3) -> Outcome:
        if max_iterations < 1:
            raise ValueError("max_iterations must be >=1")
        if outcome_id in self._items:
            raise ValueError("duplicate outcome")
        out = Outcome(outcome_id, description, max_iterations)
        self._items[outcome_id] = out
        return out

    def start(self, outcome_id: str) -> Outcome:
        out = self._items[outcome_id]
        out = Outcome(out.outcome_id, out.description, out.max_iterations, out.iteration, OutcomeState.RUNNING)
        self._items[outcome_id] = out
        return out

    def evaluate(self, outcome_id: str, *, satisfied: bool, recoverable: bool = True,
                 explanation: str = "") -> Outcome:
        out = self._items[outcome_id]
        if out.state not in {OutcomeState.RUNNING, OutcomeState.NEEDS_REVISION, OutcomeState.EVALUATING}:
            raise ValueError("outcome not evaluable in current state")
        if satisfied:
            nxt = OutcomeState.SATISFIED
            iteration = out.iteration
        elif not recoverable:
            nxt = OutcomeState.FAILED
            iteration = out.iteration
        elif out.iteration + 1 >= out.max_iterations:
            nxt = OutcomeState.MAX_ITERATIONS_REACHED
            iteration = out.iteration + 1
        else:
            nxt = OutcomeState.NEEDS_REVISION
            iteration = out.iteration + 1
        out = Outcome(out.outcome_id, out.description, out.max_iterations, iteration, nxt, explanation)
        self._items[outcome_id] = out
        return out


@dataclass(frozen=True)
class AgentDefinition:
    agent_id: str
    version: int
    model: str
    tools_digest: str
    skills_digest: str


class AgentDefinitionStore:
    """Versioned reusable agent definitions with optimistic concurrency semantics."""
    def __init__(self) -> None:
        self._defs: Dict[str, AgentDefinition] = {}

    def create(self, agent_id: str, *, model: str, tools_digest: str, skills_digest: str) -> AgentDefinition:
        if agent_id in self._defs:
            raise ValueError("agent exists")
        d = AgentDefinition(agent_id, 1, model, tools_digest, skills_digest)
        self._defs[agent_id] = d
        return d

    def update(self, agent_id: str, *, expected_version: int, model: str | None = None,
               tools_digest: str | None = None, skills_digest: str | None = None) -> AgentDefinition:
        cur = self._defs[agent_id]
        if cur.version != expected_version:
            raise RuntimeError("version conflict")
        d = AgentDefinition(
            agent_id,
            cur.version + 1,
            model or cur.model,
            tools_digest or cur.tools_digest,
            skills_digest or cur.skills_digest,
        )
        self._defs[agent_id] = d
        return d
