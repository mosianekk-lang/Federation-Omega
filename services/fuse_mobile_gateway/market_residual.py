from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Literal, Sequence

EffectClass = Literal["NONE", "READ_ONLY", "REVERSIBLE", "CONSEQUENTIAL"]

_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|secret|api[_-]?key|token)\\s*[:=]\\s*\\S+"),
    re.compile(r"\\bsk-[A-Za-z0-9_-]{12,}\\b"),
)


@dataclass(frozen=True, slots=True)
class CarrierSnapshot:
    carrier_id: str
    kind: str
    current: bool
    callable: bool
    authorized: bool
    privacy_ok: bool
    durable: bool
    background_capable: bool
    owner_takeover: bool
    latency_ms: int | None = None
    cost_class: str = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class BrowserTask:
    mission_id: str
    task_id: str
    target: str
    effect_class: EffectClass = "READ_ONLY"
    requires_signed_in_session: bool = False
    requires_background: bool = True
    requires_owner_takeover: bool = True
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class ActionIntent:
    mission_id: str
    task_id: str
    action_id: str
    operation: str
    effect_class: EffectClass
    target_ref: str
    expected_readback: str


@dataclass(frozen=True, slots=True)
class PerceptionFrame:
    mission_id: str
    frame_id: str
    source: str
    accessibility_digest: str
    image_sha256: str | None = None
    fresh: bool = True


@dataclass(frozen=True, slots=True)
class CheckpointRef:
    checkpoint_id: str
    mission_id: str
    task_id: str
    source_epoch: str
    state_sha256: str
    includes_conversation: bool
    includes_artifacts: bool
    includes_task_state: bool
    secret_values_embedded: bool = False


@dataclass(frozen=True, slots=True)
class MarketResult:
    system_id: str
    task_id: str
    environment_id: str
    outcome_score: float
    reliability_score: float
    latency_ms: int
    owner_interventions: int
    proof_strength: float
    privacy_pass: bool
    authority_pass: bool
    source_refs: tuple[str, ...] = field(default_factory=tuple)


def browser_carrier_eligible(task: BrowserTask, carrier: CarrierSnapshot) -> bool:
    if not (carrier.current and carrier.callable and carrier.authorized and carrier.privacy_ok):
        return False
    if task.requires_background and not (carrier.durable and carrier.background_capable):
        return False
    if task.requires_owner_takeover and not carrier.owner_takeover:
        return False
    if task.effect_class == "CONSEQUENTIAL":
        return False
    return True


def choose_browser_carrier(task: BrowserTask, carriers: Sequence[CarrierSnapshot]) -> CarrierSnapshot | None:
    eligible = [carrier for carrier in carriers if browser_carrier_eligible(task, carrier)]
    if not eligible:
        return None

    def score(carrier: CarrierSnapshot) -> tuple[int, int, int, int, str]:
        latency = carrier.latency_ms if carrier.latency_ms is not None else 10**9
        return (
            int(carrier.durable),
            int(carrier.background_capable),
            int(carrier.owner_takeover),
            -latency,
            carrier.carrier_id,
        )

    return max(eligible, key=score)


def browser_route_receipt(task: BrowserTask, carrier: CarrierSnapshot | None) -> dict:
    if carrier is None:
        return {
            "status": "HELD",
            "reason": "NO_QUALIFIED_BROWSER_CARRIER",
            "mission_id": task.mission_id,
            "task_id": task.task_id,
            "authority_expanded": False,
        }
    return {
        "status": "ROUTED",
        "mission_id": task.mission_id,
        "task_id": task.task_id,
        "carrier": asdict(carrier),
        "authority_expanded": False,
        "truth_boundary": "ROUTE_SELECTION_ONLY__NO_BROWSER_EFFECT_EXECUTED",
    }


