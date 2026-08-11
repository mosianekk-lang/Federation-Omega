from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

from authority_snapshot import digest, parse_utc
from governed_commercial_assurance import utc_now
from provider_dispatch_claim_lease import (
    LeasedProviderDispatchOutboxCommercialControlPlane,
)
from provider_dispatch_outbox import (
    LIVE_PROVIDER_RECEIPT_CLASS,
    MOCK_PROVIDER_RECEIPT_CLASS,
)


class FencedConformantMockProviderAdapter:
    """Reference adapter for monotonic dispatch-fencing conformance only.

    The adapter performs no external mutation. It rejects a lower fencing epoch,
    replays an exact same-epoch receipt, and returns a hash-bound mock receipt for
    a higher epoch. This proves the contract shape, not provider-native fencing.
    """

    def __init__(self, provider_domain: str = "reference_provider") -> None:
        self.provider_domain = provider_domain
        self._highest_epoch: dict[str, int] = {}
        self._receipts: dict[tuple[str, int], dict[str, Any]] = {}

    def execute(self, envelope: dict[str, Any]) -> dict[str, Any]:
        observed = envelope.get("record_sha256")
        payload = dict(envelope)
        payload.pop("record_sha256", None)
        if observed != digest(payload):
            raise RuntimeError("provider dispatch attempt envelope hash invalid")
        if envelope.get("provider_domain") != self.provider_domain:
            raise ValueError("provider dispatch domain mismatch")
        for field in (
            "dispatch_attempt_reference",
            "claim_reference",
            "fencing_epoch",
            "provider_dispatch_record_sha256",
            "attempt_start_event_sha256",
        ):
            if field not in envelope:
                raise RuntimeError("provider dispatch fencing field missing")
        key = str(envelope["provider_idempotency_key"])
        epoch = int(envelope["fencing_epoch"])
        highest = self._highest_epoch.get(key, 0)
        if epoch < highest:
            raise RuntimeError("provider dispatch fencing epoch is stale")
        receipt_key = (key, epoch)
        existing = self._receipts.get(receipt_key)
        if existing is not None:
            if existing["dispatch_attempt_reference"] != envelope[
                "dispatch_attempt_reference"
            ]:
                raise RuntimeError("provider fencing epoch equivocation")
            return deepcopy(existing)
        self._highest_epoch[key] = epoch
        receipt = {
            "receipt_class": MOCK_PROVIDER_RECEIPT_CLASS,
            "dispatch_id": envelope["dispatch_id"],
            "provider_domain": envelope["provider_domain"],
            "operation": envelope["operation"],
            "provider_idempotency_key": key,
            "dispatch_attempt_reference": envelope["dispatch_attempt_reference"],
            "claim_reference": envelope["claim_reference"],
            "fencing_epoch": epoch,
            "provider_dispatch_record_sha256": envelope[
                "provider_dispatch_record_sha256"
            ],
            "attempt_envelope_sha256": observed,
            "attempt_start_event_sha256": envelope[
                "attempt_start_event_sha256"
            ],
            "provider_request_id": "MOCK-FENCE-" + digest(envelope)[:24],
            "response_status": 200,
            "response_body_sha256": digest(
                {
                    "dispatch_id": envelope["dispatch_id"],
                    "dispatch_attempt_reference": envelope[
                        "dispatch_attempt_reference"
                    ],
                    "fencing_epoch": epoch,
                    "state": "MOCK_PROVIDER_FENCING_CONFORMANCE_ONLY",
                }
            ),
            "observed_at": envelope["attempt_started_at"],
            "external_mutation_performed": False,
            "live_provider_operation_proven": False,
            "provider_native_fencing_proven": False,
        }
        receipt["provider_receipt_sha256"] = digest(receipt)
        self._receipts[receipt_key] = deepcopy(receipt)
        return receipt


