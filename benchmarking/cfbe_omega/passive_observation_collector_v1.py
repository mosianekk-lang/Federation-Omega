from __future__ import annotations

"""Passive, proof-gated observation collection for CFBE Cohort 001.

The collector is an in-process deterministic adapter.  It does not watch a
provider, create observations, infer metrics, deploy a runtime, evaluate owner
value, or promote a candidate.  A caller must supply a real directive or an
already-measured observation together with trusted evidence receipts.
"""

from argparse import ArgumentParser
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from benchmarking.cfbe_omega.prospective_observation_cohort_v1 import (
    validate_cohort_manifest,
)
from benchmarking.cfbe_omega.value_foundry_v1 import (
    TrustedEvidenceResolver,
    canonical_hash,
    record_hash,
)
from federation.sentinel_omega.owner_value_ingress import (
    BASELINE,
    BUBBLES,
    OwnerValueMissionRecord,
    OwnerValuePairCompiler,
)


COLLECTOR_SCHEMA = "CFBE-PASSIVE-OBSERVATION-COLLECTOR-V1"
COLLECTOR_ID = "CFBE-VALUE-FOUNDRY-PASSIVE-COLLECTOR-001"
RUNTIME_STATE = "SOURCE_ADAPTER_READY_NOT_DEPLOYED"


