from __future__ import annotations

"""Deterministic registry for prospective owner-value observations.

The registry opens collection slots. It never invents a task result, records a
measurement, authenticates evidence, proves owner value, or promotes a candidate.
"""

from argparse import ArgumentParser
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarking.cfbe_omega.value_foundry_v1 import canonical_hash


SCHEMA = "CFBE-PROSPECTIVE-OWNER-VALUE-COHORT-V1"
DEFAULT_MINIMUM_PAIRS = 10


@dataclass(frozen=True, slots=True)
class ProspectiveObservationSlot:
    slot_id: str
    pair_id: str
    task_oracle_id: str
    task_class: str
    baseline_observation_id: str
    candidate_observation_id: str
    status: str
    real_observation_required: bool
    synthetic_observation_allowed: bool
    shadow_observation_allowed: bool
    baseline_received: bool
    candidate_received: bool
    pair_compiled: bool


@dataclass(frozen=True, slots=True)
class ProspectiveCohortManifest:
    schema: str
    cohort_id: str
    champion_id: str
    candidate_id: str
    source_head_sha: str
    registered_at: str
    minimum_owner_value_pairs: int
    state: str
    slots: tuple[ProspectiveObservationSlot, ...]
    observed_baseline_count: int
    observed_candidate_count: int
    compiled_pair_count: int
    owner_value_proven: bool
    provider_deployment_proven: bool
    stable_promotion_allowed: bool
    provider_effect_authorized: bool
    external_effect: bool
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _valid_git_sha(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdef" for character in value.lower())


def _unsigned_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "receipt_sha256"}


def initialize_prospective_cohort(
    *,
    cohort_id: str,
    champion_id: str,
    candidate_id: str,
    source_head_sha: str,
    registered_at: str,
    task_oracles: Sequence[Mapping[str, str]],
    minimum_owner_value_pairs: int = DEFAULT_MINIMUM_PAIRS,
) -> ProspectiveCohortManifest:
    identities = tuple(value.strip() for value in (cohort_id, champion_id, candidate_id, registered_at))
    if any(not value for value in identities):
        raise ValueError("COHORT_IDENTITY_FIELDS_REQUIRED")
    if champion_id == candidate_id:
        raise ValueError("COHORT_DISTINCT_CHAMPION_AND_CANDIDATE_REQUIRED")
    source_head_sha = source_head_sha.strip().lower()
    if not _valid_git_sha(source_head_sha):
        raise ValueError("COHORT_SOURCE_HEAD_INVALID")
    if minimum_owner_value_pairs != DEFAULT_MINIMUM_PAIRS:
        raise ValueError("COHORT_MINIMUM_MUST_REMAIN_TEN")
    if len(task_oracles) != minimum_owner_value_pairs:
        raise ValueError("COHORT_REQUIRES_EXACTLY_TEN_TASK_ORACLES")

    normalized: list[tuple[str, str]] = []
    for raw in task_oracles:
        oracle_id = str(raw.get("task_oracle_id") or "").strip()
        task_class = str(raw.get("task_class") or "").strip()
        if not oracle_id or not task_class:
            raise ValueError("COHORT_TASK_ORACLE_FIELDS_REQUIRED")
        normalized.append((oracle_id, task_class))
    if len({item[0] for item in normalized}) != len(normalized):
        raise ValueError("COHORT_TASK_ORACLE_ID_DUPLICATE")
    if len({item[1] for item in normalized}) != len(normalized):
        raise ValueError("COHORT_TASK_CLASS_DUPLICATE")

    slots = tuple(
        ProspectiveObservationSlot(
            slot_id=f"{cohort_id}-SLOT-{index:02d}",
            pair_id=f"{cohort_id}-PAIR-{index:02d}",
            task_oracle_id=oracle_id,
            task_class=task_class,
            baseline_observation_id=f"{cohort_id}-PAIR-{index:02d}-BASELINE",
            candidate_observation_id=f"{cohort_id}-PAIR-{index:02d}-BUBBLES",
            status="AWAITING_PROSPECTIVE_PAIR",
            real_observation_required=True,
            synthetic_observation_allowed=False,
            shadow_observation_allowed=False,
            baseline_received=False,
            candidate_received=False,
            pair_compiled=False,
        )
        for index, (oracle_id, task_class) in enumerate(normalized, start=1)
    )
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "cohort_id": cohort_id,
        "champion_id": champion_id,
        "candidate_id": candidate_id,
        "source_head_sha": source_head_sha,
        "registered_at": registered_at,
        "minimum_owner_value_pairs": minimum_owner_value_pairs,
        "state": "REGISTERED_AWAITING_PROSPECTIVE_OBSERVATIONS",
        "slots": tuple(asdict(slot) for slot in slots),
        "observed_baseline_count": 0,
        "observed_candidate_count": 0,
        "compiled_pair_count": 0,
        "owner_value_proven": False,
        "provider_deployment_proven": False,
        "stable_promotion_allowed": False,
        "provider_effect_authorized": False,
        "external_effect": False,
        "truth_boundary": (
            "Registration opens collection slots; it is not an owner-value observation.",
            "Every slot requires a later real matched BASELINE/BUBBLES pair from its bound task oracle.",
            "Synthetic, shadow, replayed or invented observations cannot satisfy this cohort.",
            "Collected records remain inadmissible until Value Foundry resolves their trusted evidence receipts.",
            "Cohort completion cannot self-promote, deploy, authorize provider effects or claim market superiority.",
        ),
    }
    receipt = canonical_hash(payload)
    return ProspectiveCohortManifest(
        **{key: value for key, value in payload.items() if key != "slots"},
        slots=slots,
        receipt_sha256=receipt,
    )