class FencedProviderDispatchCommercialControlPlane(
    LeasedProviderDispatchOutboxCommercialControlPlane
):
    """V13 renewable lease and monotonic dispatch-attempt fencing boundary.

    V12 prevents two local workers from holding an active claim at the same time,
    but a long provider call can outlive its lease and permit takeover while the
    first call is still in flight. V13 adds explicit lease renewal, a durable
    STARTED event, one monotonic fencing epoch per claim attempt, attempt-bound
    provider envelopes and receipts, and terminal failure records. Provider-side
    enforcement still requires fresh provider-native evidence.
    """

    CAPABILITY_REVISION = "AO-COMMERCIAL-PROVIDER-DISPATCH-FENCING-V13"
    STAGE_SCOPE = ["C03", "C06", "C07", "C11", "C14", "C15"]
    TERMINAL_EVENT_TYPES = {"COMPLETED", "EXPIRED", "ABANDONED", "ATTEMPT_FAILED"}

    @staticmethod
    def _verify_dispatch_record(record: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(record, dict):
            raise RuntimeError("provider dispatch record invalid")
        payload = dict(record)
        observed = payload.pop("record_sha256", None)
        if observed != digest(payload):
            raise RuntimeError("provider dispatch record hash invalid")
        receipt = record.get("provider_receipt")
        if receipt is not None:
            receipt_payload = dict(receipt)
            receipt_hash = receipt_payload.pop("provider_receipt_sha256", None)
            if receipt_hash != digest(receipt_payload):
                raise RuntimeError("provider dispatch receipt hash invalid")
            for field in (
                "dispatch_id",
                "provider_domain",
                "operation",
                "provider_idempotency_key",
            ):
                if receipt.get(field) != record.get(field):
                    raise RuntimeError("provider dispatch receipt binding invalid")
            if receipt.get("receipt_class") != MOCK_PROVIDER_RECEIPT_CLASS:
                raise RuntimeError("unadmitted provider receipt class")
            allowed_states = {
                "MOCK_PROVIDER_CONFORMANCE_VERIFIED_LIVE_PROVIDER_PROOF_REQUIRED",
                "MOCK_PROVIDER_FENCING_CONFORMANCE_VERIFIED_LIVE_PROVIDER_PROOF_REQUIRED",
            }
            if record.get("state") not in allowed_states:
                raise RuntimeError("mock provider dispatch state invalid")
            if receipt.get("external_mutation_performed") is not False:
                raise RuntimeError("mock provider receipt claimed external mutation")
            if receipt.get("live_provider_operation_proven") is not False:
                raise RuntimeError("mock provider receipt claimed live operation")
            if record.get("state").startswith("MOCK_PROVIDER_FENCING"):
                for field in (
                    "dispatch_attempt_reference",
                    "claim_reference",
                    "fencing_epoch",
                    "provider_dispatch_record_sha256",
                    "attempt_start_event_sha256",
                ):
                    if field not in receipt:
                        raise RuntimeError("fenced provider receipt field missing")
                if receipt.get("provider_native_fencing_proven") is not False:
                    raise RuntimeError("mock provider receipt claimed provider-native fencing")
        return dict(record)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._verify_provider_dispatch_attempt_state()

    @staticmethod
    def _latest_claim(events: list[dict[str, Any]]) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.get("event_type") != "CLAIMED":
                continue
            later_events = events[event["sequence"] :]
            terminal = next(
                (
                    later
                    for later in later_events
                    if later.get("claim_reference") == event.get("claim_reference")
                    and later.get("event_type")
                    in FencedProviderDispatchCommercialControlPlane.TERMINAL_EVENT_TYPES
                ),
                None,
            )
            if terminal is not None:
                continue
            active = dict(event)
            renewals = [
                later
                for later in later_events
                if later.get("claim_reference") == event.get("claim_reference")
                and later.get("event_type") == "RENEWED"
            ]
            if renewals:
                latest = renewals[-1]
                active["lease_expires_at"] = latest["lease_expires_at"]
                active["renewal_sequence"] = latest["sequence"]
                active["renewed_at"] = latest["event_at"]
            return active
        return None

    @staticmethod
    def _claim_events(
        events: list[dict[str, Any]], claim_reference: str
    ) -> list[dict[str, Any]]:
        return [
            event
            for event in events
            if event.get("claim_reference") == claim_reference
        ]

    def renew_provider_dispatch_claim(
        self,
        dispatch_id: str,
        *,
        claim_token: str,
        lease_seconds: int = 60,
        now: str | None = None,
    ) -> dict[str, Any]:
        if not self.MIN_LEASE_SECONDS <= lease_seconds <= self.MAX_LEASE_SECONDS:
            raise ValueError("lease_seconds outside permitted range")
        current = now or utc_now()
        current_dt = parse_utc(current)
        with self._action_coordination_locked():
            state = self._read_state()
            dispatch = state.setdefault("provider_dispatches", {}).get(dispatch_id)
            if dispatch is None:
                raise KeyError("provider dispatch not found")
            self._verify_dispatch_record(dispatch)
            events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id),
                dispatch_id,
            )
            active = self._latest_claim(events)
            if active is None or active.get("claim_reference") != claim_token:
                raise RuntimeError("provider dispatch claim token is not current")
            previous_expiry = parse_utc(str(active["lease_expires_at"]))
            if current_dt >= previous_expiry:
                raise RuntimeError("provider dispatch claim lease expired")
            new_expiry = current_dt + timedelta(seconds=lease_seconds)
            if new_expiry <= previous_expiry:
                raise ValueError("provider dispatch claim renewal must extend the lease")
            lease_expires_at = new_expiry.isoformat().replace("+00:00", "Z")
            renewed = self._append_claim_event(
                events,
                dispatch_id=dispatch_id,
                event_type="RENEWED",
                event_at=current,
                details={
                    "worker_id": active["worker_id"],
                    "claim_reference": claim_token,
                    "attempt": active["attempt"],
                    "previous_lease_expires_at": active["lease_expires_at"],
                    "lease_expires_at": lease_expires_at,
                },
            )
            state["provider_dispatch_claim_history"][dispatch_id] = events
            self._write_state(state)
            self._ledger("C06", "provider_dispatch.claim_renewed", dispatch_id, renewed)
            return dict(renewed)

    def start_provider_dispatch_attempt(
        self,
        dispatch_id: str,
        *,
        claim_token: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        current = now or utc_now()
        current_dt = parse_utc(current)
        with self._action_coordination_locked():
            state = self._read_state()
            dispatch = state.setdefault("provider_dispatches", {}).get(dispatch_id)
            if dispatch is None:
                raise KeyError("provider dispatch not found")
            self._verify_dispatch_record(dispatch)
            if dispatch.get("provider_receipt") is not None:
                raise RuntimeError("provider dispatch already completed")
            events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id),
                dispatch_id,
            )
            active = self._latest_claim(events)
            if active is None or active.get("claim_reference") != claim_token:
                raise RuntimeError("provider dispatch claim token is not current")
            if current_dt >= parse_utc(str(active["lease_expires_at"])):
                raise RuntimeError("provider dispatch claim lease expired")
            claim_events = self._claim_events(events, claim_token)
            existing = next(
                (event for event in claim_events if event.get("event_type") == "STARTED"),
                None,
            )
            if existing is not None:
                return dict(existing)
            fencing_epoch = int(active["attempt"])
            attempt_reference = digest(
                {
                    "dispatch_id": dispatch_id,
                    "dispatch_record_sha256": dispatch["record_sha256"],
                    "claim_reference": claim_token,
                    "worker_id": active["worker_id"],
                    "fencing_epoch": fencing_epoch,
                    "started_at": current,
                }
            )
            started = self._append_claim_event(
                events,
                dispatch_id=dispatch_id,
                event_type="STARTED",
                event_at=current,
                details={
                    "worker_id": active["worker_id"],
                    "claim_reference": claim_token,
                    "attempt": active["attempt"],
                    "fencing_epoch": fencing_epoch,
                    "dispatch_attempt_reference": attempt_reference,
                    "prepared_dispatch_record_sha256": dispatch["record_sha256"],
                    "lease_expires_at": active["lease_expires_at"],
                },
            )
            state["provider_dispatch_claim_history"][dispatch_id] = events
            self._write_state(state)
            self._ledger("C07", "provider_dispatch.attempt_started", dispatch_id, started)
            return dict(started)

    def provider_dispatch_attempt_envelope(
        self,
        dispatch_id: str,
        *,
        claim_token: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        current = now or utc_now()
        current_dt = parse_utc(current)
        with self._action_coordination_locked():
            state = self._read_state()
            dispatch = state.setdefault("provider_dispatches", {}).get(dispatch_id)
            if dispatch is None:
                raise KeyError("provider dispatch not found")
            self._verify_dispatch_record(dispatch)
            events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id),
                dispatch_id,
            )
            active = self._latest_claim(events)
            if active is None or active.get("claim_reference") != claim_token:
                raise RuntimeError("provider dispatch claim token is not current")
            if current_dt >= parse_utc(str(active["lease_expires_at"])):
                raise RuntimeError("provider dispatch claim lease expired")
            started = next(
                (
                    event
                    for event in self._claim_events(events, claim_token)
                    if event.get("event_type") == "STARTED"
                ),
                None,
            )
            if started is None:
                raise RuntimeError("provider dispatch attempt has not been started")
            envelope = dict(dispatch)
            prepared_record_sha256 = envelope.pop("record_sha256")
            envelope.update(
                {
                    "provider_dispatch_record_sha256": prepared_record_sha256,
                    "claim_reference": claim_token,
                    "claim_attempt": active["attempt"],
                    "fencing_epoch": started["fencing_epoch"],
                    "dispatch_attempt_reference": started[
                        "dispatch_attempt_reference"
                    ],
                    "attempt_started_at": started["event_at"],
                    "attempt_start_event_sha256": started["event_sha256"],
                    "lease_expires_at": active["lease_expires_at"],
                }
            )
            envelope["record_sha256"] = digest(envelope)
            return envelope

    def record_provider_dispatch_attempt_failure(
        self,
        dispatch_id: str,
        *,
        claim_token: str,
        error_class: str,
        retryable: bool,
        now: str | None = None,
    ) -> dict[str, Any]:
        if not error_class or len(error_class) > 128:
            raise ValueError("error_class is required and must be at most 128 characters")
        current = now or utc_now()
        current_dt = parse_utc(current)
        with self._action_coordination_locked():
            state = self._read_state()
            events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id),
                dispatch_id,
            )
            active = self._latest_claim(events)
            if active is None or active.get("claim_reference") != claim_token:
                raise RuntimeError("provider dispatch claim token is not current")
            if current_dt >= parse_utc(str(active["lease_expires_at"])):
                raise RuntimeError("provider dispatch claim lease expired")
            started = next(
                (
                    event
                    for event in self._claim_events(events, claim_token)
                    if event.get("event_type") == "STARTED"
                ),
                None,
            )
            if started is None:
                raise RuntimeError("provider dispatch attempt has not been started")
            failed = self._append_claim_event(
                events,
                dispatch_id=dispatch_id,
                event_type="ATTEMPT_FAILED",
                event_at=current,
                details={
                    "worker_id": active["worker_id"],
                    "claim_reference": claim_token,
                    "attempt": active["attempt"],
                    "fencing_epoch": started["fencing_epoch"],
                    "dispatch_attempt_reference": started[
                        "dispatch_attempt_reference"
                    ],
                    "error_class": error_class,
                    "retryable": bool(retryable),
                },
            )
            state["provider_dispatch_claim_history"][dispatch_id] = events
            self._write_state(state)
            self._ledger("C06", "provider_dispatch.attempt_failed", dispatch_id, failed)
            return dict(failed)

    def admit_provider_dispatch_receipt(
        self,
        dispatch_id: str,
        receipt: dict[str, Any],
        *,
        claim_token: str | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        if not claim_token:
            raise RuntimeError("V13 provider receipt admission requires a current claim token")
        current = now or utc_now()
        current_dt = parse_utc(current)
        with self._action_coordination_locked():
            state = self._read_state()
            dispatches = state.setdefault("provider_dispatches", {})
            record = dispatches.get(dispatch_id)
            if record is None:
                raise KeyError("provider dispatch not found")
            self._verify_dispatch_record(record)
            events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id),
                dispatch_id,
            )
            if record.get("provider_receipt") is not None:
                existing = record["provider_receipt"]
                if existing != receipt:
                    raise ValueError("provider receipt conflict")
                completed = any(
                    event.get("event_type") == "COMPLETED"
                    and event.get("claim_reference") == claim_token
                    and event.get("dispatch_attempt_reference")
                    == receipt.get("dispatch_attempt_reference")
                    for event in events
                )
                if not completed:
                    raise RuntimeError("provider dispatch receipt is bound to another attempt")
                return dict(record)
            active = self._latest_claim(events)
            if active is None or active.get("claim_reference") != claim_token:
                raise RuntimeError("provider dispatch claim token is not current")
            if current_dt >= parse_utc(str(active["lease_expires_at"])):
                raise RuntimeError("provider dispatch claim lease expired")
            started = next(
                (
                    event
                    for event in self._claim_events(events, claim_token)
                    if event.get("event_type") == "STARTED"
                ),
                None,
            )
            if started is None:
                raise RuntimeError("provider dispatch attempt has not been started")
            receipt_class = receipt.get("receipt_class")
            if receipt_class == LIVE_PROVIDER_RECEIPT_CLASS:
                raise RuntimeError(
                    "live provider receipt admission requires a concrete provider-native fencing verifier and fresh external proof"
                )
            if receipt_class != MOCK_PROVIDER_RECEIPT_CLASS:
                raise ValueError("unsupported provider receipt class")
            receipt_payload = dict(receipt)
            observed = receipt_payload.pop("provider_receipt_sha256", None)
            if observed != digest(receipt_payload):
                raise RuntimeError("provider receipt hash invalid")
            for field in (
                "dispatch_id",
                "provider_domain",
                "operation",
                "provider_idempotency_key",
            ):
                if receipt.get(field) != record.get(field):
                    raise RuntimeError("provider receipt does not bind the prepared dispatch")
            expected = {
                "dispatch_attempt_reference": started["dispatch_attempt_reference"],
                "claim_reference": claim_token,
                "fencing_epoch": started["fencing_epoch"],
                "provider_dispatch_record_sha256": started[
                    "prepared_dispatch_record_sha256"
                ],
                "attempt_start_event_sha256": started["event_sha256"],
            }
            for field, value in expected.items():
                if receipt.get(field) != value:
                    raise RuntimeError("provider receipt does not bind the current fenced attempt")
            if receipt.get("external_mutation_performed") is not False:
                raise RuntimeError("mock provider receipt may not claim external mutation")
            if receipt.get("live_provider_operation_proven") is not False:
                raise RuntimeError("mock provider receipt may not claim live operation")
            if receipt.get("provider_native_fencing_proven") is not False:
                raise RuntimeError("mock provider receipt may not claim provider-native fencing")
            updated = dict(record)
            updated.pop("record_sha256", None)
            updated["state"] = (
                "MOCK_PROVIDER_FENCING_CONFORMANCE_VERIFIED_"
                "LIVE_PROVIDER_PROOF_REQUIRED"
            )
            updated["provider_receipt"] = deepcopy(receipt)
            updated["record_sha256"] = digest(updated)
            dispatches[dispatch_id] = updated
            completed = self._append_claim_event(
                events,
                dispatch_id=dispatch_id,
                event_type="COMPLETED",
                event_at=current,
                details={
                    "worker_id": active["worker_id"],
                    "claim_reference": claim_token,
                    "attempt": active["attempt"],
                    "fencing_epoch": started["fencing_epoch"],
                    "dispatch_attempt_reference": started[
                        "dispatch_attempt_reference"
                    ],
                    "provider_receipt_sha256": receipt[
                        "provider_receipt_sha256"
                    ],
                    "completed_dispatch_record_sha256": updated["record_sha256"],
                },
            )
            state["provider_dispatch_claim_history"][dispatch_id] = events
            self._write_state(state)
            self._ledger(
                "C07", "provider_dispatch.fenced_receipt_admitted", dispatch_id, completed
            )
            return dict(updated)

    def _verify_provider_dispatch_attempt_state(self) -> bool:
        self._verify_provider_dispatch_claim_state()
        state = self._read_state()
        histories = state.get("provider_dispatch_claim_history", {})
        for dispatch_id, raw_events in histories.items():
            events = self._verify_claim_history(raw_events, dispatch_id)
            claims = {
                str(event["claim_reference"]): event
                for event in events
                if event.get("event_type") == "CLAIMED"
            }
            last_epoch = 0
            for claim_reference, claim in claims.items():
                related = self._claim_events(events, claim_reference)
                effective_expiry = str(claim["lease_expires_at"])
                started_events: list[dict[str, Any]] = []
                terminal_seen = False
                for event in related[1:]:
                    event_type = event.get("event_type")
                    if event_type == "RENEWED":
                        if terminal_seen:
                            raise RuntimeError("provider dispatch claim renewed after terminal event")
                        if event.get("worker_id") != claim.get("worker_id"):
                            raise RuntimeError("provider dispatch claim renewal worker invalid")
                        if event.get("attempt") != claim.get("attempt"):
                            raise RuntimeError("provider dispatch claim renewal attempt invalid")
                        if event.get("previous_lease_expires_at") != effective_expiry:
                            raise RuntimeError("provider dispatch claim renewal chain invalid")
                        if parse_utc(str(event["lease_expires_at"])) <= parse_utc(
                            effective_expiry
                        ):
                            raise RuntimeError("provider dispatch claim renewal did not extend lease")
                        effective_expiry = str(event["lease_expires_at"])
                    elif event_type == "STARTED":
                        if terminal_seen:
                            raise RuntimeError("provider dispatch attempt started after terminal event")
                        started_events.append(event)
                        if len(started_events) > 1:
                            raise RuntimeError("provider dispatch claim has multiple started attempts")
                        if event.get("attempt") != claim.get("attempt"):
                            raise RuntimeError("provider dispatch fencing attempt invalid")
                        epoch = int(event.get("fencing_epoch", 0))
                        if epoch != int(claim["attempt"]) or epoch <= last_epoch:
                            raise RuntimeError("provider dispatch fencing epoch invalid")
                        last_epoch = epoch
                    elif event_type in self.TERMINAL_EVENT_TYPES:
                        terminal_seen = True
                        if event_type in {"COMPLETED", "ATTEMPT_FAILED"}:
                            if len(started_events) != 1:
                                raise RuntimeError(
                                    "provider dispatch terminal attempt lacks one start event"
                                )
                            started = started_events[0]
                            if event.get("dispatch_attempt_reference") != started.get(
                                "dispatch_attempt_reference"
                            ):
                                raise RuntimeError(
                                    "provider dispatch terminal attempt binding invalid"
                                )
                            if event.get("fencing_epoch") != started.get(
                                "fencing_epoch"
                            ):
                                raise RuntimeError(
                                    "provider dispatch terminal fencing binding invalid"
                                )
                if started_events:
                    started = started_events[0]
                    if started.get("lease_expires_at") != claim.get("lease_expires_at"):
                        if not any(
                            event.get("event_type") == "RENEWED"
                            for event in related
                        ):
                            raise RuntimeError("provider dispatch start lease binding invalid")
            receipt = state.get("provider_dispatches", {}).get(dispatch_id, {}).get(
                "provider_receipt"
            )
            if receipt is not None:
                completed = [
                    event for event in events if event.get("event_type") == "COMPLETED"
                ]
                if len(completed) != 1:
                    raise RuntimeError("admitted fenced receipt must have one completion")
                complete = completed[0]
                for field in (
                    "dispatch_attempt_reference",
                    "fencing_epoch",
                    "provider_receipt_sha256",
                ):
                    if complete.get(field) != receipt.get(field):
                        raise RuntimeError("fenced receipt completion binding invalid")
        return True

    def provider_dispatch_attempt_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            self._verify_provider_dispatch_attempt_state()
            histories = self._read_state().get("provider_dispatch_claim_history", {})
            events = [event for history in histories.values() for event in history]
            return {
                "capability_revision": self.CAPABILITY_REVISION,
                "integrity": "VERIFIED",
                "stage_scope": list(self.STAGE_SCOPE),
                "renewal_events": sum(
                    1 for event in events if event.get("event_type") == "RENEWED"
                ),
                "started_attempts": sum(
                    1 for event in events if event.get("event_type") == "STARTED"
                ),
                "failed_attempts": sum(
                    1
                    for event in events
                    if event.get("event_type") == "ATTEMPT_FAILED"
                ),
                "completed_attempts": sum(
                    1 for event in events if event.get("event_type") == "COMPLETED"
                ),
                "lease_renewal_supported": True,
                "one_started_attempt_per_claim": True,
                "monotonic_fencing_epoch": True,
                "attempt_envelope_hash_bound": True,
                "receipt_bound_to_current_fenced_attempt": True,
                "stale_fencing_receipt_rejected": True,
                "terminal_failure_releases_claim": True,
                "mock_provider_fencing_conformance": True,
                "provider_native_fencing_proven": False,
                "external_mutation_performed": False,
                "live_provider_operation_proven": False,
                "distributed_provider_exactly_once_proven": False,
            }

    def governed_authority_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            result = super().governed_authority_readback()
            result["canonical_class"] = self.__class__.__name__
            result["predecessor_class"] = (
                "LeasedProviderDispatchOutboxCommercialControlPlane"
            )
            result["provider_dispatch_fencing"] = (
                self.provider_dispatch_attempt_readback()
            )
            return result
