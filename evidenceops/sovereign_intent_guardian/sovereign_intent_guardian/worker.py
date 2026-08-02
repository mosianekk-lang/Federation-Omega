"""One-shot worker accepting data-only advisory receipts, never executable providers."""

from __future__ import annotations

import re
from typing import Mapping

from .contracts import Verdict
from .policy import evaluate
from .provider import AdvisoryReview, PermanentAdvisoryError, validated_advisory_record
from .store import GuardianStore, LeaseRejected


class GuardianWorker:
    """Local deterministic worker with no tools, callbacks, connectors or provider code."""

    def __init__(
        self,
        store: GuardianStore,
        *,
        worker_id: str,
        boot_id: str,
        advisory_review: AdvisoryReview | None = None,
        lease_seconds: int = 60,
    ):
        self.store = store
        self.worker_id = worker_id
        self.boot_id = boot_id
        self.advisory_review = advisory_review
        self.lease_seconds = lease_seconds

    @property
    def advisory_available(self) -> bool:
        return self.advisory_review is not None

    def start(self, *, now: float | None = None) -> None:
        self.store.register_worker(self.worker_id, self.boot_id, now=now)

    def run_once(self, *, now: float | None = None) -> Mapping[str, Any]:
        lease = self.store.claim_task(
            self.worker_id, self.boot_id, lease_seconds=self.lease_seconds, now=now
        )
        if lease is None:
            return {"state": "IDLE", "effect_performed": False, "release_authority": "NONE"}
        request = lease["request"]
        try:
            self.store.heartbeat(lease, extend_seconds=self.lease_seconds, now=now)
            delivered_count, ledger_hash = self.store.output_snapshot(
                request.mission_id, request.mission_version
            )
            result = evaluate(
                request,
                delivered_output_count=delivered_count,
                output_ledger_hash=ledger_hash,
                output_ledger_verified=True,
                advisory_available=self.advisory_available,
                continuity_attestation_verified=self.store.verify_continuity(request),
            )
            if result.verdict in {Verdict.BLOCK, Verdict.SOVEREIGN_DECISION_REQUIRED}:
                advisory = {
                    "provider_id": "not-consumed",
                    "source_type": "MODEL_ADVISORY_RECEIPT",
                    "authority": "ADVISORY_ONLY",
                    "reason": "DETERMINISTIC_NON_ALIGN",
                }
            elif self.advisory_review is None:
                advisory = {
                    "provider_id": "disabled",
                    "source_type": "MODEL_ADVISORY_RECEIPT",
                    "authority": "ADVISORY_ONLY",
                    "reason": "NO_ADVISORY_RECEIPT",
                }
            else:
                advisory = validated_advisory_record(self.advisory_review)

            result = result.with_advisory(advisory)
            self.store.heartbeat(lease, extend_seconds=self.lease_seconds, now=now)
            result_hash = self.store.complete_task(lease, result, now=now)
            return {
                "state": "COMPLETED",
                "task_id": lease["task_id"],
                "verdict": result.verdict.value,
                "result_hash": result_hash,
                "authorizes_action": False,
                "effect_performed": False,
                "release_authority": "NONE",
            }
        except PermanentAdvisoryError as exc:
            code = str(exc) if re.fullmatch(r"[A-Z][A-Z0-9_]{2,79}", str(exc)) else "ADVISORY_RECEIPT_SCHEMA_INVALID"
            state = self.store.fail_task(lease, reason_code=code, transient=False, now=now)
            return {"state": state, "task_id": lease["task_id"], "reason_code": code}
        except LeaseRejected as exc:
            code = str(exc)
            if code in {
                "RESULT_INPUT_HASH_MISMATCH", "OUTPUT_LEDGER_INVALID",
                "OUTPUT_LEDGER_SNAPSHOT_MISMATCH", "SECRET_LIKE_RESULT_REJECTED",
                "DETERMINISTIC_RESULT_MISMATCH",
            }:
                state = self.store.fail_task(
                    lease, reason_code="SEMANTIC_COMPLETION_REJECTED", transient=False, now=now
                )
                return {
                    "state": state,
                    "task_id": lease["task_id"],
                    "reason_code": "SEMANTIC_COMPLETION_REJECTED",
                }
            raise
        except Exception:
            state = self.store.fail_task(
                lease, reason_code="UNKNOWN_TERMINAL_FAILURE", transient=False, now=now
            )
            return {
                "state": state,
                "task_id": lease["task_id"],
                "reason_code": "UNKNOWN_TERMINAL_FAILURE",
            }
