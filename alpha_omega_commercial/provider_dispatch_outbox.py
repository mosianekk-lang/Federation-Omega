from __future__ import annotations

from copy import deepcopy
from typing import Any

from authority_action_idempotency import (
    IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane,
)
from authority_snapshot import digest
from governed_commercial_assurance import utc_now


MOCK_PROVIDER_RECEIPT_CLASS = "MOCK_PROVIDER_CONFORMANCE"
LIVE_PROVIDER_RECEIPT_CLASS = "LIVE_PROVIDER_NATIVE"


class ConformantMockProviderAdapter:
    """Deterministic reference provider for dispatch-contract conformance only.

    The adapter never performs an external operation. It proves that a provider
    can consume the stable dispatch identity and return an exact-retry-safe,
    hash-bound acknowledgement. Its receipts are permanently excluded from live
    provider, customer, payment, revenue and Cloud Run evidence.
    """

    def __init__(self, provider_domain: str = "reference_provider") -> None:
        self.provider_domain = provider_domain
        self._receipts: dict[str, dict[str, Any]] = {}

    def execute(self, envelope: dict[str, Any]) -> dict[str, Any]:
        observed = envelope.get("record_sha256")
        payload = dict(envelope)
        payload.pop("record_sha256", None)
        if observed != digest(payload):
            raise RuntimeError("provider dispatch envelope hash invalid")
        if envelope.get("provider_domain") != self.provider_domain:
            raise ValueError("provider dispatch domain mismatch")
        idempotency_key = str(envelope["provider_idempotency_key"])
        existing = self._receipts.get(idempotency_key)
        if existing is not None:
            if existing["dispatch_id"] != envelope["dispatch_id"]:
                raise RuntimeError("provider idempotency key collision")
            return deepcopy(existing)
        receipt = {
            "receipt_class": MOCK_PROVIDER_RECEIPT_CLASS,
            "dispatch_id": envelope["dispatch_id"],
            "provider_domain": envelope["provider_domain"],
            "operation": envelope["operation"],
            "provider_idempotency_key": idempotency_key,
            "provider_request_id": "MOCK-" + digest(envelope)[:24],
            "response_status": 200,
            "response_body_sha256": digest(
                {
                    "dispatch_id": envelope["dispatch_id"],
                    "payload_sha256": envelope["payload_sha256"],
                    "state": "MOCK_PROVIDER_CONFORMANCE_ONLY",
                }
            ),
            "observed_at": envelope["prepared_at"],
            "external_mutation_performed": False,
            "live_provider_operation_proven": False,
        }
        receipt["provider_receipt_sha256"] = digest(receipt)
        self._receipts[idempotency_key] = deepcopy(receipt)
        return receipt