def prepare_computer_use(perception: PerceptionFrame, intent: ActionIntent, *, authority_granted: bool) -> dict:
    if not perception.fresh:
        return {"status": "HELD", "reason": "STALE_PERCEPTION"}
    if perception.mission_id != intent.mission_id:
        return {"status": "HELD", "reason": "MISSION_MISMATCH"}
    if intent.effect_class == "CONSEQUENTIAL" and not authority_granted:
        return {"status": "HELD", "reason": "ACTION_AUTHORITY_REQUIRED"}
    return {
        "status": "READY",
        "perception": asdict(perception),
        "intent": asdict(intent),
        "requires_post_readback": True,
        "authority_expanded": False,
        "truth_boundary": "PREPARED_ACTION_ONLY__NO_GUI_EFFECT_EXECUTED",
    }


def reconcile_computer_use(intent: ActionIntent, observed_state: str, *, effect_observed: bool) -> dict:
    if observed_state == intent.expected_readback and effect_observed:
        return {"status": "SEMANTIC_SUCCESS", "action_id": intent.action_id, "effect_verified": True}
    if not effect_observed:
        return {"status": "READBACK_REQUIRED", "action_id": intent.action_id, "effect_verified": False}
    return {
        "status": "SEMANTIC_MISMATCH",
        "action_id": intent.action_id,
        "effect_verified": True,
        "observed": observed_state,
        "expected": intent.expected_readback,
    }


def redact_replay_text(text: str) -> str:
    output = text
    for pattern in _SECRET_PATTERNS:
        output = pattern.sub("[REDACTED]", output)
    return output[:4000]


