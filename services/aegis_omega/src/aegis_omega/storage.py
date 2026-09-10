from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Protocol

from .schemas import Assessment, SealedEvent
from .evidence_chain import compile_evidence_chain


class IdempotencyCollision(RuntimeError):
    pass


def _request_doc_key(request_id: str) -> str:
    """Return a provider-safe deterministic Firestore document id."""
    return hashlib.sha256(request_id.encode("utf-8")).hexdigest()


def _legacy_request_doc_key_if_safe(request_id: str) -> str | None:
    """Legacy raw ids are read only when they are valid Firestore path segments."""
    if not request_id or "/" in request_id or request_id in {".", ".."}:
        return None
    if request_id.startswith("__") and request_id.endswith("__"):
        return None
    if len(request_id.encode("utf-8")) > 1500:
        return None
    return request_id


def _verify_request_record(data: dict, request_id: str, request_hash: str) -> str:
    stored_id = str(data.get("request_id") or "")
    stored_hash = str(data.get("request_hash") or "")
    case_id = str(data.get("case_id") or "")
    if stored_id and stored_id != request_id:
        raise IdempotencyCollision("AEGIS_IDEMPOTENCY_KEY_COLLISION")
    if stored_hash != request_hash:
        raise IdempotencyCollision("AEGIS_IDEMPOTENCY_KEY_COLLISION")
    if not case_id:
        raise RuntimeError("AEGIS_REQUEST_CASE_MISSING")
    return case_id


class CaseStore(Protocol):
    def put(self, assessment: Assessment, events: list[SealedEvent], request_id: str = "", request_hash: str = "") -> dict: ...
    def get(self, case_id: str) -> dict | None: ...
    def resolve_request(self, request_id: str, request_hash: str) -> dict | None: ...
    def outbox_state(self, case_id: str) -> dict | None: ...
    def claim_outbox(self, case_id: str, claimant: str, ttl_seconds: int = 60) -> bool: ...
    def release_outbox_claim(self, case_id: str, claimant: str) -> None: ...
    def mark_outbox_delivered(self, case_id: str, provider_ref: str = "", claimant: str = "") -> None: ...


class InMemoryCaseStore:
    def __init__(self):
        from threading import RLock
        self._lock = RLock()
        self._cases: dict[str, dict] = {}
        self._requests: dict[str, tuple[str, str]] = {}
        self._outbox: dict[str, dict] = {}

    def put(self, assessment, events, request_id="", request_hash=""):
        with self._lock:
            if request_id:
                prior = self._requests.get(request_id)
                if prior:
                    prior_hash, prior_case = prior
                    if prior_hash != request_hash:
                        raise IdempotencyCollision("AEGIS_IDEMPOTENCY_KEY_COLLISION")
                    return self._cases[prior_case]
            payload = {
                "assessment": assessment.model_dump(mode="json"),
                "events": [e.model_dump(mode="json") for e in events],
                "evidence_chain": compile_evidence_chain(events),
                "request_id": request_id,
                "request_hash": request_hash,
            }
            self._cases[assessment.case_id] = payload
            self._outbox[assessment.case_id] = {
                "delivered": False,
                "provider_ref": "",
                "claim_owner": "",
                "claim_expires_at": None,
            }
            if request_id:
                self._requests[request_id] = (request_hash, assessment.case_id)
            return payload

    def get(self, case_id):
        with self._lock:
            return self._cases.get(case_id)

    def resolve_request(self, request_id, request_hash):
        if not request_id:
            return None
        with self._lock:
            prior = self._requests.get(request_id)
            if not prior:
                return None
            prior_hash, case_id = prior
            if prior_hash != request_hash:
                raise IdempotencyCollision("AEGIS_IDEMPOTENCY_KEY_COLLISION")
            return self._cases.get(case_id)

    def outbox_state(self, case_id):
        with self._lock:
            value = self._outbox.get(case_id)
            return dict(value) if value is not None else None

    def claim_outbox(self, case_id, claimant, ttl_seconds=60):
        if not claimant:
            raise RuntimeError("AEGIS_OUTBOX_CLAIMANT_REQUIRED")
        now = datetime.now(timezone.utc)
        with self._lock:
            state = self._outbox.get(case_id)
            if state is None:
                raise RuntimeError("AEGIS_OUTBOX_CASE_MISSING")
            if state.get("delivered") is True:
                return False
            owner = str(state.get("claim_owner") or "")
            expires = state.get("claim_expires_at")
            if owner and owner != claimant and isinstance(expires, datetime) and expires > now:
                return False
            state["claim_owner"] = claimant
            state["claim_expires_at"] = now + timedelta(seconds=max(1, int(ttl_seconds)))
            return True

    def release_outbox_claim(self, case_id, claimant):
        with self._lock:
            state = self._outbox.get(case_id)
            if state is None or state.get("delivered") is True:
                return
            if str(state.get("claim_owner") or "") == claimant:
                state["claim_owner"] = ""
                state["claim_expires_at"] = None

    def mark_outbox_delivered(self, case_id, provider_ref="", claimant=""):
        with self._lock:
            state = self._outbox.get(case_id)
            if state is None:
                raise RuntimeError("AEGIS_OUTBOX_CASE_MISSING")
            owner = str(state.get("claim_owner") or "")
            if claimant and owner not in {"", claimant}:
                raise RuntimeError("AEGIS_OUTBOX_CLAIM_MISMATCH")
            self._outbox[case_id] = {
                "delivered": True,
                "provider_ref": provider_ref,
                "claim_owner": "",
                "claim_expires_at": None,
            }


