from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Mapping


QUEUE_ALIAS = "FO_GAS_AUTHORITY_GATEWAY_PRIVATE_V2"
INBOX_ALIAS = "FO_GAS_GATEWAY_INBOX"
COMMAND_SCHEMA = "BUBBLES-KDV-PRIVATE-QUEUE-COMMAND-V1"
RECEIPT_SCHEMA = "BUBBLES-KDV-PRIVATE-QUEUE-RECEIPT-V1"
APPROVAL_ERROR = "APPROVAL_KEY_REQUIRED_OR_INVALID"


class PrivateQueueError(ValueError):
    pass


@dataclass(frozen=True)
class PrivateQueueRequest:
    command_id: str
    created_at: str
    command: str
    target: str = ""
    payload: Mapping[str, object] = field(default_factory=dict)
    dry_run: bool = True
    risk: str = "LOW"
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.command_id.strip():
            raise PrivateQueueError("command_id is required")
        if not self.created_at.strip():
            raise PrivateQueueError("created_at is required")
        if not self.command.strip():
            raise PrivateQueueError("command is required")
        if self.risk not in {"LOW", "MEDIUM", "HIGH", "P0"}:
            raise PrivateQueueError(f"Unsupported risk: {self.risk}")


@dataclass(frozen=True)
class PrivateQueueDecision:
    state: str
    command_id: str
    queue_state: str
    reason: str
    processed_at: str = ""
    result: Mapping[str, object] = field(default_factory=dict)
    retry_allowed: bool = False


def _reject_secret_fields(value: object) -> None:
    secret_markers = (
        "approvalkey",
        "approval_key",
        "password",
        "secret",
        "private_key",
        "access_token",
        "refresh_token",
        "api_key",
        "authorization",
        "credential",
    )
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in secret_markers):
                raise PrivateQueueError(
                    "Secret or approval-bearing fields are prohibited in Bubbles private-queue payloads"
                )
            _reject_secret_fields(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_secret_fields(child)


def build_queue_row(request: PrivateQueueRequest) -> tuple[object, ...]:
    """Return the 12-column FO-GAS inbox row without any approval material.

    The adapter deliberately leaves the approval column blank. A provider-side
    approval requirement becomes AUTHORITY_HELD on readback; Bubbles must never
    retrieve, infer, replay, or persist a raw gateway approval value.
    """

    _reject_secret_fields(request.payload)
    if request.command == "GAS_SELFTEST":
        if not request.dry_run:
            raise PrivateQueueError("GAS_SELFTEST must be dry-run in the Bubbles adapter")
        if request.risk != "LOW":
            raise PrivateQueueError("GAS_SELFTEST must use LOW risk in the Bubbles adapter")
        if request.target:
            raise PrivateQueueError("GAS_SELFTEST must not have an external target")

    payload_json = json.dumps(dict(request.payload), sort_keys=True, separators=(",", ":"))
    row: tuple[object, ...] = (
        request.command_id,
        request.created_at,
        "PENDING",
        request.command,
        request.target,
        payload_json,
        "",  # approvalKey: intentionally blank and never populated by Bubbles
        request.dry_run,
        request.risk,
        "",  # resultJson
        "",  # processedAt
        request.notes,
    )
    return row


def command_fingerprint(request: PrivateQueueRequest) -> str:
    row = build_queue_row(request)
    canonical = json.dumps(row, sort_keys=False, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def interpret_queue_row(row: list[object] | tuple[object, ...]) -> PrivateQueueDecision:
    if len(row) < 12:
        raise PrivateQueueError("FO-GAS readback row must contain 12 columns")

    command_id = str(row[0] or "")
    queue_state = str(row[2] or "").upper()
    result_raw = row[9] if len(row) > 9 else ""
    processed_at = str(row[10] or "") if len(row) > 10 else ""

    result: dict[str, object] = {}
    if result_raw:
        if isinstance(result_raw, Mapping):
            result = dict(result_raw)
        else:
            try:
                parsed = json.loads(str(result_raw))
            except json.JSONDecodeError as exc:
                raise PrivateQueueError("FO-GAS resultJson is not valid JSON") from exc
            if isinstance(parsed, Mapping):
                result = dict(parsed)

    if queue_state in {"PENDING", "QUEUED", "READY"}:
        return PrivateQueueDecision(
            state="PENDING",
            command_id=command_id,
            queue_state=queue_state,
            reason="Command is awaiting private gateway processing.",
            processed_at=processed_at,
            result=result,
            retry_allowed=False,
        )

    error = str(result.get("error", ""))
    if queue_state in {"ERROR", "FAILED"} and error == APPROVAL_ERROR:
        return PrivateQueueDecision(
            state="AUTHORITY_HELD",
            command_id=command_id,
            queue_state=queue_state,
            reason=(
                "FO-GAS processor is live and rejected the command at its approval gate. "
                "Do not retry with a raw approval key; resolve through an opaque provider-side permit route."
            ),
            processed_at=processed_at,
            result=result,
            retry_allowed=False,
        )

    if queue_state in {"ERROR", "FAILED"}:
        return PrivateQueueDecision(
            state="FAILURE",
            command_id=command_id,
            queue_state=queue_state,
            reason=error or "FO-GAS returned an execution failure.",
            processed_at=processed_at,
            result=result,
            retry_allowed=False,
        )

    if queue_state == "DONE":
        result_status = str(result.get("status", "")).upper()
        if result_status not in {"OK", "SUCCESS", "DONE"}:
            return PrivateQueueDecision(
                state="PROOF_FAILED",
                command_id=command_id,
                queue_state=queue_state,
                reason="Queue row is DONE but resultJson does not carry a successful semantic status.",
                processed_at=processed_at,
                result=result,
                retry_allowed=False,
            )
        if not processed_at:
            return PrivateQueueDecision(
                state="PROOF_FAILED",
                command_id=command_id,
                queue_state=queue_state,
                reason="Queue row is DONE but processedAt readback is missing.",
                result=result,
                retry_allowed=False,
            )
        return PrivateQueueDecision(
            state="SUCCESS",
            command_id=command_id,
            queue_state=queue_state,
            reason="Private gateway processing and semantic readback succeeded.",
            processed_at=processed_at,
            result=result,
            retry_allowed=False,
        )

    return PrivateQueueDecision(
        state="CONSTRAINT",
        command_id=command_id,
        queue_state=queue_state,
        reason=f"Unsupported FO-GAS queue state: {queue_state!r}",
        processed_at=processed_at,
        result=result,
        retry_allowed=False,
    )


def proof_receipt(
    request: PrivateQueueRequest,
    readback_row: list[object] | tuple[object, ...],
) -> dict[str, object]:
    decision = interpret_queue_row(readback_row)
    return {
        "schema": RECEIPT_SCHEMA,
        "adapter": QUEUE_ALIAS,
        "inbox": INBOX_ALIAS,
        "command_id": request.command_id,
        "command_fingerprint": command_fingerprint(request),
        "state": decision.state,
        "queue_state": decision.queue_state,
        "processed_at": decision.processed_at,
        "reason": decision.reason,
        "retry_allowed": decision.retry_allowed,
        "result": dict(decision.result),
        "truth_boundary": (
            "This receipt proves only the supplied Drive-backed FO-GAS row and its readback. "
            "It never proves broader Google Cloud, Apps Script API, deployment, or mutation authority. "
            "Raw approval values are outside the adapter contract."
        ),
    }
