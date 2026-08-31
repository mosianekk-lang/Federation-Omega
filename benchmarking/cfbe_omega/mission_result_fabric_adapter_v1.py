from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

from federation.bubbles_frontier_hyperperformance import (
    CacheDecision,
    DeterministicAction,
    DeterministicResultCache,
)
from federation.mission_ir import MissionIR


_SCHEMA = "FEDERATION-MISSION-RESULT-IDENTITY-V1"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class MissionResultIdentity:
    schema: str
    mission_id: str
    mission_ir_sha256: str
    step_id: str
    source_sha256: str
    input_sha256: str
    policy_sha256: str
    environment_sha256: str
    proof_scope: str
    fresh_until: str
    cache_key: str

    def deterministic_action(self) -> DeterministicAction:
        return DeterministicAction(
            action=f"MISSIONIR:{self.mission_id}:{self.step_id}",
            source_sha256=self.source_sha256,
            input_sha256=self.input_sha256,
            environment_sha256=self.environment_sha256,
            proof_scope=self.proof_scope,
            fresh_until=self.fresh_until,
            effect_class="NO_EFFECT",
        )

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "mission_id": self.mission_id,
            "mission_ir_sha256": self.mission_ir_sha256,
            "step_id": self.step_id,
            "source_sha256": self.source_sha256,
            "input_sha256": self.input_sha256,
            "policy_sha256": self.policy_sha256,
            "environment_sha256": self.environment_sha256,
            "proof_scope": self.proof_scope,
            "fresh_until": self.fresh_until,
            "cache_key": self.cache_key,
            "truth_boundary": {
                "step_effect_class": "NO_EFFECT",
                "provider_effect_authorized": False,
                "financial_effect_authorized": False,
                "publication_authorized": False,
                "persistent_cache_proven": False,
            },
        }


@dataclass(frozen=True, slots=True)
class MissionResultLookupReceipt:
    state: str
    reuse: bool
    mission_id: str
    step_id: str
    cache_key: str
    result_ref: str = ""
    result_sha256: str = ""
    proof_refs: tuple[str, ...] = ()
    reason: str = ""
    provider_effect_authorized: bool = False
    financial_effect_authorized: bool = False
    publication_authorized: bool = False


def compile_mission_result_identity(
    mission: MissionIR,
    *,
    step_id: str,
    input_identity: Mapping[str, object],
    policy_identity: Mapping[str, object],
    environment_identity: Mapping[str, object],
    proof_scope: str,
    fresh_until: str,
    step_effect_class: str = "NO_EFFECT",
) -> MissionResultIdentity:
    """Compile one deterministic MissionIR step into the existing result-cache identity.

    The adapter is intentionally step-scoped. A mission may itself be READ_ONLY or
    effectful, but only deterministic NO_EFFECT steps are eligible for reuse here.
    Provider reads/effects and persistent cache semantics remain outside this adapter.
    """

    normalized = mission.normalized()
    normalized.validate()
    step = str(step_id).strip()
    scope = str(proof_scope).strip()
    if not step or not scope:
        raise ValueError("MISSION_RESULT_IDENTITY_REQUIRED")
    if str(step_effect_class).strip().upper() != "NO_EFFECT":
        raise ValueError("MISSION_RESULT_STEP_EFFECT_PROHIBITED")

    mission_sha = normalized.digest()
    source_sha = _digest({"source_frontier": normalized.source_frontier})
    input_sha = _digest(
        {
            "mission_ir_sha256": mission_sha,
            "step_id": step,
            "input_identity": dict(input_identity),
        }
    )
    policy_sha = _digest(dict(policy_identity))
    environment_sha = _digest(
        {
            "environment_identity": dict(environment_identity),
            "policy_sha256": policy_sha,
        }
    )
    action = DeterministicAction(
        action=f"MISSIONIR:{normalized.mission_id}:{step}",
        source_sha256=source_sha,
        input_sha256=input_sha,
        environment_sha256=environment_sha,
        proof_scope=scope,
        fresh_until=str(fresh_until).strip(),
        effect_class="NO_EFFECT",
    )
    return MissionResultIdentity(
        schema=_SCHEMA,
        mission_id=normalized.mission_id,
        mission_ir_sha256=mission_sha,
        step_id=step,
        source_sha256=source_sha,
        input_sha256=input_sha,
        policy_sha256=policy_sha,
        environment_sha256=environment_sha,
        proof_scope=scope,
        fresh_until=str(fresh_until).strip(),
        cache_key=action.cache_key(),
    )


def lookup_mission_result(
    cache: DeterministicResultCache,
    identity: MissionResultIdentity,
    *,
    now: str,
) -> MissionResultLookupReceipt:
    action = identity.deterministic_action()
    try:
        decision: CacheDecision = cache.lookup(action, now=now)
    except ValueError as exc:
        if str(exc) == "DETERMINISTIC_ACTION_FRESHNESS_EXPIRED":
            return MissionResultLookupReceipt(
                state="HOLD_FRESHNESS_EXPIRED",
                reuse=False,
                mission_id=identity.mission_id,
                step_id=identity.step_id,
                cache_key=identity.cache_key,
                reason="Result identity lease expired; re-page/recompute before reuse.",
            )
        raise
    return MissionResultLookupReceipt(
        state=decision.state,
        reuse=decision.reuse,
        mission_id=identity.mission_id,
        step_id=identity.step_id,
        cache_key=decision.cache_key,
        result_ref=decision.result_ref,
        result_sha256=decision.result_sha256,
        proof_refs=decision.proof_refs,
        reason=decision.reason,
    )


def record_mission_result(
    cache: DeterministicResultCache,
    identity: MissionResultIdentity,
    *,
    result_ref: str,
    result_sha256: str,
    proof_refs: tuple[str, ...],
    recorded_at: str,
    now: str,
) -> MissionResultLookupReceipt:
    decision = cache.record(
        identity.deterministic_action(),
        result_ref=result_ref,
        result_sha256=result_sha256,
        proof_refs=proof_refs,
        recorded_at=recorded_at,
        now=now,
    )
    return MissionResultLookupReceipt(
        state=decision.state,
        reuse=decision.reuse,
        mission_id=identity.mission_id,
        step_id=identity.step_id,
        cache_key=decision.cache_key,
        result_ref=decision.result_ref,
        result_sha256=decision.result_sha256,
        proof_refs=decision.proof_refs,
        reason=decision.reason,
    )