def _git_sha(value: Any, code: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 40 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(code)
    return text


def _required(value: Any, code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(code)
    return text


def _iso(value: Any, code: str) -> str:
    try:
        parsed = datetime.fromisoformat(_required(value, code).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(code) from exc
    if parsed.tzinfo is None:
        raise ValueError(code)
    return parsed.astimezone(timezone.utc).isoformat()


def _proof_refs(value: Any, code: str) -> tuple[str, ...]:
    if isinstance(value, str):
        refs = tuple(sorted({item.strip() for item in value.split(";") if item.strip()}))
    else:
        refs = tuple(sorted({str(item).strip() for item in value or () if str(item).strip()}))
    if not refs:
        raise ValueError(code)
    return refs


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


@dataclass(frozen=True, slots=True)
class DirectiveBinding:
    directive_id: str
    directive_event_sha256: str
    directive_record_sha256: str
    directive_proof_refs: tuple[str, ...]
    resolved_receipt_sha256s: tuple[str, ...]
    observed_at: str
    source_head_sha: str
    task_class: str
    slot_id: str
    pair_id: str
    task_oracle_id: str
    baseline_observation_id: str
    candidate_observation_id: str
    status: str
    pair_ready: bool


@dataclass(frozen=True, slots=True)
class CollectedObservation:
    observation_id: str
    pair_id: str
    variant: str
    observation_event_sha256: str
    observation_record_sha256: str
    canonical_record_json: str
    proof_refs: tuple[str, ...]
    resolved_receipt_sha256s: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CollectorActionReceipt:
    schema: str
    action: str
    collector_id: str
    directive_id: str
    slot_id: str
    pair_id: str
    observation_id: str
    idempotent_replay: bool
    pair_ready: bool
    owner_value_proven: bool
    stable_promotion_allowed: bool
    provider_effect_authorized: bool
    external_effect: bool
    state_receipt_sha256: str
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CollectorState:
    schema: str
    collector_id: str
    cohort_id: str
    cohort_receipt_sha256: str
    source_base_sha: str
    runtime_state: str
    bindings: tuple[DirectiveBinding, ...]
    observations: tuple[CollectedObservation, ...]
    bound_directive_count: int
    collected_observation_count: int
    pair_ready_count: int
    owner_value_proven: bool
    provider_runtime_deployed: bool
    stable_promotion_allowed: bool
    provider_effect_authorized: bool
    external_effect: bool
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CollectorState":
        bindings = tuple(DirectiveBinding(**item) for item in value.get("bindings") or ())
        observations = tuple(CollectedObservation(**item) for item in value.get("observations") or ())
        return cls(
            **{
                key: item
                for key, item in value.items()
                if key not in {"bindings", "observations", "truth_boundary"}
            },
            bindings=bindings,
            observations=observations,
            truth_boundary=tuple(value.get("truth_boundary") or ()),
        )


def canonical_state_hash(value: Mapping[str, Any]) -> str:
    return canonical_hash({key: item for key, item in value.items() if key != "receipt_sha256"})


def _state(
    *,
    cohort_id: str,
    cohort_receipt_sha256: str,
    source_base_sha: str,
    bindings: tuple[DirectiveBinding, ...],
    observations: tuple[CollectedObservation, ...],
) -> CollectorState:
    pair_ready_count = sum(binding.pair_ready for binding in bindings)
    payload: dict[str, Any] = {
        "schema": COLLECTOR_SCHEMA,
        "collector_id": COLLECTOR_ID,
        "cohort_id": cohort_id,
        "cohort_receipt_sha256": cohort_receipt_sha256,
        "source_base_sha": source_base_sha,
        "runtime_state": RUNTIME_STATE,
        "bindings": tuple(asdict(item) for item in bindings),
        "observations": tuple(asdict(item) for item in observations),
        "bound_directive_count": len(bindings),
        "collected_observation_count": len(observations),
        "pair_ready_count": pair_ready_count,
        "owner_value_proven": False,
        "provider_runtime_deployed": False,
        "stable_promotion_allowed": False,
        "provider_effect_authorized": False,
        "external_effect": False,
        "truth_boundary": (
            "This is a passive in-process adapter, not a watcher, scheduler, hook or deployed runtime.",
            "Only real caller-supplied directives and measured observations with trusted receipts can enter state.",
            "Binding and collection do not prove owner value; pair-ready records require separate Value Foundry evaluation.",
            "No state transition can self-promote, deploy, authorize provider effects or claim external effect.",
        ),
    }
    return CollectorState(
        **{key: item for key, item in payload.items() if key not in {"bindings", "observations"}},
        bindings=bindings,
        observations=observations,
        receipt_sha256=canonical_hash(payload),
    )


def initialize_collector(
    cohort_manifest: Mapping[str, Any],
    *,
    source_base_sha: str,
) -> CollectorState:
    validate_cohort_manifest(cohort_manifest)
    state = _state(
        cohort_id=_required(cohort_manifest.get("cohort_id"), "COLLECTOR_COHORT_ID_REQUIRED"),
        cohort_receipt_sha256=_required(
            cohort_manifest.get("receipt_sha256"), "COLLECTOR_COHORT_RECEIPT_REQUIRED"
        ),
        source_base_sha=_git_sha(source_base_sha, "COLLECTOR_SOURCE_BASE_SHA_INVALID"),
        bindings=(),
        observations=(),
    )
    validate_collector_state(state.to_dict())
    return state


def validate_collector_state(value: Mapping[str, Any]) -> None:
    failures: list[str] = []
    if value.get("schema") != COLLECTOR_SCHEMA:
        failures.append("COLLECTOR_STATE_SCHEMA_INVALID")
    if value.get("collector_id") != COLLECTOR_ID:
        failures.append("COLLECTOR_STATE_ID_INVALID")
    try:
        _git_sha(value.get("source_base_sha"), "COLLECTOR_STATE_SOURCE_SHA_INVALID")
    except ValueError as exc:
        failures.append(str(exc))
    if value.get("runtime_state") != RUNTIME_STATE:
        failures.append("COLLECTOR_RUNTIME_STATE_INVALID")
    for key in (
        "owner_value_proven",
        "provider_runtime_deployed",
        "stable_promotion_allowed",
        "provider_effect_authorized",
        "external_effect",
    ):
        if value.get(key) is not False:
            failures.append("COLLECTOR_TRUTH_BOUNDARY_INVALID:" + key)

    bindings = value.get("bindings") or ()
    observations = value.get("observations") or ()
    if not isinstance(bindings, (list, tuple)) or not isinstance(observations, (list, tuple)):
        failures.append("COLLECTOR_STATE_COLLECTIONS_INVALID")
        bindings, observations = (), ()
    directive_ids = [str(item.get("directive_id") or "") for item in bindings]
    slot_ids = [str(item.get("slot_id") or "") for item in bindings]
    pair_ids = [str(item.get("pair_id") or "") for item in bindings]
    observation_ids = [str(item.get("observation_id") or "") for item in observations]
    if len(set(directive_ids)) != len(directive_ids) or "" in directive_ids:
        failures.append("COLLECTOR_DIRECTIVE_ID_DUPLICATE_OR_EMPTY")
    if len(set(slot_ids)) != len(slot_ids) or len(set(pair_ids)) != len(pair_ids):
        failures.append("COLLECTOR_SLOT_OR_PAIR_DUPLICATE")
    if len(set(observation_ids)) != len(observation_ids) or "" in observation_ids:
        failures.append("COLLECTOR_OBSERVATION_ID_DUPLICATE_OR_EMPTY")

    variants_by_pair: dict[str, set[str]] = {}
    for item in observations:
        pair_id = str(item.get("pair_id") or "")
        variants_by_pair.setdefault(pair_id, set()).add(str(item.get("variant") or ""))
        try:
            raw = json.loads(str(item.get("canonical_record_json") or ""))
        except (TypeError, ValueError):
            failures.append("COLLECTOR_OBSERVATION_CANONICAL_JSON_INVALID")
            continue
        if canonical_hash(raw) != item.get("observation_event_sha256"):
            failures.append("COLLECTOR_OBSERVATION_EVENT_HASH_MISMATCH")
        if record_hash(raw) != item.get("observation_record_sha256"):
            failures.append("COLLECTOR_OBSERVATION_RECORD_HASH_MISMATCH")

    ready_count = 0
    for item in bindings:
        variants = variants_by_pair.get(str(item.get("pair_id") or ""), set())
        ready = variants == {BASELINE, BUBBLES}
        if item.get("pair_ready") is not ready:
            failures.append("COLLECTOR_BINDING_PAIR_READY_MISMATCH")
        expected_status = (
            "PAIR_READY_FOR_SEPARATE_FOUNDRY_EVALUATION"
            if ready
            else "BOUND_AWAITING_TRUSTED_PAIR"
        )
        if item.get("status") != expected_status:
            failures.append("COLLECTOR_BINDING_STATUS_INVALID")
        ready_count += int(ready)
    if any(pair_id not in set(pair_ids) for pair_id in variants_by_pair):
        failures.append("COLLECTOR_ORPHAN_OBSERVATION")
    if value.get("bound_directive_count") != len(bindings):
        failures.append("COLLECTOR_BOUND_COUNT_MISMATCH")
    if value.get("collected_observation_count") != len(observations):
        failures.append("COLLECTOR_OBSERVATION_COUNT_MISMATCH")
    if value.get("pair_ready_count") != ready_count:
        failures.append("COLLECTOR_PAIR_READY_COUNT_MISMATCH")
    if value.get("receipt_sha256") != canonical_state_hash(value):
        failures.append("COLLECTOR_STATE_RECEIPT_HASH_MISMATCH")
    if failures:
        raise ValueError("|".join(sorted(set(failures))))


def _receipt(
    *,
    action: str,
    state: CollectorState,
    binding: DirectiveBinding,
    observation_id: str = "",
    idempotent_replay: bool = False,
) -> CollectorActionReceipt:
    payload = {
        "schema": COLLECTOR_SCHEMA + "-ACTION-RECEIPT",
        "action": action,
        "collector_id": state.collector_id,
        "directive_id": binding.directive_id,
        "slot_id": binding.slot_id,
        "pair_id": binding.pair_id,
        "observation_id": observation_id,
        "idempotent_replay": idempotent_replay,
        "pair_ready": binding.pair_ready,
        "owner_value_proven": False,
        "stable_promotion_allowed": False,
        "provider_effect_authorized": False,
        "external_effect": False,
        "state_receipt_sha256": state.receipt_sha256,
    }
    return CollectorActionReceipt(**payload, receipt_sha256=canonical_hash(payload))


def bind_eligible_directive(
    state: CollectorState,
    cohort_manifest: Mapping[str, Any],
    directive_event: Mapping[str, Any],
    *,
    evidence_registry: Mapping[str, Mapping[str, Any]],
    trusted_verifiers: Iterable[str],
) -> tuple[CollectorState, CollectorActionReceipt]:
    validate_collector_state(state.to_dict())
    validate_cohort_manifest(cohort_manifest)
    if state.cohort_id != cohort_manifest.get("cohort_id"):
        raise ValueError("COLLECTOR_COHORT_ID_MISMATCH")
    if state.cohort_receipt_sha256 != cohort_manifest.get("receipt_sha256"):
        raise ValueError("COLLECTOR_COHORT_RECEIPT_MISMATCH")

    directive_id = _required(directive_event.get("directive_id"), "COLLECTOR_DIRECTIVE_ID_REQUIRED")
    task_class = _required(directive_event.get("task_class"), "COLLECTOR_TASK_CLASS_REQUIRED")
    source_head_sha = _git_sha(
        directive_event.get("source_head_sha"), "COLLECTOR_DIRECTIVE_SOURCE_SHA_INVALID"
    )
    collector_source_epoch = _git_sha(
        state.source_base_sha, "COLLECTOR_SOURCE_EPOCH_INVALID"
    )
    if source_head_sha != collector_source_epoch:
        raise ValueError("COLLECTOR_DIRECTIVE_SOURCE_EPOCH_MISMATCH")
    observed_at = _iso(directive_event.get("observed_at"), "COLLECTOR_DIRECTIVE_TIMESTAMP_INVALID")
    if directive_event.get("real_directive") is not True:
        raise ValueError("COLLECTOR_REAL_DIRECTIVE_REQUIRED")
    for field in ("synthetic", "shadow", "replayed"):
        if directive_event.get(field) is not False:
            raise ValueError("COLLECTOR_" + field.upper() + "_DIRECTIVE_PROHIBITED")
    refs = _proof_refs(directive_event.get("proof_refs"), "COLLECTOR_DIRECTIVE_PROOF_REQUIRED")
    event_hash = canonical_hash(directive_event)
    record_sha = record_hash(directive_event)

    existing = next((item for item in state.bindings if item.directive_id == directive_id), None)
    if existing is not None:
        if existing.directive_event_sha256 != event_hash:
            raise ValueError("COLLECTOR_DIRECTIVE_REPLAY_CONFLICT")
        return state, _receipt(
            action="BIND_DIRECTIVE", state=state, binding=existing, idempotent_replay=True
        )

    resolver = TrustedEvidenceResolver(evidence_registry, trusted_verifiers)
    receipt_hashes: list[str] = []
    for reference in refs:
        resolved = resolver.resolve(
            reference,
            subject=f"directive:{directive_id}",
            source_head_sha=source_head_sha,
            expected_record_sha256=record_sha,
        )
        receipt_hashes.append(resolved.receipt_sha256)

    occupied_slots = {item.slot_id for item in state.bindings}
    compatible = [
        item
        for item in cohort_manifest.get("slots") or ()
        if item.get("task_class") == task_class and item.get("slot_id") not in occupied_slots
    ]
    if not compatible:
        raise ValueError("COLLECTOR_NO_COMPATIBLE_EMPTY_SLOT")
    slot = sorted(compatible, key=lambda item: str(item.get("slot_id") or ""))[0]
    if (
        slot.get("real_observation_required") is not True
        or slot.get("synthetic_observation_allowed") is not False
        or slot.get("shadow_observation_allowed") is not False
        or any(slot.get(key) is not False for key in ("baseline_received", "candidate_received", "pair_compiled"))
    ):
        raise ValueError("COLLECTOR_SLOT_NOT_EMPTY_OR_REAL_ONLY")

    binding = DirectiveBinding(
        directive_id=directive_id,
        directive_event_sha256=event_hash,
        directive_record_sha256=record_sha,
        directive_proof_refs=refs,
        resolved_receipt_sha256s=tuple(sorted(receipt_hashes)),
        observed_at=observed_at,
        source_head_sha=source_head_sha,
        task_class=task_class,
        slot_id=_required(slot.get("slot_id"), "COLLECTOR_SLOT_ID_REQUIRED"),
        pair_id=_required(slot.get("pair_id"), "COLLECTOR_PAIR_ID_REQUIRED"),
        task_oracle_id=_required(slot.get("task_oracle_id"), "COLLECTOR_ORACLE_ID_REQUIRED"),
        baseline_observation_id=_required(
            slot.get("baseline_observation_id"), "COLLECTOR_BASELINE_ID_REQUIRED"
        ),
        candidate_observation_id=_required(
            slot.get("candidate_observation_id"), "COLLECTOR_CANDIDATE_ID_REQUIRED"
        ),
        status="BOUND_AWAITING_TRUSTED_PAIR",
        pair_ready=False,
    )
    updated = _state(
        cohort_id=state.cohort_id,
        cohort_receipt_sha256=state.cohort_receipt_sha256,
        source_base_sha=state.source_base_sha,
        bindings=tuple(sorted(state.bindings + (binding,), key=lambda item: item.slot_id)),
        observations=state.observations,
    )
    validate_collector_state(updated.to_dict())
    return updated, _receipt(action="BIND_DIRECTIVE", state=updated, binding=binding)


def ingest_owner_value_observation(
    state: CollectorState,
    observation: Mapping[str, Any],
    *,
    evidence_registry: Mapping[str, Mapping[str, Any]],
    trusted_verifiers: Iterable[str],
) -> tuple[CollectorState, CollectorActionReceipt]:
    validate_collector_state(state.to_dict())
    if observation.get("real_observation") is not True:
        raise ValueError("COLLECTOR_REAL_OBSERVATION_REQUIRED")
    for field in ("synthetic", "shadow", "replayed"):
        if observation.get(field) is not False:
            raise ValueError("COLLECTOR_" + field.upper() + "_OBSERVATION_PROHIBITED")
    item = OwnerValueMissionRecord.from_mapping(observation)
    binding = next((value for value in state.bindings if value.pair_id == item.pair_id), None)
    if binding is None:
        raise ValueError("COLLECTOR_OBSERVATION_WITHOUT_BINDING")
    expected_observation_id = (
        binding.baseline_observation_id if item.variant == BASELINE else binding.candidate_observation_id
    )
    identity_failures = []
    if item.observation_id != expected_observation_id:
        identity_failures.append("OBSERVATION_ID_MISMATCH")
    if item.mission_id != binding.directive_id:
        identity_failures.append("DIRECTIVE_ID_MISMATCH")
    if item.mission_class != binding.task_class:
        identity_failures.append("TASK_CLASS_MISMATCH")
    if item.oracle_id != binding.task_oracle_id:
        identity_failures.append("ORACLE_MISMATCH")
    if item.source_head_sha != binding.source_head_sha:
        identity_failures.append("SOURCE_HEAD_MISMATCH")
    if identity_failures:
        raise ValueError("COLLECTOR_" + "|COLLECTOR_".join(sorted(identity_failures)))

    event_hash = canonical_hash(observation)
    existing = next(
        (value for value in state.observations if value.observation_id == item.observation_id),
        None,
    )
    if existing is not None:
        if existing.observation_event_sha256 != event_hash:
            raise ValueError("COLLECTOR_OBSERVATION_REPLAY_CONFLICT")
        return state, _receipt(
            action="INGEST_OBSERVATION",
            state=state,
            binding=binding,
            observation_id=item.observation_id,
            idempotent_replay=True,
        )

    resolver = TrustedEvidenceResolver(evidence_registry, trusted_verifiers)
    receipt_hashes: list[str] = []
    raw_record_sha = record_hash(observation)
    for reference in item.proof_refs:
        resolved = resolver.resolve(
            reference,
            subject=f"owner-value:{item.observation_id}",
            source_head_sha=item.source_head_sha,
            expected_record_sha256=raw_record_sha,
        )
        receipt_hashes.append(resolved.receipt_sha256)
    collected = CollectedObservation(
        observation_id=item.observation_id,
        pair_id=item.pair_id,
        variant=item.variant,
        observation_event_sha256=event_hash,
        observation_record_sha256=raw_record_sha,
        canonical_record_json=_canonical_json(observation),
        proof_refs=item.proof_refs,
        resolved_receipt_sha256s=tuple(sorted(receipt_hashes)),
    )
    observations = tuple(
        sorted(state.observations + (collected,), key=lambda value: value.observation_id)
    )
    pair_records = [
        json.loads(value.canonical_record_json)
        for value in observations
        if value.pair_id == binding.pair_id
    ]
    pair_ready = len(pair_records) == 2
    if pair_ready:
        parsed = tuple(OwnerValueMissionRecord.from_mapping(value) for value in pair_records)
        OwnerValuePairCompiler.compile(*parsed)
    updated_binding = replace(
        binding,
        status=(
            "PAIR_READY_FOR_SEPARATE_FOUNDRY_EVALUATION"
            if pair_ready
            else "BOUND_AWAITING_TRUSTED_PAIR"
        ),
        pair_ready=pair_ready,
    )
    bindings = tuple(
        updated_binding if value.directive_id == binding.directive_id else value
        for value in state.bindings
    )
    updated = _state(
        cohort_id=state.cohort_id,
        cohort_receipt_sha256=state.cohort_receipt_sha256,
        source_base_sha=state.source_base_sha,
        bindings=bindings,
        observations=observations,
    )
    validate_collector_state(updated.to_dict())
    return updated, _receipt(
        action="INGEST_OBSERVATION",
        state=updated,
        binding=updated_binding,
        observation_id=item.observation_id,
    )


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.input.read_text(encoding="utf-8"))
    action = str(request.get("action") or "").lower()
    if action == "initialize":
        state = initialize_collector(
            request["cohort_manifest"], source_base_sha=request["source_base_sha"]
        )
        output = {"state": state.to_dict(), "action_receipt": None}
    else:
        state = CollectorState.from_mapping(request["state"])
        if action == "bind":
            state, receipt = bind_eligible_directive(
                state,
                request["cohort_manifest"],
                request["directive_event"],
                evidence_registry=request.get("evidence_registry") or {},
                trusted_verifiers=request.get("trusted_verifiers") or (),
            )
        elif action == "ingest":
            state, receipt = ingest_owner_value_observation(
                state,
                request["observation"],
                evidence_registry=request.get("evidence_registry") or {},
                trusted_verifiers=request.get("trusted_verifiers") or (),
            )
        else:
            raise ValueError("COLLECTOR_ACTION_INVALID")
        output = {"state": state.to_dict(), "action_receipt": receipt.to_dict()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COLLECTOR_SCHEMA",
    "CollectedObservation",
    "CollectorActionReceipt",
    "CollectorState",
    "DirectiveBinding",
    "bind_eligible_directive",
    "canonical_state_hash",
    "ingest_owner_value_observation",
    "initialize_collector",
    "validate_collector_state",
]
