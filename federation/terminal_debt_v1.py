"""FUSE Terminal Debt Ledger + Autonomous Debt Burner v1.

A durable zero-debt finality mechanism for FUSE missions.  It converts mandatory
terminal predicates into typed debt, preserves them across chat/client loss, ranks
dependency-ready work, executes collision-safe waves through registered handlers,
and refuses terminal success while mandatory debt remains open.

The module does not mint authority, install software by itself, or claim a
capability is mature without evidence.  Effect authority and provider/runtime
execution remain with existing FUSE organs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from hashlib import sha256
import json
from typing import Callable, Iterable, Mapping, Sequence

from .run_store_v1 import RunStore


SCHEMA = "FUSE-TERMINAL-DEBT-V1"
VERSION = "1.0.0"

DEFAULT_MATURITY_STAGES = (
    "DESIGN",
    "SOURCE",
    "BUILD",
    "TEST",
    "INTEGRATION",
    "RUNTIME",
    "SEMANTIC",
    "RECOVERY",
    "SECURITY",
    "UX",
    "OWNER_VALUE",
)


class DebtState(StrEnum):
    OPEN = "OPEN"
    READY = "READY"
    BLOCKED = "BLOCKED"
    CLOSED = "CLOSED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True, slots=True)
class MaturityVector:
    required: tuple[str, ...] = DEFAULT_MATURITY_STAGES
    passed: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        required = tuple(dict.fromkeys(str(x).upper() for x in self.required if str(x).strip()))
        passed = tuple(dict.fromkeys(str(x).upper() for x in self.passed if str(x).strip()))
        if not required:
            raise ValueError("MATURITY_REQUIRED_EMPTY")
        object.__setattr__(self, "required", required)
        object.__setattr__(self, "passed", passed)

    @property
    def missing(self) -> tuple[str, ...]:
        accepted = set(self.passed)
        return tuple(stage for stage in self.required if stage not in accepted)

    @property
    def complete(self) -> bool:
        return not self.missing


@dataclass(frozen=True, slots=True)
class TerminalDebtSpec:
    debt_id: str
    predicate: str
    family: str = "GENERAL"
    dependencies: tuple[str, ...] = ()
    collision_keys: tuple[str, ...] = ()
    required_maturity: tuple[str, ...] = DEFAULT_MATURITY_STAGES
    priority: int = 50
    unlock_value: float = 1.0
    estimated_cost: float = 1.0
    owner_only: bool = False
    effect_class: str = "BUILD_TEST"
    mandatory: bool = True
    next_action: str = ""

    def __post_init__(self) -> None:
        if not self.debt_id.strip():
            raise ValueError("DEBT_ID_REQUIRED")
        if not self.predicate.strip():
            raise ValueError("PREDICATE_REQUIRED")
        if self.priority < 0:
            raise ValueError("PRIORITY_NEGATIVE")
        if self.estimated_cost <= 0:
            raise ValueError("ESTIMATED_COST_NONPOSITIVE")


@dataclass(frozen=True, slots=True)
class TerminalDebtItem:
    mission_id: str
    spec: TerminalDebtSpec
    maturity: MaturityVector
    state: DebtState
    evidence_refs: tuple[str, ...] = ()
    blocker_keys: tuple[str, ...] = ()
    failure_fingerprint: str = ""
    attempts: int = 0

    @property
    def terminal_score(self) -> float:
        missing_factor = max(1, len(self.maturity.missing))
        return (
            max(1, self.spec.priority)
            * max(0.01, float(self.spec.unlock_value))
            / max(0.01, float(self.spec.estimated_cost))
            / missing_factor
        )

    @property
    def closed(self) -> bool:
        return self.state in (DebtState.CLOSED, DebtState.SUPERSEDED)


@dataclass(frozen=True, slots=True)
class DebtOutcome:
    ok: bool
    evidence_refs: tuple[str, ...] = ()
    passed_maturity: tuple[str, ...] = ()
    blocker_keys: tuple[str, ...] = ()
    failure_fingerprint: str = ""
    superseded: bool = False


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def failure_fingerprint(*parts: object) -> str:
    return sha256("|".join(str(x) for x in parts).encode()).hexdigest()[:24]


def debt_to_payload(item: TerminalDebtItem) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "mission_id": item.mission_id,
        "debt_id": item.spec.debt_id,
        "predicate": item.spec.predicate,
        "family": item.spec.family,
        "dependencies": list(item.spec.dependencies),
        "collision_keys": list(item.spec.collision_keys),
        "required_maturity": list(item.maturity.required),
        "passed_maturity": list(item.maturity.passed),
        "missing_maturity": list(item.maturity.missing),
        "priority": item.spec.priority,
        "unlock_value": item.spec.unlock_value,
        "estimated_cost": item.spec.estimated_cost,
        "owner_only": item.spec.owner_only,
        "effect_class": item.spec.effect_class,
        "mandatory": item.spec.mandatory,
        "next_action": item.spec.next_action,
        "state": item.state.value,
        "evidence_refs": list(item.evidence_refs),
        "blocker_keys": list(item.blocker_keys),
        "failure_fingerprint": item.failure_fingerprint,
        "attempts": item.attempts,
        "terminal_score": item.terminal_score,
    }


def payload_to_debt(payload: Mapping[str, object]) -> TerminalDebtItem:
    spec = TerminalDebtSpec(
        debt_id=str(payload["debt_id"]),
        predicate=str(payload["predicate"]),
        family=str(payload.get("family", "GENERAL")),
        dependencies=tuple(str(x) for x in payload.get("dependencies", ()) or ()),
        collision_keys=tuple(str(x) for x in payload.get("collision_keys", ()) or ()),
        required_maturity=tuple(str(x) for x in payload.get("required_maturity", DEFAULT_MATURITY_STAGES) or DEFAULT_MATURITY_STAGES),
        priority=int(payload.get("priority", 50)),
        unlock_value=float(payload.get("unlock_value", 1.0)),
        estimated_cost=float(payload.get("estimated_cost", 1.0)),
        owner_only=bool(payload.get("owner_only", False)),
        effect_class=str(payload.get("effect_class", "BUILD_TEST")),
        mandatory=bool(payload.get("mandatory", True)),
        next_action=str(payload.get("next_action", "")),
    )
    maturity = MaturityVector(
        required=spec.required_maturity,
        passed=tuple(str(x) for x in payload.get("passed_maturity", ()) or ()),
    )
    return TerminalDebtItem(
        mission_id=str(payload["mission_id"]),
        spec=spec,
        maturity=maturity,
        state=DebtState(str(payload.get("state", DebtState.OPEN.value))),
        evidence_refs=tuple(str(x) for x in payload.get("evidence_refs", ()) or ()),
        blocker_keys=tuple(str(x) for x in payload.get("blocker_keys", ()) or ()),
        failure_fingerprint=str(payload.get("failure_fingerprint", "")),
        attempts=int(payload.get("attempts", 0)),
    )


class TerminalDebtLedger:
    """Durable terminal-debt controller backed by the existing RunStore."""

    def __init__(self, store: RunStore):
        self.store = store

    @staticmethod
    def _evidence_for(
        spec: TerminalDebtSpec,
        evidence: Mapping[str, object],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        raw = evidence.get(spec.predicate)
        if raw is True:
            return spec.required_maturity, ()
        if raw is False or raw is None:
            return (), ()
        if isinstance(raw, Mapping):
            passed = tuple(
                stage for stage in spec.required_maturity
                if raw.get(stage) is True or raw.get(stage.lower()) is True
            )
            refs = tuple(str(x) for x in raw.get("evidence_refs", ()) or ())
            return passed, refs
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            passed = tuple(str(x).upper() for x in raw)
            return passed, ()
        return (), ()

    def reconcile(
        self,
        mission_id: str,
        specs: Sequence[TerminalDebtSpec],
        evidence: Mapping[str, object] | None = None,
    ) -> tuple[TerminalDebtItem, ...]:
        evidence = evidence or {}
        existing = {item.spec.debt_id: item for item in self.items(mission_id)}
        out: list[TerminalDebtItem] = []
        declared = set()

        for spec in specs:
            declared.add(spec.debt_id)
            passed, refs = self._evidence_for(spec, evidence)
            prior = existing.get(spec.debt_id)
            merged_passed = tuple(dict.fromkeys((*((prior.maturity.passed) if prior else ()), *passed)))
            maturity = MaturityVector(spec.required_maturity, merged_passed)
            evidence_refs = tuple(dict.fromkeys((*((prior.evidence_refs) if prior else ()), *refs)))
            if maturity.complete:
                state = DebtState.CLOSED
                blockers: tuple[str, ...] = ()
            elif prior and prior.state is DebtState.SUPERSEDED:
                state = DebtState.SUPERSEDED
                blockers = ()
            else:
                state = DebtState.OPEN
                blockers = prior.blocker_keys if prior else ()
            item = TerminalDebtItem(
                mission_id,
                spec,
                maturity,
                state,
                evidence_refs,
                blockers,
                prior.failure_fingerprint if prior else "",
                prior.attempts if prior else 0,
            )
            self.store.upsert_terminal_debt(
                mission_id,
                spec.debt_id,
                debt_to_payload(item),
                state=item.state.value,
            )
            out.append(item)

        # A previously mandatory debt may not silently disappear from the active
        # profile.  Preserve it as OPEN unless the prior record was explicitly
        # closed/superseded.
        for debt_id, prior in existing.items():
            if debt_id in declared:
                continue
            if prior.spec.mandatory and not prior.closed:
                self.store.upsert_terminal_debt(
                    mission_id,
                    debt_id,
                    debt_to_payload(prior),
                    state=prior.state.value,
                )
                out.append(prior)

        return tuple(sorted(out, key=lambda x: x.spec.debt_id))

    def items(self, mission_id: str) -> tuple[TerminalDebtItem, ...]:
        rows = self.store.terminal_debts(mission_id)
        return tuple(payload_to_debt(row["payload"]) for row in rows)

    def open_items(self, mission_id: str, *, mandatory_only: bool = True) -> tuple[TerminalDebtItem, ...]:
        items = self.items(mission_id)
        return tuple(
            item for item in items
            if not item.closed and (item.spec.mandatory or not mandatory_only)
        )

    def terminal_zero(self, mission_id: str) -> bool:
        return len(self.open_items(mission_id, mandatory_only=True)) == 0

    def ready_items(
        self,
        mission_id: str,
        *,
        owner_authority: bool = False,
    ) -> tuple[TerminalDebtItem, ...]:
        items = self.items(mission_id)
        state = {item.spec.debt_id: item for item in items}
        ready = []
        for item in items:
            if item.closed or not item.spec.mandatory:
                continue
            if item.spec.owner_only and not owner_authority:
                continue
            if item.blocker_keys:
                continue
            if all(state.get(dep) is not None and state[dep].closed for dep in item.spec.dependencies):
                ready.append(item)
        return tuple(sorted(ready, key=lambda x: (-x.terminal_score, x.spec.debt_id)))

    def burn_plan(
        self,
        mission_id: str,
        *,
        owner_authority: bool = False,
        limit: int = 8,
    ) -> tuple[TerminalDebtItem, ...]:
        ready = self.ready_items(mission_id, owner_authority=owner_authority)
        selected: list[TerminalDebtItem] = []
        occupied: set[str] = set()
        for item in ready:
            keys = set(item.spec.collision_keys)
            if keys & occupied:
                continue
            selected.append(item)
            occupied |= keys
            if len(selected) >= max(1, limit):
                break
        return tuple(selected)

    def apply_outcome(self, item: TerminalDebtItem, outcome: DebtOutcome) -> TerminalDebtItem:
        if outcome.superseded:
            state = DebtState.SUPERSEDED
            maturity = item.maturity
        else:
            maturity = MaturityVector(
                item.maturity.required,
                tuple(dict.fromkeys((*item.maturity.passed, *(str(x).upper() for x in outcome.passed_maturity)))),
            )
            state = DebtState.CLOSED if outcome.ok and maturity.complete else (
                DebtState.BLOCKED if outcome.blocker_keys else DebtState.OPEN
            )
        updated = TerminalDebtItem(
            item.mission_id,
            item.spec,
            maturity,
            state,
            tuple(dict.fromkeys((*item.evidence_refs, *outcome.evidence_refs))),
            tuple(outcome.blocker_keys),
            outcome.failure_fingerprint or ("" if outcome.ok else failure_fingerprint(item.spec.debt_id, item.attempts + 1)),
            item.attempts + 1,
        )
        self.store.upsert_terminal_debt(
            item.mission_id,
            item.spec.debt_id,
            debt_to_payload(updated),
            state=updated.state.value,
        )
        return updated


class AutonomousDebtBurner:
    """Executes a collision-safe READY debt wave through registered handlers."""

    def __init__(
        self,
        ledger: TerminalDebtLedger,
        handlers: Mapping[str, Callable[[TerminalDebtItem], DebtOutcome]],
    ) -> None:
        self.ledger = ledger
        self.handlers = dict(handlers)

    def burn_wave(
        self,
        mission_id: str,
        *,
        owner_authority: bool = False,
        limit: int = 8,
    ) -> tuple[TerminalDebtItem, ...]:
        plan = self.ledger.burn_plan(
            mission_id,
            owner_authority=owner_authority,
            limit=limit,
        )
        results = []
        for item in plan:
            handler = self.handlers.get(item.spec.family) or self.handlers.get("*")
            if handler is None:
                outcome = DebtOutcome(
                    False,
                    blocker_keys=(f"NO_HANDLER:{item.spec.family}",),
                    failure_fingerprint=failure_fingerprint("NO_HANDLER", item.spec.family),
                )
            else:
                outcome = handler(item)
                if not isinstance(outcome, DebtOutcome):
                    raise TypeError("DEBT_HANDLER_MUST_RETURN_DEBT_OUTCOME")
            results.append(self.ledger.apply_outcome(item, outcome))
        return tuple(results)


def compile_predicate_specs(
    predicates: Iterable[str],
    *,
    family: str = "TERMINAL",
    required_maturity: tuple[str, ...] = DEFAULT_MATURITY_STAGES,
    priority: int = 50,
) -> tuple[TerminalDebtSpec, ...]:
    return tuple(
        TerminalDebtSpec(
            debt_id=f"DEBT-{str(predicate).upper()}",
            predicate=str(predicate).upper(),
            family=family,
            required_maturity=required_maturity,
            priority=priority,
        )
        for predicate in dict.fromkeys(str(x) for x in predicates if str(x).strip())
    )


__all__ = [
    "AutonomousDebtBurner",
    "DebtOutcome",
    "DebtState",
    "DEFAULT_MATURITY_STAGES",
    "MaturityVector",
    "TerminalDebtItem",
    "TerminalDebtLedger",
    "TerminalDebtSpec",
    "compile_predicate_specs",
    "failure_fingerprint",
]