class ProviderDispatchOutboxCommercialControlPlane(
    IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane
):
    """V11 service-platform provider dispatch preparation and receipt boundary.

    V10 makes local owner-reserved action retries exact and crash-safe. V11 adds
    a durable provider dispatch outbox whose stable provider idempotency key is
    cryptographically derived from the committed V10 action, accepted provider
    authority snapshot and exact provider command. A deterministic mock adapter
    proves contract conformance. Live provider receipt admission remains held
    until a concrete provider-native verifier and fresh external proof exist.
    """

    CAPABILITY_REVISION = "AO-COMMERCIAL-PROVIDER-DISPATCH-OUTBOX-V11"
    STAGE_SCOPE = ["C03", "C06", "C07", "C11", "C14", "C15"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._verify_provider_dispatch_state()

    def _committed_action_record(
        self, *, action: str, object_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        collection = self._ACTION_COLLECTIONS.get(action)
        if collection is None:
            raise ValueError("unsupported provider dispatch action")
        record = self._read_state().get(collection, {}).get(object_id)
        if record is None:
            raise KeyError("committed authority action not found")
        seal = self._verify_idempotency_seal(
            record,
            expected_action=action,
            expected_object_id=object_id,
        )
        if seal is None:
            raise RuntimeError("provider dispatch requires a V10 idempotency seal")
        return dict(record), dict(seal)

    @staticmethod
    def _dispatch_payload(
        *,
        action: str,
        object_id: str,
        provider_domain: str,
        operation: str,
        payload: dict[str, Any],
        seal: dict[str, Any],
        prepared_at: str,
    ) -> dict[str, Any]:
        payload_sha256 = digest(payload)
        provider_idempotency_key = digest(
            {
                "action": action,
                "object_id": object_id,
                "intent_sha256": seal["intent_sha256"],
                "transaction_id": seal["transaction_id"],
                "snapshot_sha256": seal["snapshot_sha256"],
                "acceptance_entry_sha256": seal["acceptance_entry_sha256"],
                "provider_domain": provider_domain,
                "operation": operation,
                "payload_sha256": payload_sha256,
            }
        )
        dispatch_id = "DISPATCH-" + provider_idempotency_key[:24]
        return {
            "state": "PREPARED_PROVIDER_PROOF_REQUIRED",
            "dispatch_id": dispatch_id,
            "action": action,
            "object_id": object_id,
            "provider_domain": provider_domain,
            "operation": operation,
            "payload_sha256": payload_sha256,
            "provider_idempotency_key": provider_idempotency_key,
            "action_intent_sha256": seal["intent_sha256"],
            "action_transaction_id": seal["transaction_id"],
            "authority_snapshot_sha256": seal["snapshot_sha256"],
            "acceptance_entry_sha256": seal["acceptance_entry_sha256"],
            "prepared_at": prepared_at,
            "external_mutation_performed": False,
            "live_provider_operation_proven": False,
            "provider_receipt": None,
        }

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
            if receipt.get("receipt_class") == MOCK_PROVIDER_RECEIPT_CLASS:
                if record.get("state") != (
                    "MOCK_PROVIDER_CONFORMANCE_VERIFIED_"
                    "LIVE_PROVIDER_PROOF_REQUIRED"
                ):
                    raise RuntimeError("mock provider dispatch state invalid")
                if receipt.get("external_mutation_performed") is not False:
                    raise RuntimeError("mock provider receipt claimed external mutation")
                if receipt.get("live_provider_operation_proven") is not False:
                    raise RuntimeError("mock provider receipt claimed live operation")
            else:
                raise RuntimeError("unadmitted provider receipt class")
        return dict(record)

    def prepare_provider_dispatch(
        self,
        *,
        action: str,
        object_id: str,
        provider_domain: str,
        operation: str,
        payload: dict[str, Any],
        now: str | None = None,
    ) -> dict[str, Any]:
        if self.authority_profile != "LIVE_PROVIDER_AUTHORITY":
            raise RuntimeError("provider dispatch requires live provider authority profile")
        if not provider_domain or not operation:
            raise ValueError("provider domain and operation are required")
        current = now or utc_now()
        with self._action_coordination_locked():
            _, seal = self._committed_action_record(action=action, object_id=object_id)
            candidate = self._dispatch_payload(
                action=action,
                object_id=object_id,
                provider_domain=provider_domain,
                operation=operation,
                payload=payload,
                seal=seal,
                prepared_at=current,
            )
            dispatch_id = candidate["dispatch_id"]
            state = self._read_state()
            dispatches = state.setdefault("provider_dispatches", {})
            existing = dispatches.get(dispatch_id)
            if existing is not None:
                self._verify_dispatch_record(existing)
                comparable = dict(existing)
                comparable.pop("record_sha256", None)
                candidate_without_hash = dict(candidate)
                if comparable != candidate_without_hash:
                    raise ValueError("provider dispatch conflict for stable idempotency key")
                return dict(existing)
            candidate["record_sha256"] = digest(candidate)
            dispatches[dispatch_id] = candidate
            self._write_state(state)
            self._ledger("C07", "provider_dispatch.prepared", dispatch_id, candidate)
            return dict(candidate)

    def admit_provider_dispatch_receipt(
        self,
        dispatch_id: str,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        with self._action_coordination_locked():
            state = self._read_state()
            dispatches = state.setdefault("provider_dispatches", {})
            record = dispatches.get(dispatch_id)
            if record is None:
                raise KeyError("provider dispatch not found")
            self._verify_dispatch_record(record)
            receipt_class = receipt.get("receipt_class")
            if receipt_class == LIVE_PROVIDER_RECEIPT_CLASS:
                raise RuntimeError(
                    "live provider receipt admission requires a concrete "
                    "provider-native verifier and fresh external proof"
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
            existing = record.get("provider_receipt")
            if existing is not None:
                if existing != receipt:
                    raise ValueError("provider receipt conflict")
                return dict(record)
            updated = dict(record)
            updated.pop("record_sha256", None)
            updated["state"] = (
                "MOCK_PROVIDER_CONFORMANCE_VERIFIED_"
                "LIVE_PROVIDER_PROOF_REQUIRED"
            )
            updated["provider_receipt"] = deepcopy(receipt)
            updated["record_sha256"] = digest(updated)
            dispatches[dispatch_id] = updated
            self._write_state(state)
            self._ledger("C07", "provider_dispatch.mock_receipt_admitted", dispatch_id, updated)
            return dict(updated)

    def _verify_provider_dispatch_state(self) -> bool:
        state = self._read_state()
        for dispatch_id, record in state.get("provider_dispatches", {}).items():
            verified = self._verify_dispatch_record(record)
            if verified.get("dispatch_id") != dispatch_id:
                raise RuntimeError("provider dispatch identity invalid")
            self._committed_action_record(
                action=str(verified["action"]),
                object_id=str(verified["object_id"]),
            )
        return True

    def provider_dispatch_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            self._verify_provider_dispatch_state()
            records = list(self._read_state().get("provider_dispatches", {}).values())
            return {
                "capability_revision": self.CAPABILITY_REVISION,
                "integrity": "VERIFIED",
                "stage_scope": list(self.STAGE_SCOPE),
                "prepared_dispatches": len(records),
                "mock_conformance_receipts": sum(
                    1
                    for record in records
                    if record.get("provider_receipt", {}).get("receipt_class")
                    == MOCK_PROVIDER_RECEIPT_CLASS
                ),
                "live_provider_receipts": 0,
                "stable_provider_idempotency_key": True,
                "exact_prepare_retry_returns_original_record": True,
                "conflicting_dispatch_rejected": True,
                "mock_receipt_replay_is_idempotent": True,
                "live_receipt_requires_provider_native_verifier": True,
                "external_mutation_performed": False,
                "live_provider_operation_proven": False,
                "distributed_provider_exactly_once_proven": False,
            }

    def governed_authority_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            result = super().governed_authority_readback()
            result["canonical_class"] = self.__class__.__name__
            result["predecessor_class"] = (
                "IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane"
            )
            result["provider_dispatch_outbox"] = self.provider_dispatch_readback()
            return result
