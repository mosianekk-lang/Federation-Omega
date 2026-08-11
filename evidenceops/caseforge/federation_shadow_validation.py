from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping, Sequence

from .federation_autonomous_controller import AutonomousRegressionPlanner
from .federation_evolution_program import AUTHORITY_CEILING, SYSTEM_PROFILES


SHADOW_VALIDATOR_VERSION = "1.0.1"


@dataclass(frozen=True)
class ShadowIncident:
    fingerprint: str
    observed_incident: str
    historical_success_code: str
    repair_proof_ref: str

    def validate(self) -> "ShadowIncident":
        if not all(
            str(value).strip()
            for value in (
                self.fingerprint,
                self.observed_incident,
                self.historical_success_code,
                self.repair_proof_ref,
            )
        ):
            raise ValueError("shadow incident is incomplete")
        return self


@dataclass(frozen=True)
class ShadowReplay:
    fingerprint: str
    predicted_repair_code: str
    historical_success_code: str
    matched: bool
    expected_behavior: str
    prohibited_behavior: str
    repair_proof_ref: str
    policy_source: str
    external_effect: bool = False


@dataclass(frozen=True)
class ShadowValidationReceipt:
    system_id: str
    validator_version: str
    source_commit: str
    replay_count: int
    matched_count: int
    status: str
    failed_fingerprints: tuple[str, ...]
    receipt_sha256: str
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False


class ShadowRegressionPlanner(AutonomousRegressionPlanner):
    """Stricter shadow planner incorporating real learned governance failures."""

    learned_behavior_map: Mapping[str, tuple[str, str]] = {
        "CONTROLLER_SOURCE_ADMISSION_DRIFT": (
            "preserve the drift, close or abandon the stale candidate, recut from fresh current main, reapply only the bounded delta, rerun Airlock/Leak Guard and independently read back main",
            "force the stale branch, overwrite newer main, or treat prior admission as current proof",
        ),
        "SCHEDULED_ATTESTATION_WITHOUT_EXECUTION_PROOF": (
            "quarantine the unsupported attestation, reverse any premature maturity promotion, and require an actual qualifying runtime iteration with fresh bootstrap/current-main/private/twin readback",
            "infer runtime execution from a scheduler title, planned time, invocation label, private row, or controller source existence",
        ),
        "RECEIPT_BINDING_DRIFT": (
            "read back the exact provider-persisted replay fields, canonicalize those exact bound fields, recompute the receipt digest, supersede any preliminary digest, and block maturity promotion until the binding is proven",
            "treat semantically equivalent strings, pre-write payloads, or successful persistence alone as proof that a hash-bound receipt matches the persisted state",
        ),
    }

    behavior_map = dict(AutonomousRegressionPlanner.behavior_map) | dict(learned_behavior_map)


