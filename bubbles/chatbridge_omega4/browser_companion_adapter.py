from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Mapping, Sequence

from .alpha_omega_capture import (
    CaptureObservation,
    CapturePath,
    CapturePathKind,
    CapturePathState,
    ConversationStream,
    StreamExpectation,
)
from .full_fidelity_ledger import (
    ConversationEventType,
    EventExecutionState,
    PayloadAvailability,
)


BROWSER_CAPTURE_SCHEMA = "CHATBRIDGE-ALPHA-OMEGA-BROWSER-CAPTURE-1"
BROWSER_COMPANION_ADAPTER_VERSION = "CHATBRIDGE-BROWSER-COMPANION-INGRESS-1.0"
_DEFAULT_MAX_PAYLOAD_BYTES = 8_000_000
_DEFAULT_MAX_OBSERVATIONS = 10_000
_FORBIDDEN_SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "bearer",
    "connector_token",
    "password",
    "secret",
    "token",
    "x_chatbridge_token",
    "x-chatbridge-token",
}


class BrowserCompanionEnvelopeError(ValueError):
    """A bounded browser-capture envelope failed identity or integrity validation."""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _sha256(value: Any) -> str:
    text = value if isinstance(value, str) else _canonical_json(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BrowserCompanionEnvelopeError(f"{field}_MUST_BE_OBJECT")
    return value


def _require_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise BrowserCompanionEnvelopeError(f"{field}_REQUIRED")
    return text


def _reject_secret_fields(value: Any, *, path: str = "") -> None:
    """Reject transport/auth material, without inspecting governed message text values."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().casefold().replace("-", "_")
            if normalized in {item.replace("-", "_") for item in _FORBIDDEN_SECRET_KEYS}:
                raise BrowserCompanionEnvelopeError(
                    f"SECRET_FIELD_PROHIBITED:{path + '.' if path else ''}{key}"
                )
            _reject_secret_fields(item, path=f"{path}.{key}" if path else str(key))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_secret_fields(item, path=f"{path}[{index}]")


def _browser_payload_hash(observation: Mapping[str, Any]) -> str:
    event_type = str(observation.get("event_type", "OTHER"))
    metadata = observation.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    if event_type == ConversationEventType.TERMINAL_WARNING.value:
        return _sha256(
            {
                "conversation_key": str(observation.get("conversation_key", "")),
                "event_type": event_type,
                "content": observation.get("content"),
                "sequence": observation.get("global_sequence"),
            }
        )

    # A rendered-turn CORRECTION is appended after detecting a changed prior stable turn.
    # Its browser payload hash intentionally remains the hash of the current MESSAGE-shaped
    # turn. This preserves the old record and proves what the browser currently rendered.
    hashed_event_type = (
        ConversationEventType.MESSAGE.value
        if event_type == ConversationEventType.CORRECTION.value
        else event_type
    )
    return _sha256(
        {
            "conversation_key": str(observation.get("conversation_key", "")),
            "role": str(observation.get("role", "UNKNOWN")),
            "event_type": hashed_event_type,
            "content": observation.get("content"),
            "source_turn_id": str(observation.get("source_turn_id", "")),
            "provider_event_id": str(observation.get("provider_event_id", "")),
            "artifacts": list(observation.get("artifacts", []) or []),
        }
    )


def _full_snapshot_hash(payload: Mapping[str, Any]) -> str:
    capture_path = _require_mapping(payload.get("capture_path"), "capture_path")
    source = _require_mapping(payload.get("source"), "source")
    observations = payload.get("observations", [])
    if not isinstance(observations, list):
        raise BrowserCompanionEnvelopeError("OBSERVATIONS_MUST_BE_ARRAY")
    return _sha256(
        {
            "conversation_key": str(source.get("conversation_key", "")),
            "path_id": str(capture_path.get("path_id", "")),
            "observations": [
                {
                    "source_event_id": str(item.get("source_event_id", "")),
                    "payload_hash": str(
                        (item.get("metadata") or {}).get("payload_hash", "")
                    ),
                    "global_sequence": item.get("global_sequence"),
                    "stream": str(item.get("stream", "OTHER")),
                }
                for item in observations
                if isinstance(item, Mapping)
            ],
        }
    )


def _safe_summary(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    allowed = (
        "state",
        "captured",
        "reused",
        "staged",
        "reconciled",
        "canonical_appended",
        "conflicts",
        "gaps",
        "restore_mode",
        "exact_context_complete",
        "exact_alpha_omega_complete",
        "event_count",
        "coverage_percent",
        "path_count",
        "independent_group_count",
    )
    return {key: value[key] for key in allowed if key in value}


class BrowserCompanionAdapter:
    """Ingress boundary from the no-admin browser companion into ChatBridge Ω4.9.

    The adapter accepts only the browser envelope schema, verifies exact conversation /
    namespace / path identity and browser-side SHA-256 evidence, registers the rendered-DOM
    route as a non-authoritative Alpha→Omega path, and submits observations to the durable
    Ω4.9 runtime. A rendered browser path is bounded by default. Test-only source-complete
    assertions are ignored unless this adapter is explicitly constructed to admit them.
    """

    VERSION = BROWSER_COMPANION_ADAPTER_VERSION

    def __init__(
        self,
        runtime: Any,
        *,
        max_payload_bytes: int = _DEFAULT_MAX_PAYLOAD_BYTES,
        max_observations: int = _DEFAULT_MAX_OBSERVATIONS,
        allow_test_source_complete_claim: bool = False,
    ) -> None:
        self.runtime = runtime
        self.max_payload_bytes = int(max_payload_bytes)
        self.max_observations = int(max_observations)
        self.allow_test_source_complete_claim = bool(
            allow_test_source_complete_claim
        )
        if self.max_payload_bytes < 1:
            raise ValueError("max_payload_bytes must be positive")
        if self.max_observations < 1:
            raise ValueError("max_observations must be positive")

    def _validate_envelope(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        if str(payload.get("schema", "")) != BROWSER_CAPTURE_SCHEMA:
            raise BrowserCompanionEnvelopeError("INVALID_CAPTURE_SCHEMA")
        serialized = _canonical_json(payload).encode("utf-8")
        if len(serialized) > self.max_payload_bytes:
            raise BrowserCompanionEnvelopeError("CAPTURE_PAYLOAD_TOO_LARGE")
        _reject_secret_fields(payload)

        source = _require_mapping(payload.get("source"), "source")
        path_payload = _require_mapping(payload.get("capture_path"), "capture_path")
        snapshot = _require_mapping(payload.get("snapshot"), "snapshot")
        conversation_key = _require_text(
            source.get("conversation_key"), "conversation_key"
        )
        namespace_key = _require_text(payload.get("namespace_key"), "namespace_key")
        path_id = _require_text(path_payload.get("path_id"), "path_id")

        if str(path_payload.get("conversation_key", "")).strip() != conversation_key:
            raise BrowserCompanionEnvelopeError("CAPTURE_PATH_IDENTITY_MISMATCH")
        if str(path_payload.get("kind", "")) != CapturePathKind.RENDERED_DOM.value:
            raise BrowserCompanionEnvelopeError("BROWSER_PATH_KIND_MUST_BE_RENDERED_DOM")
        if bool(path_payload.get("authoritative", False)):
            raise BrowserCompanionEnvelopeError("BROWSER_PATH_CANNOT_SELF_DECLARE_AUTHORITATIVE")

        raw_observations = payload.get("observations", [])
        if not isinstance(raw_observations, list):
            raise BrowserCompanionEnvelopeError("OBSERVATIONS_MUST_BE_ARRAY")
        if len(raw_observations) > self.max_observations:
            raise BrowserCompanionEnvelopeError("TOO_MANY_OBSERVATIONS")

        source_event_ids: set[str] = set()
        observations: list[CaptureObservation] = []
        for raw in raw_observations:
            item = _require_mapping(raw, "observation")
            if str(item.get("conversation_key", "")).strip() != conversation_key:
                raise BrowserCompanionEnvelopeError("OBSERVATION_IDENTITY_MISMATCH")
            if str(item.get("namespace_key", "")).strip().casefold() != namespace_key.casefold():
                raise BrowserCompanionEnvelopeError("OBSERVATION_NAMESPACE_MISMATCH")
            if str(item.get("path_id", "")).strip() != path_id:
                raise BrowserCompanionEnvelopeError("OBSERVATION_PATH_MISMATCH")
            source_event_id = _require_text(
                item.get("source_event_id"), "source_event_id"
            )
            if source_event_id in source_event_ids:
                raise BrowserCompanionEnvelopeError("DUPLICATE_SOURCE_EVENT_ID")
            source_event_ids.add(source_event_id)

            metadata = item.get("metadata")
            metadata = metadata if isinstance(metadata, Mapping) else {}
            claimed_payload_hash = _require_text(
                metadata.get("payload_hash"), "payload_hash"
            )
            if claimed_payload_hash != _browser_payload_hash(item):
                raise BrowserCompanionEnvelopeError("OBSERVATION_PAYLOAD_HASH_MISMATCH")

            event_type = str(item.get("event_type", "OTHER"))
            if event_type == ConversationEventType.TERMINAL_WARNING.value:
                if str(item.get("stream", "")) != ConversationStream.TERMINAL.value:
                    raise BrowserCompanionEnvelopeError("TERMINAL_STREAM_MISMATCH")
                if str(item.get("execution_state", "")) != EventExecutionState.NOT_EXECUTED_TERMINAL.value:
                    raise BrowserCompanionEnvelopeError("TERMINAL_INTENT_MUST_NOT_BE_EXECUTED")
            elif item.get("global_sequence") is None and event_type != ConversationEventType.CORRECTION.value:
                raise BrowserCompanionEnvelopeError("ONLY_CORRECTIONS_MAY_USE_DERIVED_GLOBAL_ORDER")

            observation = CaptureObservation.from_dict(dict(item))
            # Keep browser evidence bounded. Provider-native paths may later corroborate it.
            if observation.payload_availability == PayloadAvailability.RAW_GOVERNED:
                pass
            observations.append(observation)

        claimed_snapshot_hash = _require_text(snapshot.get("sha256"), "snapshot_sha256")
        delta = payload.get("delta")
        is_delta = isinstance(delta, Mapping)
        reconstructable_full_snapshot = bool(
            not is_delta
            or (
                not str(delta.get("previous_snapshot_sha256", "")).strip()
                and int(delta.get("added_count", 0) or 0)
                == int(snapshot.get("observation_count", 0) or 0)
                and int(delta.get("correction_count", 0) or 0) == 0
                and int(delta.get("removed_from_rendered_dom_count", 0) or 0) == 0
            )
        )
        if reconstructable_full_snapshot and claimed_snapshot_hash != _full_snapshot_hash(payload):
            raise BrowserCompanionEnvelopeError("SNAPSHOT_HASH_MISMATCH")

        truth_boundary = _require_mapping(
            payload.get("truth_boundary"), "truth_boundary"
        )
        if bool(truth_boundary.get("native_hidden_chat_access", True)):
            raise BrowserCompanionEnvelopeError("NATIVE_HIDDEN_CHAT_ACCESS_CLAIM_PROHIBITED")
        if not bool(truth_boundary.get("missing_content_is_never_guessed", False)):
            raise BrowserCompanionEnvelopeError("NEVER_GUESS_BOUNDARY_REQUIRED")

        source_complete_claim = bool(
            path_payload.get("metadata", {}).get("source_complete_claim", False)
            if isinstance(path_payload.get("metadata"), Mapping)
            else False
        ) or bool(snapshot.get("exact_source_completeness_claimed", False))
        trusted_source_complete_claim = bool(
            source_complete_claim and self.allow_test_source_complete_claim
        )

        bounded_path_payload = dict(path_payload)
        bounded_path_payload.update(
            {
                "kind": CapturePathKind.RENDERED_DOM.value,
                "state": CapturePathState.AVAILABLE.value,
                "source_provider": str(
                    path_payload.get("source_provider", "CHATGPT_WEB")
                ),
                "authoritative": False,
                # Keep registered path properties stable across browser snapshots.
                "proof_strength": 0.72,
                "completeness": 1.0 if trusted_source_complete_claim else 0.65,
                "freshness": 1.0,
                "speed": 0.95,
                "reversibility": 1.0,
                "owner_burden": 0.0,
                "privacy_cost": 0.35,
                "maintenance_cost": 0.25,
            }
        )
        bounded_path_payload["metadata"] = {
            "browser_companion_adapter_version": self.VERSION,
            "companion_version": str(payload.get("companion_version", "")),
            "rendered_dom_snapshot": True,
            "coverage_assertion": (
                "TEST_ONLY_ADAPTER_TRUSTED_COMPLETE_RENDERED_RANGE"
                if trusted_source_complete_claim
                else "BOUNDED_RENDERED_DOM_NO_NATIVE_COMPLETENESS_CLAIM"
            ),
            "provider_native_completeness_not_inferred": True,
        }

        return {
            "conversation_key": conversation_key,
            "namespace_key": namespace_key.casefold(),
            "path": CapturePath.from_dict(bounded_path_payload),
            "observations": observations,
            "source_provider": str(source.get("provider", "CHATGPT_WEB")),
            "title": str(source.get("title", "")),
            "snapshot": dict(snapshot),
            "stream_manifest": list(payload.get("stream_manifest", []) or []),
            "source_complete_claim_received": source_complete_claim,
            "trusted_source_complete_claim": trusted_source_complete_claim,
            "terminal_observed": bool(snapshot.get("terminal_observed", False)),
            "capture_id": _require_text(payload.get("capture_id"), "capture_id"),
            "captured_at": str(payload.get("captured_at", "")),
            "envelope_sha256": _sha256(payload),
            "snapshot_hash_verification": (
                "FULL_SNAPSHOT_HASH_VERIFIED"
                if reconstructable_full_snapshot
                else "DELTA_ENVELOPE_OBSERVATION_HASHES_VERIFIED_FULL_SNAPSHOT_REQUIRES_PRIOR_STATE"
            ),
        }

    @staticmethod
    def _stream_expectations(
        manifest: Iterable[Any],
    ) -> list[StreamExpectation]:
        expectations: list[StreamExpectation] = []
        for raw in manifest:
            if not isinstance(raw, Mapping):
                continue
            if not bool(raw.get("source_complete_claim", False)):
                continue
            first = raw.get("observed_first_sequence")
            last = raw.get("observed_last_sequence")
            if first is None or last is None:
                continue
            expectations.append(
                StreamExpectation(
                    stream=ConversationStream(
                        str(raw.get("stream", ConversationStream.OTHER.value))
                    ),
                    expected_first_sequence=int(first),
                    expected_last_sequence=int(last),
                    required=bool(raw.get("required_for_exact_restore", True)),
                    allow_empty=False,
                )
            )
        return expectations

    def ingest(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        parsed = self._validate_envelope(_require_mapping(payload, "payload"))
        path_receipt = self.runtime.register_capture_path(parsed["path"])
        capture_receipt = self.runtime.capture_multipath_stream_events(
            parsed["observations"],
            allow_derived_ordering=True,
            source_provider=parsed["source_provider"],
            title=parsed["title"],
        )

        expectation_receipt: Dict[str, Any] = {}
        finalization_receipt: Dict[str, Any] = {}
        if parsed["trusted_source_complete_claim"]:
            expectations = self._stream_expectations(parsed["stream_manifest"])
            if expectations:
                expectation_receipt = self.runtime.declare_stream_expectations(
                    parsed["conversation_key"], expectations
                )
            expected_last = int(
                parsed["snapshot"].get("last_global_sequence") or 0
            )
            if expected_last:
                finalization_receipt = (
                    self.runtime.finalize_multipath_stream_capture(
                        parsed["conversation_key"],
                        parsed["namespace_key"],
                        expected_last_sequence=expected_last,
                        closure_reason=(
                            "BROWSER_TEST_ASSERTED_COMPLETE_TERMINAL_CAPTURE"
                            if parsed["terminal_observed"]
                            else "BROWSER_TEST_ASSERTED_COMPLETE_CAPTURE"
                        ),
                        terminal_observed=parsed["terminal_observed"],
                        allow_derived_ordering=True,
                    )
                )
        else:
            # Reconcile current browser deltas but never seal a bounded rendered-DOM path
            # as a complete native source transcript.
            self.runtime.reconcile_multipath_stream_capture(
                parsed["conversation_key"],
                parsed["namespace_key"],
                allow_derived_ordering=True,
                source_provider=parsed["source_provider"],
                title=parsed["title"],
            )

        assessment = self.runtime.assess_multipath_stream_capture(
            parsed["conversation_key"]
        )
        exact_alpha_omega = bool(assessment.get("exact_alpha_omega_complete", False))
        exact_transcript = bool(
            assessment.get("ffcl", {}).get("exact_context_complete", False)
            if isinstance(assessment.get("ffcl"), Mapping)
            else assessment.get("exact_context_complete", False)
        )
        return {
            "ok": True,
            "receipt": {
                "schema": "CHATBRIDGE-BROWSER-COMPANION-PROVIDER-RECEIPT-1",
                "adapter_version": self.VERSION,
                "state": "BROWSER_CAPTURE_INGESTED_VERIFIED",
                "capture_id": parsed["capture_id"],
                "conversation_key": parsed["conversation_key"],
                "namespace_key": parsed["namespace_key"],
                "path_id": parsed["path"].path_id,
                "path_kind": parsed["path"].kind.value,
                "envelope_sha256": parsed["envelope_sha256"],
                "snapshot_sha256": parsed["snapshot"].get("sha256", ""),
                "snapshot_hash_verification": parsed[
                    "snapshot_hash_verification"
                ],
                "observation_count": len(parsed["observations"]),
                "terminal_observed": parsed["terminal_observed"],
                "source_complete_claim_received": parsed[
                    "source_complete_claim_received"
                ],
                "source_complete_claim_trusted": parsed[
                    "trusted_source_complete_claim"
                ],
                "exact_transcript_complete": exact_transcript,
                "exact_alpha_omega_complete": exact_alpha_omega,
                "path_receipt": _safe_summary(path_receipt),
                "capture_receipt": _safe_summary(capture_receipt),
                "stream_expectation_receipt": _safe_summary(
                    expectation_receipt
                ),
                "finalization_receipt": _safe_summary(
                    finalization_receipt
                ),
                "assessment": _safe_summary(assessment),
                "truth_boundary": {
                    "rendered_dom_is_bounded_by_default": True,
                    "native_hidden_chat_access": False,
                    "browser_installation_or_live_interception_not_proved_by_ingress": True,
                    "provider_readback_proves_only_this_received_envelope": True,
                    "missing_context_is_never_guessed": True,
                },
                "captured_at": parsed["captured_at"],
            },
        }


def ingest_browser_companion_capture(
    runtime: Any,
    payload: Mapping[str, Any],
    *,
    allow_test_source_complete_claim: bool = False,
    max_payload_bytes: int = _DEFAULT_MAX_PAYLOAD_BYTES,
    max_observations: int = _DEFAULT_MAX_OBSERVATIONS,
) -> Dict[str, Any]:
    """Functional ingress wrapper suitable for an HTTP/App/MCP transport boundary."""
    return BrowserCompanionAdapter(
        runtime,
        allow_test_source_complete_claim=allow_test_source_complete_claim,
        max_payload_bytes=max_payload_bytes,
        max_observations=max_observations,
    ).ingest(payload)


__all__ = [
    "BROWSER_CAPTURE_SCHEMA",
    "BROWSER_COMPANION_ADAPTER_VERSION",
    "BrowserCompanionAdapter",
    "BrowserCompanionEnvelopeError",
    "ingest_browser_companion_capture",
]