def validate_cohort_manifest(payload: Mapping[str, Any]) -> None:
    failures: list[str] = []
    if payload.get("schema") != SCHEMA:
        failures.append("COHORT_SCHEMA_INVALID")
    if payload.get("state") != "REGISTERED_AWAITING_PROSPECTIVE_OBSERVATIONS":
        failures.append("COHORT_STATE_INVALID")
    if not _valid_git_sha(str(payload.get("source_head_sha") or "")):
        failures.append("COHORT_SOURCE_HEAD_INVALID")
    slots = payload.get("slots")
    if not isinstance(slots, (list, tuple)) or len(slots) != DEFAULT_MINIMUM_PAIRS:
        failures.append("COHORT_SLOT_COUNT_INVALID")
        slots = []
    slot_ids = {str(item.get("slot_id") or "") for item in slots if isinstance(item, Mapping)}
    pair_ids = {str(item.get("pair_id") or "") for item in slots if isinstance(item, Mapping)}
    oracle_ids = {str(item.get("task_oracle_id") or "") for item in slots if isinstance(item, Mapping)}
    if min(len(slot_ids), len(pair_ids), len(oracle_ids)) != DEFAULT_MINIMUM_PAIRS:
        failures.append("COHORT_SLOT_IDENTITY_INVALID")
    for item in slots:
        if not isinstance(item, Mapping):
            failures.append("COHORT_SLOT_INVALID")
            continue
        if item.get("real_observation_required") is not True:
            failures.append("COHORT_REAL_OBSERVATION_REQUIRED")
        if item.get("synthetic_observation_allowed") is not False:
            failures.append("COHORT_SYNTHETIC_OBSERVATION_PROHIBITED")
        if item.get("shadow_observation_allowed") is not False:
            failures.append("COHORT_SHADOW_OBSERVATION_PROHIBITED")
        if any(item.get(key) is not False for key in ("baseline_received", "candidate_received", "pair_compiled")):
            failures.append("COHORT_INITIAL_OBSERVATION_STATE_INVALID")
    for key in ("observed_baseline_count", "observed_candidate_count", "compiled_pair_count"):
        if payload.get(key) != 0:
            failures.append("COHORT_INITIAL_COUNT_INVALID")
    for key in (
        "owner_value_proven",
        "provider_deployment_proven",
        "stable_promotion_allowed",
        "provider_effect_authorized",
        "external_effect",
    ):
        if payload.get(key) is not False:
            failures.append("COHORT_TRUTH_BOUNDARY_INVALID")
    if payload.get("receipt_sha256") != canonical_hash(_unsigned_manifest(payload)):
        failures.append("COHORT_RECEIPT_HASH_MISMATCH")
    if failures:
        raise ValueError("|".join(sorted(set(failures))))


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.input.read_text(encoding="utf-8"))
    manifest = initialize_prospective_cohort(**request).to_dict()
    validate_cohort_manifest(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