class FirestoreCaseStore:
    def __init__(self, project: str | None = None):
        from google.cloud import firestore
        self.firestore = firestore
        self.client = firestore.Client(project=project or None)

    def _request_refs(self, request_id: str):
        primary = self.client.collection("aegis_requests").document(_request_doc_key(request_id))
        legacy_key = _legacy_request_doc_key_if_safe(request_id)
        legacy = None
        if legacy_key and legacy_key != primary.id:
            legacy = self.client.collection("aegis_requests").document(legacy_key)
        return primary, legacy

    def put(self, assessment, events, request_id="", request_hash=""):
        payload = {
            "assessment": assessment.model_dump(mode="json"),
            "events": [e.model_dump(mode="json") for e in events],
            "evidence_chain": compile_evidence_chain(events),
            "request_id": request_id,
            "request_hash": request_hash,
        }
        case_ref = self.client.collection("aegis_cases").document(assessment.case_id)
        outbox_ref = self.client.collection("aegis_outbox").document(assessment.case_id)
        outbox_seed = {
            "delivered": False,
            "provider_ref": "",
            "claim_owner": "",
            "claim_expires_at": None,
        }
        if not request_id:
            batch = self.client.batch()
            batch.set(case_ref, payload)
            batch.set(outbox_ref, outbox_seed)
            batch.commit()
            return payload

        req_ref, legacy_ref = self._request_refs(request_id)
        transaction = self.client.transaction()

        @self.firestore.transactional
        def txn(t):
            req = req_ref.get(transaction=t)
            legacy = legacy_ref.get(transaction=t) if legacy_ref is not None and not req.exists else None
            record = req if req.exists else legacy if legacy is not None and legacy.exists else None
            if record is not None:
                data = record.to_dict() or {}
                case_id = _verify_request_record(data, request_id, request_hash)
                existing_case_ref = self.client.collection("aegis_cases").document(case_id)
                existing_case = existing_case_ref.get(transaction=t)
                if not existing_case.exists:
                    raise RuntimeError("AEGIS_REQUEST_CASE_MISSING")
                if not req.exists:
                    t.set(req_ref, {"request_id": request_id, "request_hash": request_hash, "case_id": case_id})
                return existing_case.to_dict()
            t.set(case_ref, payload)
            t.set(req_ref, {"request_id": request_id, "request_hash": request_hash, "case_id": assessment.case_id})
            t.set(outbox_ref, outbox_seed)
            return payload

        return txn(transaction)

    def get(self, case_id):
        doc = self.client.collection("aegis_cases").document(case_id).get()
        return doc.to_dict() if doc.exists else None

    def resolve_request(self, request_id, request_hash):
        if not request_id:
            return None
        req_ref, legacy_ref = self._request_refs(request_id)
        doc = req_ref.get()
        if not doc.exists and legacy_ref is not None:
            doc = legacy_ref.get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        case_id = _verify_request_record(data, request_id, request_hash)
        return self.get(case_id)

    def outbox_state(self, case_id):
        doc = self.client.collection("aegis_outbox").document(case_id).get()
        return doc.to_dict() if doc.exists else None

    def claim_outbox(self, case_id, claimant, ttl_seconds=60):
        if not claimant:
            raise RuntimeError("AEGIS_OUTBOX_CLAIMANT_REQUIRED")
        ref = self.client.collection("aegis_outbox").document(case_id)
        transaction = self.client.transaction()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=max(1, int(ttl_seconds)))

        @self.firestore.transactional
        def txn(t):
            doc = ref.get(transaction=t)
            if not doc.exists:
                raise RuntimeError("AEGIS_OUTBOX_CASE_MISSING")
            state = doc.to_dict() or {}
            if state.get("delivered") is True:
                return False
            owner = str(state.get("claim_owner") or "")
            expires = state.get("claim_expires_at")
            if owner and owner != claimant and isinstance(expires, datetime) and expires > now:
                return False
            t.set(ref, {"claim_owner": claimant, "claim_expires_at": expires_at}, merge=True)
            return True

        return bool(txn(transaction))

    def release_outbox_claim(self, case_id, claimant):
        ref = self.client.collection("aegis_outbox").document(case_id)
        transaction = self.client.transaction()

        @self.firestore.transactional
        def txn(t):
            doc = ref.get(transaction=t)
            if not doc.exists:
                return
            state = doc.to_dict() or {}
            if state.get("delivered") is True:
                return
            if str(state.get("claim_owner") or "") == claimant:
                t.set(ref, {"claim_owner": "", "claim_expires_at": None}, merge=True)

        txn(transaction)

    def mark_outbox_delivered(self, case_id, provider_ref="", claimant=""):
        ref = self.client.collection("aegis_outbox").document(case_id)
        transaction = self.client.transaction()

        @self.firestore.transactional
        def txn(t):
            doc = ref.get(transaction=t)
            if not doc.exists:
                raise RuntimeError("AEGIS_OUTBOX_CASE_MISSING")
            state = doc.to_dict() or {}
            owner = str(state.get("claim_owner") or "")
            if claimant and owner not in {"", claimant}:
                raise RuntimeError("AEGIS_OUTBOX_CLAIM_MISMATCH")
            t.set(
                ref,
                {
                    "delivered": True,
                    "provider_ref": provider_ref,
                    "claim_owner": "",
                    "claim_expires_at": None,
                },
                merge=True,
            )

        txn(transaction)


def build_case_store(kind: str, project: str = ""):
    return FirestoreCaseStore(project or None) if kind.lower() == "firestore" else InMemoryCaseStore()
