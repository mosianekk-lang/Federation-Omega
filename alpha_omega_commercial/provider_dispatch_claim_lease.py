from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

from authority_snapshot import digest, parse_utc
from governed_commercial_assurance import utc_now
from provider_dispatch_outbox import (
    LIVE_PROVIDER_RECEIPT_CLASS,
    MOCK_PROVIDER_RECEIPT_CLASS,
    ProviderDispatchOutboxCommercialControlPlane,
)


class LeasedProviderDispatchOutboxCommercialControlPlane(
    ProviderDispatchOutboxCommercialControlPlane
):
    """V12 local worker-claim and lease boundary for provider dispatches.

    V11 prepares an exact, durable provider command but does not select one local
    worker as the current dispatcher. V12 adds a hash-chained claim history with
    bounded leases, exact same-worker retry, stale-token rejection and explicit
    expiry takeover. It prevents concurrent local workers from dispatching the
    same prepared command through this control plane. It does not prove a remote
    provider performed exactly one external mutation.
    """

    CAPABILITY_REVISION = "AO-COMMERCIAL-PROVIDER-DISPATCH-LEASE-V12"
    STAGE_SCOPE = ["C03", "C06", "C07", "C11", "C14", "C15"]
    MIN_LEASE_SECONDS = 5
    MAX_LEASE_SECONDS = 900

    @staticmethod
    def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
        payload = dict(event)
        payload.pop("event_sha256", None)
        return payload

    @classmethod
    def _verify_claim_history(cls, events: Any, dispatch_id: str) -> list[dict[str, Any]]:
        if events is None:
            return []
        if not isinstance(events, list):
            raise RuntimeError("provider dispatch claim history invalid")
        verified: list[dict[str, Any]] = []
        previous = ""
        for sequence, raw in enumerate(events, start=1):
            if not isinstance(raw, dict):
                raise RuntimeError("provider dispatch claim event invalid")
            event = dict(raw)
            if event.get("dispatch_id") != dispatch_id:
                raise RuntimeError("provider dispatch claim identity invalid")
            if event.get("sequence") != sequence:
                raise RuntimeError("provider dispatch claim sequence invalid")
            if event.get("previous_event_sha256") != previous:
                raise RuntimeError("provider dispatch claim chain invalid")
            observed = event.get("event_sha256")
            if observed != digest(cls._event_payload(event)):
                raise RuntimeError("provider dispatch claim event hash invalid")
            previous = str(observed)
            verified.append(event)
        return verified

    @classmethod
    def _append_claim_event(
        cls,
        events: list[dict[str, Any]],
        *,
        dispatch_id: str,
        event_type: str,
        event_at: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        event = {
            "dispatch_id": dispatch_id,
            "sequence": len(events) + 1,
            "event_type": event_type,
            "event_at": event_at,
            "previous_event_sha256": (
                events[-1]["event_sha256"] if events else ""
            ),
            **details,
        }
        event["event_sha256"] = digest(event)
        events.append(event)
        return event

    @staticmethod
    def _latest_claim(events: list[dict[str, Any]]) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.get("event_type") == "CLAIMED":
                terminal = next(
                    (
                        later
                        for later in events[event["sequence"] :]
                        if later.get("claim_token") == event.get("claim_token")
                        and later.get("event_type") in {"COMPLETED", "EXPIRED", "ABANDONED"}
                    ),
                    None,
                )
                if terminal is None:
                    return event
        return None

    def claim_provider_dispatch(
        self,
        dispatch_id: str,
        *,
        worker_id: str,
        lease_seconds: int = 60,
        now: str | None = None,
    ) -> dict[str, Any]:
        if not worker_id or len(worker_id) > 128:
            raise ValueError("worker_id is required and must be at most 128 characters")
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
            if dispatch.get("provider_receipt") is not None:
                raise RuntimeError("provider dispatch already completed")

            histories = state.setdefault("provider_dispatch_claim_history", {})
            events = self._verify_claim_history(histories.get(dispatch_id), dispatch_id)
            active = self._latest_claim(events)
            if active is not None:
                if current_dt < parse_utc(str(active["lease_expires_at"])):
                    if active.get("worker_id") == worker_id:
                        return dict(active)
                    raise RuntimeError("provider dispatch already claimed by another worker")
                self._append_claim_event(
                    events,
                    dispatch_id=dispatch_id,
                    event_type="EXPIRED",
                    event_at=current,
                    details={
                        "worker_id": active["worker_id"],
                        "claim_token": active["claim_token"],
                        "attempt": active["attempt"],
                    },
                )

            attempt = sum(1 for item in events if item.get("event_type") == "CLAIMED") + 1
            lease_expires_at = (current_dt + timedelta(seconds=lease_seconds)).isoformat().replace(
                "+00:00", "Z"
            )
            previous = events[-1]["event_sha256"] if events else ""
            claim_token = digest(
                {
                    "dispatch_id": dispatch_id,
                    "dispatch_record_sha256": dispatch["record_sha256"],
                    "worker_id": worker_id,
                    "attempt": attempt,
                    "claimed_at": current,
                    "lease_expires_at": lease_expires_at,
                    "previous_event_sha256": previous,
                }
            )
            claimed = self._append_claim_event(
                events,
                dispatch_id=dispatch_id,
                event_type="CLAIMED",
                event_at=current,
                details={
                    "worker_id": worker_id,
                    "attempt": attempt,
                    "claimed_at": current,
                    "lease_expires_at": lease_expires_at,
                    "dispatch_record_sha256": dispatch["record_sha256"],
                    "claim_token": claim_token,
                },
            )
            histories[dispatch_id] = events
            self._write_state(state)
            self._ledger("C06", "provider_dispatch.claimed", dispatch_id, claimed)
            return dict(claimed)

    def abandon_provider_dispatch_claim(
        self,
        dispatch_id: str,
        *,
        claim_token: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        current = now or utc_now()
        with self._action_coordination_locked():
            state = self._read_state()
            events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id),
                dispatch_id,
            )
            active = self._latest_claim(events)
            if active is None or active.get("claim_token") != claim_token:
                raise RuntimeError("provider dispatch claim token is not current")
            abandoned = self._append_claim_event(
                events,
                dispatch_id=dispatch_id,
                event_type="ABANDONED",
                event_at=current,
                details={
                    "worker_id": active["worker_id"],
                    "claim_token": claim_token,
                    "attempt": active["attempt"],
                },
            )
            state["provider_dispatch_claim_history"][dispatch_id] = events
            self._write_state(state)
            self._ledger("C06", "provider_dispatch.claim_abandoned", dispatch_id, abandoned)
            return dict(abandoned)

    def admit_provider_dispatch_receipt(
        self,
        dispatch_id: str,
        receipt: dict[str, Any],
        *,
        claim_token: str | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        if not claim_token:
            raise RuntimeError("V12 provider receipt admission requires a current claim token")
        current = now or utc_now()
        current_dt = parse_utc(current)
        with self._action_coordination_locked():
            state = self._read_state()
            dispatches = state.setdefault("provider_dispatches", {})
            record = dispatches.get(dispatch_id)
            if record is None:
                raise KeyError("provider dispatch not found")
            self._verify_dispatch_record(record)
            if record.get("provider_receipt") is not None:
                existing = record["provider_receipt"]
                if existing != receipt:
                    raise ValueError("provider receipt conflict")
                events = self._verify_claim_history(
                    state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id),
                    dispatch_id,
                )
                completed = any(
                    event.get("event_type") == "COMPLETED"
                    and event.get("claim_token") == claim_token
                    for event in events
                )
                if not completed:
                    raise RuntimeError("provider dispatch receipt is bound to another claim")
                return dict(record)

            events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id),
                dispatch_id,
            )
            active = self._latest_claim(events)
            if active is None or active.get("claim_token") != claim_token:
                raise RuntimeError("provider dispatch claim token is not current")
            if current_dt >= parse_utc(str(active["lease_expires_at"])):
                raise RuntimeError("provider dispatch claim lease expired")

            receipt_class = receipt.get("receipt_class")
            if receipt_class == LIVE_PROVIDER_RECEIPT_CLASS:
                raise RuntimeError(
                    "live provider receipt admission requires a concrete provider-native verifier and fresh external proof"
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
            if receipt.get("external_mutation_performed") is not False:
                raise RuntimeError("mock provider receipt may not claim external mutation")
            if receipt.get("live_provider_operation_proven") is not False:
                raise RuntimeError("mock provider receipt may not claim live operation")

            updated = dict(record)
            updated.pop("record_sha256", None)
            updated["state"] = "MOCK_PROVIDER_CONFORMANCE_VERIFIED_LIVE_PROVIDER_PROOF_REQUIRED"
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
                    "claim_token": claim_token,
                    "attempt": active["attempt"],
                    "provider_receipt_sha256": receipt["provider_receipt_sha256"],
                    "completed_dispatch_record_sha256": updated["record_sha256"],
                },
            )
            state["provider_dispatch_claim_history"][dispatch_id] = events
            self._write_state(state)
            self._ledger("C07", "provider_dispatch.claimed_receipt_admitted", dispatch_id, completed)
            return dict(updated)

    def _verify_provider_dispatch_claim_state(self) -> bool:
        state = self._read_state()
        histories = state.get("provider_dispatch_claim_history", {})
        if not isinstance(histories, dict):
            raise RuntimeError("provider dispatch claim state invalid")
        for dispatch_id, raw_events in histories.items():
            if dispatch_id not in state.get("provider_dispatches", {}):
                raise RuntimeError("provider dispatch claim references unknown dispatch")
            events = self._verify_claim_history(raw_events, dispatch_id)
            completed = [event for event in events if event.get("event_type") == "COMPLETED"]
            receipt = state["provider_dispatches"][dispatch_id].get("provider_receipt")
            if completed and receipt is None:
                raise RuntimeError("completed provider claim has no admitted receipt")
            if receipt is not None:
                if len(completed) != 1:
                    raise RuntimeError("admitted provider receipt must have one completed claim")
                if completed[0].get("provider_receipt_sha256") != receipt.get(
                    "provider_receipt_sha256"
                ):
                    raise RuntimeError("completed provider claim receipt binding invalid")
        return True

    def provider_dispatch_claim_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            self._verify_provider_dispatch_state()
            self._verify_provider_dispatch_claim_state()
            histories = self._read_state().get("provider_dispatch_claim_history", {})
            events = [event for history in histories.values() for event in history]
            active = 0
            for dispatch_id, history in histories.items():
                if self._latest_claim(self._verify_claim_history(history, dispatch_id)) is not None:
                    active += 1
            return {
                "capability_revision": self.CAPABILITY_REVISION,
                "integrity": "VERIFIED",
                "stage_scope": list(self.STAGE_SCOPE),
                "dispatches_with_claim_history": len(histories),
                "claim_events": len(events),
                "active_claims": active,
                "completed_claims": sum(
                    1 for event in events if event.get("event_type") == "COMPLETED"
                ),
                "expired_claims": sum(
                    1 for event in events if event.get("event_type") == "EXPIRED"
                ),
                "abandoned_claims": sum(
                    1 for event in events if event.get("event_type") == "ABANDONED"
                ),
                "one_active_local_worker_per_dispatch": True,
                "same_worker_claim_retry_is_idempotent": True,
                "expired_claim_takeover_supported": True,
                "stale_claim_token_rejected": True,
                "receipt_requires_current_unexpired_claim": True,
                "local_duplicate_dispatch_prevented": True,
                "external_mutation_performed": False,
                "live_provider_operation_proven": False,
                "distributed_provider_exactly_once_proven": False,
            }

    def governed_authority_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            result = super().governed_authority_readback()
            result["canonical_class"] = self.__class__.__name__
            result["predecessor_class"] = "ProviderDispatchOutboxCommercialControlPlane"
            result["provider_dispatch_claim_lease"] = self.provider_dispatch_claim_readback()
            return result
