"""FUSE One Single-Mind Collective Cognition v1.

A deterministic, provider-neutral coordination kernel for bounded execution actors.
This module is intentionally non-sovereign: it derives coordination decisions from
caller-supplied state and never grants authority, performs effects, or becomes a
truth/proof root.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping, Sequence


ACTIVE_STATES = frozenset({"REGISTERED", "ACTIVE", "CLAIMED", "RUNNING", "WAITING", "IDLE", "SUSPECT"})


class ConflictClass(str, Enum):
    DISJOINT_READ = "DISJOINT_READ"
    SHARED_READ = "SHARED_READ"
    DISJOINT_WRITE = "DISJOINT_WRITE"
    OVERLAPPING_WRITE = "OVERLAPPING_WRITE"
    SHARED_EFFECT = "SHARED_EFFECT"
    CANONICAL_STATE = "CANONICAL_STATE"
    UNKNOWN = "UNKNOWN"


class DedupeAction(str, Enum):
    START = "START"
    JOIN_EXISTING = "JOIN_EXISTING"
    OBSERVE = "OBSERVE"
    BECOME_CRITIC = "BECOME_CRITIC"
    BECOME_TESTER = "BECOME_TESTER"
    WORK_STEAL_DISJOINT_SUBPREDICATE = "WORK_STEAL_DISJOINT_SUBPREDICATE"
    CONSUME_RESULT = "CONSUME_RESULT"


class EpistemicMode(str, Enum):
    COORDINATION_ONLY = "COORDINATION_ONLY"
    DEPENDENCY_AWARE = "DEPENDENCY_AWARE"
    EVIDENCE_AWARE = "EVIDENCE_AWARE"
    FULL_COLLABORATIVE = "FULL_COLLABORATIVE"
    BLIND_CHALLENGER = "BLIND_CHALLENGER"
    JUDGE_ISOLATED = "JUDGE_ISOLATED"


class ClaimState(str, Enum):
    OBSERVATION = "OBSERVATION"
    HYPOTHESIS = "HYPOTHESIS"
    EVIDENCE_SUPPORTED = "EVIDENCE_SUPPORTED"
    JUDGE_ACCEPTED = "JUDGE_ACCEPTED"
    SHARED_FACT = "SHARED_FACT"
    SUPERSEDED = "SUPERSEDED"
    REFUTED = "REFUTED"
    UNKNOWN = "UNKNOWN"
    DISPUTED = "DISPUTED"


def _canon_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _canon_seq(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({_canon_text(v) for v in values if str(v).strip()}))


def _digest_payload(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SemanticObjective:
    desired_outcome: str
    acceptance_predicates: tuple[str, ...] = ()
    target_capability: str = ""
    mutable_scope: tuple[str, ...] = ()
    effect_scope: tuple[str, ...] = ()
    source_epoch: str = ""
    provider_epoch: str = ""

    @classmethod
    def build(
        cls,
        desired_outcome: str,
        acceptance_predicates: Iterable[str] = (),
        target_capability: str = "",
        mutable_scope: Iterable[str] = (),
        effect_scope: Iterable[str] = (),
        source_epoch: str = "",
        provider_epoch: str = "",
    ) -> "SemanticObjective":
        return cls(
            desired_outcome=_canon_text(desired_outcome),
            acceptance_predicates=_canon_seq(acceptance_predicates),
            target_capability=_canon_text(target_capability),
            mutable_scope=_canon_seq(mutable_scope),
            effect_scope=_canon_seq(effect_scope),
            source_epoch=source_epoch.strip(),
            provider_epoch=provider_epoch.strip(),
        )

    @property
    def fingerprint(self) -> str:
        return _digest_payload(asdict(self))


@dataclass(frozen=True)
class SpawnRecord:
    spawn_id: str
    parent_spawn_id: str | None
    mission_id: str
    packet_id: str | None
    semantic_role_id: str
    worker_class: str
    runtime: str
    provider: str | None
    model: str | None
    state: str
    dependencies: tuple[str, ...] = ()
    read_scope: tuple[str, ...] = ()
    write_scope: tuple[str, ...] = ()
    effect_scope: tuple[str, ...] = ()
    source_epoch: str = ""
    provider_epoch: str = ""
    authority_ceiling: str = ""
    privacy_ceiling: str = ""
    cost_ceiling: str = ""
    idempotency_key: str = ""
    fencing_token: int | None = None
    heartbeat_at: str | None = None
    checkpoint_pointer: str | None = None
    result_pointer: str | None = None
    failure_fingerprint: str | None = None
    next_dependency: str | None = None
    semantic_objective_hash: str = ""
    touches_canonical_state: bool = False
    scope_known: bool = True

    def compact_projection(self) -> dict[str, object]:
        return {
            "spawn_id": self.spawn_id,
            "mission_id": self.mission_id,
            "packet_id": self.packet_id,
            "semantic_role_id": self.semantic_role_id,
            "worker_class": self.worker_class,
            "runtime": self.runtime,
            "provider": self.provider,
            "state": self.state,
            "dependencies": list(self.dependencies),
            "read_scope_digest": _digest_payload({"v": _canon_seq(self.read_scope)}),
            "write_scope_digest": _digest_payload({"v": _canon_seq(self.write_scope)}),
            "effect_scope_digest": _digest_payload({"v": _canon_seq(self.effect_scope)}),
            "source_epoch": self.source_epoch,
            "provider_epoch": self.provider_epoch,
            "fencing_token": self.fencing_token,
            "heartbeat_at": self.heartbeat_at,
            "checkpoint_pointer": self.checkpoint_pointer,
            "result_pointer": self.result_pointer,
            "failure_fingerprint": self.failure_fingerprint,
            "next_dependency": self.next_dependency,
            "semantic_objective_hash": self.semantic_objective_hash,
        }


@dataclass(frozen=True)
class ContinuationCapsule:
    mission_id: str
    packet_id: str | None
    objective_hash: str
    terminal_predicates_closed: tuple[str, ...]
    terminal_predicates_open: tuple[str, ...]
    accepted_fact_refs: tuple[str, ...]
    contradiction_refs: tuple[str, ...]
    completed_work_refs: tuple[str, ...]
    failure_fingerprints: tuple[str, ...]
    active_owner_refs: tuple[str, ...]
    source_epoch: str
    provider_epochs: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    checkpoint_hash: str
    authority_ceiling: str
    effect_ceiling: str
    next_dependency_ready_action: str
    owner_action_required: str = "NONE"

    @property
    def digest(self) -> str:
        return _digest_payload(asdict(self))


@dataclass(frozen=True)
class BeliefClaim:
    claim_id: str
    subject: str
    value: str
    state: ClaimState
    observed_at: str
    source_epoch: str = ""
    provider_epoch: str = ""
    evidence_refs: tuple[str, ...] = ()
    falsifier: str = ""

    def identity(self) -> tuple[str, str]:
        return (_canon_text(self.subject), self.claim_id)


def preserve_contradictions(claims: Sequence[BeliefClaim]) -> tuple[BeliefClaim, ...]:
    """Return all claims unchanged; contradictory values are evidence, not overwrite targets."""
    return tuple(claims)


def classify_conflict(a: SpawnRecord, b: SpawnRecord) -> ConflictClass:
    if not a.scope_known or not b.scope_known:
        return ConflictClass.UNKNOWN
    if a.touches_canonical_state or b.touches_canonical_state:
        return ConflictClass.CANONICAL_STATE

    a_read, b_read = set(a.read_scope), set(b.read_scope)
    a_write, b_write = set(a.write_scope), set(b.write_scope)
    a_effect, b_effect = set(a.effect_scope), set(b.effect_scope)

    if a_effect & b_effect:
        return ConflictClass.SHARED_EFFECT
    if a_write & b_write:
        return ConflictClass.OVERLAPPING_WRITE
    if (a_write & b_read) or (b_write & a_read):
        return ConflictClass.OVERLAPPING_WRITE
    if a_write or b_write:
        return ConflictClass.DISJOINT_WRITE
    if a_read & b_read:
        return ConflictClass.SHARED_READ
    return ConflictClass.DISJOINT_READ


def choose_dedupe_action(
    newcomer: SpawnRecord,
    siblings: Sequence[SpawnRecord],
    *,
    epistemic_mode: EpistemicMode = EpistemicMode.DEPENDENCY_AWARE,
) -> DedupeAction:
    equivalent = [
        s
        for s in siblings
        if s.spawn_id != newcomer.spawn_id
        and s.semantic_objective_hash
        and s.semantic_objective_hash == newcomer.semantic_objective_hash
        and s.source_epoch == newcomer.source_epoch
        and s.provider_epoch == newcomer.provider_epoch
    ]
    if not equivalent:
        return DedupeAction.START

    if epistemic_mode in {EpistemicMode.BLIND_CHALLENGER, EpistemicMode.JUDGE_ISOLATED}:
        return DedupeAction.BECOME_CRITIC

    states = {s.state.upper() for s in equivalent}
    if states & {"RESULT_READY", "ACKED", "COMPLETE", "TERMINATED"}:
        return DedupeAction.CONSUME_RESULT
    if states & ACTIVE_STATES:
        return DedupeAction.JOIN_EXISTING
    return DedupeAction.OBSERVE


def derive_active_cognition_map(records: Sequence[SpawnRecord]) -> tuple[dict[str, object], ...]:
    active = [r for r in records if r.state.upper() in ACTIVE_STATES]
    active.sort(key=lambda r: (r.mission_id, r.semantic_role_id, r.spawn_id))
    return tuple(r.compact_projection() for r in active)


def continuation_required(record: SpawnRecord) -> bool:
    return record.state.upper() in {"RUNNING", "WAITING", "SUSPECT"} and not record.checkpoint_pointer


def sibling_preflight(
    actor: SpawnRecord,
    siblings: Sequence[SpawnRecord],
    *,
    epistemic_mode: EpistemicMode = EpistemicMode.DEPENDENCY_AWARE,
) -> dict[str, object]:
    relevant = tuple(s for s in siblings if s.spawn_id != actor.spawn_id)
    conflicts = {s.spawn_id: classify_conflict(actor, s).value for s in relevant}
    dedupe = choose_dedupe_action(actor, relevant, epistemic_mode=epistemic_mode)
    blocking = tuple(
        sid
        for sid, cls in conflicts.items()
        if cls in {
            ConflictClass.OVERLAPPING_WRITE.value,
            ConflictClass.SHARED_EFFECT.value,
            ConflictClass.CANONICAL_STATE.value,
            ConflictClass.UNKNOWN.value,
        }
    )
    return {
        "spawn_id": actor.spawn_id,
        "mission_id": actor.mission_id,
        "semantic_objective_hash": actor.semantic_objective_hash,
        "dedupe_action": dedupe.value,
        "conflicts": conflicts,
        "blocking_siblings": blocking,
        "may_execute_disjoint_work": dedupe != DedupeAction.CONSUME_RESULT,
        "authority_ceiling": actor.authority_ceiling,
        "privacy_ceiling": actor.privacy_ceiling,
        "cost_ceiling": actor.cost_ceiling,
    }


def propagate_learning(
    *,
    learning_refs: Iterable[str],
    receiver_scope: Iterable[str],
    authority_ceiling: str | None = None,
    provider_permissions: Iterable[str] = (),
) -> dict[str, object]:
    """Project reusable learning while explicitly refusing authority inheritance."""
    _ = authority_ceiling, tuple(provider_permissions)
    return {
        "learning_refs": list(_canon_seq(learning_refs)),
        "receiver_scope": list(_canon_seq(receiver_scope)),
        "authority_inherited": False,
        "provider_permissions_inherited": False,
    }


def checkpoint_digest(payload: Mapping[str, object]) -> str:
    return _digest_payload(payload)