def compile_replay_event(
    *,
    mission_id: str,
    kind: str,
    message: str,
    ref: str = "",
    previous_sha256: str = "0" * 64,
    observed_at: float,
) -> dict:
    payload = {
        "mission_id": mission_id,
        "kind": kind,
        "message": redact_replay_text(message),
        "ref": ref[:1000],
        "observed_at": observed_at,
        "previous_sha256": previous_sha256,
        "truth_boundary": "OWNER_REPLAY_VIEW_ONLY__PERSIST_VIA_EXISTING_CANONICAL_EVENT_OR_ARTIFACT_STORE",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return {**payload, "chain_sha256": hashlib.sha256(canonical).hexdigest()}


def verify_replay_chain(events: Sequence[dict]) -> dict:
    previous = "0" * 64
    for index, event in enumerate(events):
        if event.get("previous_sha256") != previous:
            return {"status": "FAIL", "index": index, "reason": "CHAIN_PREIMAGE_MISMATCH"}
        body = {key: value for key, value in event.items() if key != "chain_sha256"}
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()
        if digest != event.get("chain_sha256"):
            return {"status": "FAIL", "index": index, "reason": "CHAIN_DIGEST_MISMATCH"}
        previous = digest
    return {"status": "PASS", "events": len(events), "head": previous}


def validate_checkpoints(checkpoints: Sequence[CheckpointRef]) -> dict:
    ids: set[str] = set()
    for checkpoint in checkpoints:
        if checkpoint.secret_values_embedded:
            return {"status": "FAIL", "reason": "SECRET_VALUE_EMBEDDED", "checkpoint_id": checkpoint.checkpoint_id}
        if checkpoint.checkpoint_id in ids:
            return {"status": "FAIL", "reason": "DUPLICATE_CHECKPOINT_ID", "checkpoint_id": checkpoint.checkpoint_id}
        ids.add(checkpoint.checkpoint_id)
    return {"status": "PASS", "count": len(checkpoints)}


def selective_restore_plan(
    checkpoints: Sequence[CheckpointRef],
    checkpoint_id: str,
    *,
    conversation: bool = False,
    artifacts: bool = False,
    task_state: bool = True,
) -> dict:
    checkpoint = next((item for item in checkpoints if item.checkpoint_id == checkpoint_id), None)
    if checkpoint is None:
        return {"status": "HELD", "reason": "CHECKPOINT_NOT_FOUND"}
    if checkpoint.secret_values_embedded:
        return {"status": "HELD", "reason": "CHECKPOINT_SECRET_BOUNDARY_FAIL"}
    requested = {"conversation": conversation, "artifacts": artifacts, "task_state": task_state}
    available = {
        "conversation": checkpoint.includes_conversation,
        "artifacts": checkpoint.includes_artifacts,
        "task_state": checkpoint.includes_task_state,
    }
    missing = [key for key, enabled in requested.items() if enabled and not available[key]]
    if missing:
        return {"status": "HELD", "reason": "REQUESTED_STATE_NOT_AVAILABLE", "missing": missing}
    return {
        "status": "RESTORE_PLAN_READY",
        "checkpoint_id": checkpoint_id,
        "restore": requested,
        "source_epoch": checkpoint.source_epoch,
        "state_sha256": checkpoint.state_sha256,
        "authority_expanded": False,
        "truth_boundary": "RESTORE_PLAN_ONLY__PORTABLE_STATE_EXECUTOR_PERFORMS_RESTORE",
    }


def assess_market_results(results: Sequence[MarketResult], *, independent_judge: bool = False) -> dict:
    if not results:
        return {"status": "HELD", "reason": "NO_MATCHED_RESULTS", "market_leadership_proven": False}
    systems = {result.system_id for result in results}
    if len(systems) < 2:
        return {"status": "HELD", "reason": "CHALLENGER_REQUIRED", "market_leadership_proven": False}

    cohorts: dict[tuple[str, str], list[MarketResult]] = {}
    for result in results:
        cohorts.setdefault((result.task_id, result.environment_id), []).append(result)

    for key, cohort in cohorts.items():
        if {result.system_id for result in cohort} != systems:
            return {
                "status": "HELD",
                "reason": "UNMATCHED_COHORT",
                "task_environment": key,
                "market_leadership_proven": False,
            }
        if any(not (result.privacy_pass and result.authority_pass) for result in cohort):
            return {
                "status": "HELD",
                "reason": "HARD_GATE_FAILURE",
                "task_environment": key,
                "market_leadership_proven": False,
            }

    aggregate: dict[str, dict] = {}
    for system_id in sorted(systems):
        cohort = [result for result in results if result.system_id == system_id]
        aggregate[system_id] = {
            "outcome_mean": sum(result.outcome_score for result in cohort) / len(cohort),
            "reliability_mean": sum(result.reliability_score for result in cohort) / len(cohort),
            "latency_mean_ms": sum(result.latency_ms for result in cohort) / len(cohort),
            "owner_interventions_mean": sum(result.owner_interventions for result in cohort) / len(cohort),
            "proof_strength_mean": sum(result.proof_strength for result in cohort) / len(cohort),
            "n": len(cohort),
        }

    return {
        "status": "INDEPENDENT_JUDGE_INPUT_READY" if independent_judge else "MEASURED_MATCHED_COHORT",
        "systems": aggregate,
        "market_leadership_proven": False,
        "truth_boundary": "MEASUREMENTS_ONLY__NO_SELF_CERTIFIED_WINNER",
    }


def market_residual_status() -> dict:
    return {
        "schema": "FUSE-WORKSPACE-MARKET-RESIDUAL-V1",
        "version": "0.5.0",
        "state_roots_added": 0,
        "authority_roots_added": 0,
        "capabilities": [
            "BROWSER_WORKER_ROUTING",
            "COMPUTER_USE_PREPARE_READBACK_COURT",
            "ACTIVITY_REPLAY_PROJECTION",
            "CHECKPOINT_SELECTIVE_RESTORE_PLAN",
            "MATCHED_MARKET_BENCHMARK_MEASUREMENT",
        ],
        "truth_boundary": "CONTROL_AND_PROJECTION_ONLY__NO_LIVE_BROWSER_GUI_RESTORE_OR_MARKET_LEADERSHIP_EFFECT",
    }