class HistoricalShadowValidator:
    """Replay preserved real incidents against the current safe-repair policy.

    A1 internal/no-effect only. Unknown policies and divergences fail closed.
    Receipt generation must use the exact repair-proof strings read back from the
    provider-persisted replay state; semantic equivalence is insufficient.
    """

    repair_code_map: Mapping[str, str] = {
        "INVALID_ARGUMENT_OR_SCHEMA": "DISCOVER_SCHEMA_AND_RETRY_CORRECTED_ROUTE",
        "STALE_BASE_HEAD_REJECTED": "RECUT_CURRENT_MAIN_REAPPLY_DELTA_RERUN",
        "PHOENIX_EXPORT_REGRESSION": "REPAIR_CODE_NOT_GATE_RERUN",
        "CONNECTOR_STATE_STALE": "REPROBE_REFRESH_TWIN",
        "DIAGNOSIS_SUBSTITUTION": "DEFECT_TO_REPAIR_CONTINUE",
        "CONTROLLER_SOURCE_ADMISSION_DRIFT": "RECUT_CURRENT_MAIN_REAPPLY_DELTA_RERUN",
        "SCHEDULED_ATTESTATION_WITHOUT_EXECUTION_PROOF": "QUARANTINE_REVERSE_REQUIRE_ACTUAL_RUNTIME",
        "RECEIPT_BINDING_DRIFT": "READBACK_RECOMPUTE_EXACT_PERSISTED_RECEIPT_BEFORE_PROMOTION",
    }

    def __init__(self) -> None:
        self.planner = ShadowRegressionPlanner()

    @staticmethod
    def _base(fingerprint: str) -> str:
        return str(fingerprint).split(":", 1)[0].strip()

    def replay(self, incident: ShadowIncident) -> ShadowReplay:
        incident.validate()
        base = self._base(incident.fingerprint)
        if base not in self.repair_code_map or base not in self.planner.behavior_map:
            return ShadowReplay(
                fingerprint=incident.fingerprint,
                predicted_repair_code="UNKNOWN_POLICY",
                historical_success_code=incident.historical_success_code,
                matched=False,
                expected_behavior="fail closed and require an explicit learned repair policy",
                prohibited_behavior="silently generalize an unknown failure into a maturity pass",
                repair_proof_ref=incident.repair_proof_ref,
                policy_source="UNRESOLVED",
            )
        expected, prohibited = self.planner.behavior_map[base]
        predicted = self.repair_code_map[base]
        return ShadowReplay(
            fingerprint=incident.fingerprint,
            predicted_repair_code=predicted,
            historical_success_code=incident.historical_success_code,
            matched=predicted == incident.historical_success_code,
            expected_behavior=expected,
            prohibited_behavior=prohibited,
            repair_proof_ref=incident.repair_proof_ref,
            policy_source=(
                "SHADOW_LEARNED_EXTENSION"
                if base in ShadowRegressionPlanner.learned_behavior_map
                else "AUTONOMOUS_REGRESSION_PLANNER"
            ),
        )

    def canonical_receipt_body(
        self,
        *,
        system_id: str,
        source_commit: str,
        replays: Sequence[ShadowReplay],
        status: str,
    ) -> dict[str, object]:
        return {
            "system_id": system_id,
            "validator_version": SHADOW_VALIDATOR_VERSION,
            "source_commit": source_commit,
            "authority_ceiling": AUTHORITY_CEILING,
            "external_effect": False,
            "status": status,
            "replays": [
                {
                    "fingerprint": replay.fingerprint,
                    "predicted_repair_code": replay.predicted_repair_code,
                    "historical_success_code": replay.historical_success_code,
                    "matched": replay.matched,
                    "repair_proof_ref": replay.repair_proof_ref,
                    "policy_source": replay.policy_source,
                }
                for replay in replays
            ],
        }

    def receipt_digest_from_persisted_replays(
        self,
        *,
        system_id: str,
        source_commit: str,
        replays: Sequence[ShadowReplay],
        status: str,
    ) -> str:
        body = self.canonical_receipt_body(
            system_id=system_id,
            source_commit=source_commit,
            replays=replays,
            status=status,
        )
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(canonical).hexdigest()

    def validate_suite(
        self,
        *,
        system_id: str,
        source_commit: str,
        incidents: Sequence[ShadowIncident],
    ) -> tuple[tuple[ShadowReplay, ...], ShadowValidationReceipt]:
        if system_id not in SYSTEM_PROFILES:
            raise ValueError("shadow validation system must be registered")
        if not str(source_commit).strip():
            raise ValueError("source_commit is required")
        if not incidents:
            raise ValueError("shadow validation requires at least one real incident")

        replays = tuple(self.replay(incident) for incident in incidents)
        matched_count = sum(1 for replay in replays if replay.matched)
        failed = tuple(sorted(replay.fingerprint for replay in replays if not replay.matched))
        status = "PASS" if matched_count == len(replays) and not failed else "FAIL"
        receipt = ShadowValidationReceipt(
            system_id=system_id,
            validator_version=SHADOW_VALIDATOR_VERSION,
            source_commit=source_commit,
            replay_count=len(replays),
            matched_count=matched_count,
            status=status,
            failed_fingerprints=failed,
            receipt_sha256=self.receipt_digest_from_persisted_replays(
                system_id=system_id,
                source_commit=source_commit,
                replays=replays,
                status=status,
            ),
        )
        return replays, receipt


__all__ = [
    "HistoricalShadowValidator",
    "SHADOW_VALIDATOR_VERSION",
    "ShadowIncident",
    "ShadowRegressionPlanner",
    "ShadowReplay",
    "ShadowValidationReceipt",
]
