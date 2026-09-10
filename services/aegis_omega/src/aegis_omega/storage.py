from __future__ import annotations

import hashlib
import time
from typing import Protocol

from .schemas import Assessment, SealedEvent
from .evidence_chain import compile_evidence_chain


class IdempotencyCollision(RuntimeError):
    pass


def _request_doc_key(request_id: str) -> str:
    """Map an arbitrary owner request id to a Firestore-safe deterministic key."""
    raw = str(request_id).encode("utf-8")
    return "r_" + hashlib.sha256(raw).hexdigest()


def _legacy_request_id_safe(request_id: str) -> bool:
    """Only probe a legacy raw Firestore document id when the id is provider-safe."""
    value = str(request_id or "")
    if not value or "/" in value or value in {".", ".."}:
        return False
    if value.startswith("__") and value.endswith("__"):
        return False
    return True


class CaseStore(Protocol):
    def put(self, assessment: Assessment, events: list[SealedEvent], request_id: str = "", request_hash: str = "") -> dict: ...
    def get(self, case_id: str) -> dict | None: ...
    def resolve_request(self, request_id: str, request_hash: str) -> dict | None: ...
    def outbox_state(self, case_id: str) -> dict | None: ...
    def claim_outbox_delivery(self, case_id: str, claimant_id: str, lease_seconds: float = 30.0) -> dict: ...
    def mark_outbox_delivered(self, case_id: str, provider_ref: str = "", claimant_id: str = "") -> None: ...
    def release_outbox_claim(self, case_id: str, claimant_id: str) -> None: ...


class InMemoryCaseStore:
    def __init__(self):
        from threading import RLock
        self._lock = RLock()
        self._cases = {}
        self._requests = {}
        self._outbox = {}

    @staticmethod
    def _new_outbox() -> dict:
        return {
            "delivered": False,
            "provider_ref": "",
            "claim_owner": "",
            "claim_expires_at": 0.0,
        }

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
            self._outbox[assessment.case_id] = self._new_outbox()
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

    def claim_outbox_delivery(self, case_id, claimant_id, lease_seconds=30.0):
        claimant = str(claimant_id or "").strip()
        if not claimant:
            raise ValueError("AEGIS_OUTBOX_CLAIMANT_REQUIRED")
        if float(lease_seconds) <= 0:
            raise ValueError("AEGIS_OUTBOX_CLAIM_LEASE_INVALID")
        now = time.time()
        with self._lock:
            state = self._outbox.get(case_id)
            if state is None:
                raise RuntimeError("AEGIS_OUTBOX_CASE_MISSING")
            if state.get("delivered") is True:
                return {**state, "claimed": False, "already_delivered": True}
            owner = str(state.get("claim_owner") or "")
            expires = float(state.get("claim_expires_at") or 0.0)
            if owner and owner != claimant and expires > now:
                return {**state, "claimed": False, "already_delivered": False}
            state["claim_owner"] = claimant
            state["claim_expires_at"] = now + float(lease_seconds)
            return {**state, "claimed": True, "already_delivered": False}

    def mark_outbox_delivered(self, case_id, provider_ref="", claimant_id=""):
        claimant = str(claimant_id or "").strip()
        with self._lock:
            state = self._outbox.get(case_id)
            if state is None:
                raise RuntimeError("AEGIS_OUTBOX_CASE_MISSING")
            owner = str(state.get("claim_owner") or "")
            if claimant and owner not in {"", claimant}:
                raise RuntimeError("AEGIS_OUTBOX_CLAIM_OWNERSHIP_MISMATCH")
            state.update({
                "delivered": True,
                "provider_ref": provider_ref,
                "claim_owner": "",
                "claim_expires_at": 0.0,
            })

    def release_outbox_claim(self, case_id, claimant_id):
        claimant = str(claimant_id or "").strip()
        with self._lock:
            state = self._outbox.get(case_id)
            if state is None or state.get("delivered") is True:
                return
            if str(state.get("claim_owner") or "") == claimant:
                state["claim_owner"] = ""
                state["claim_expires_at"] = 0.0


class FirestoreCaseStore:
    def __init__(self, project: str | None = None):
        from google.cloud import firestore
        self.firestore = firestore
        self.client = firestore.Client(project=project or None)

    @staticmethod
    def _new_outbox() -> dict:
        return {
            "delivered": False,
            "provider_ref": "",
            "claim_owner": "",
            "claim_expires_at": 0.0,
        }

    def _request_ref(self, request_id: str):
        return self.client.collection("aegis_requests").document(_request_doc_key(request_id))

    def _read_request_mapping(self, request_id: str):
        hashed = self._request_ref(request_id).get()
        if hashed.exists:
            return hashed
        # Migration-only fallback for records written before hashed request keys.
        if _legacy_request_id_safe(request_id):
            legacy = self.client.collection("aegis_requests").document(request_id).get()
            if legacy.exists:
                return legacy
        return None

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
        if not request_id:
            batch = self.client.batch()
            batch.set(case_ref, payload)
            batch.set(outbox_ref, self._new_outbox())
            batch.commit()
            return payload

        req_ref = self._request_ref(request_id)
        transaction = self.client.transaction()

        @self.firestore.transactional
        def txn(t):
            req = req_ref.get(transaction=t)
            if req.exists:
                data = req.to_dict() or {}
                if data.get("request_id") not in {None, "", request_id}:
                    raise IdempotencyCollision("AEGIS_REQUEST_KEY_COLLISION")
                if data.get("request_hash") != request_hash:
                    raise IdempotencyCollision("AEGIS_IDEMPOTENCY_KEY_COLLISION")
                existing_case = self.client.collection("aegis_cases").document(str(data.get("case_id"))).get(transaction=t)
                return existing_case.to_dict() if existing_case.exists else None
            t.set(case_ref, payload)
            t.set(req_ref, {
                "request_id": request_id,
                "request_hash": request_hash,
                "case_id": assessment.case_id,
            })
            t.set(outbox_ref, self._new_outbox())
            return payload

        return txn(transaction)

    def get(self, case_id):
        doc = self.client.collection("aegis_cases").document(case_id).get()
        return doc.to_dict() if doc.exists else None

    def resolve_request(self, request_id, request_hash):
        if not request_id:
            return None
        doc = self._read_request_mapping(request_id)
        if doc is None:
            return None
        data = doc.to_dict() or {}
        if data.get("request_id") not in {None, "", request_id}:
            raise IdempotencyCollision("AEGIS_REQUEST_KEY_COLLISION")
        if data.get("request_hash") != request_hash:
            raise IdempotencyCollision("AEGIS_IDEMPOTENCY_KEY_COLLISION")
        return self.get(str(data.get("case_id")))

    def outbox_state(self, case_id):
        doc = self.client.collection("aegis_outbox").document(case_id).get()
        return doc.to_dict() if doc.exists else None

    def claim_outbox_delivery(self, case_id, claimant_id, lease_seconds=30.0):
        claimant = str(claimant_id or "").strip()
        if not claimant:
            raise ValueError("AEGIS_OUTBOX_CLAIMANT_REQUIRED")
        if float(lease_seconds) <= 0:
            raise ValueError("AEGIS_OUTBOX_CLAIM_LEASE_INVALID")
        ref = self.client.collection("aegis_outbox").document(case_id)
        transaction = self.client.transaction()
        now = time.time()

        @self.firestore.transactional
        def txn(t):
            doc = ref.get(transaction=t)
            if not doc.exists:
                raise RuntimeError("AEGIS_OUTBOX_CASE_MISSING")
            state = doc.to_dict() or {}
            if state.get("delivered") is True:
                return {**state, "claimed": False, "already_delivered": True}
            owner = str(state.get("claim_owner") or "")
            expires = float(state.get("claim_expires_at") or 0.0)
            if owner and owner != claimant and expires > now:
                return {**state, "claimed": False, "already_delivered": False}
            t.set(ref, {"claim_owner": claimant, "claim_expires_at": now + float(lease_seconds)}, merge=True)
            return {**state, "claim_owner": claimant, "claim_expires_at": now + float(lease_seconds), "claimed": True, "already_delivered": False}

        return txn(transaction)

    def mark_outbox_delivered(self, case_id, provider_ref="", claimant_id=""):
        claimant = str(claimant_id or "").strip()
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
                raise RuntimeError("AEGIS_OUTBOX_CLAIM_OWNERSHIP_MISMATCH")
            t.set(ref, {
                "delivered": True,
                "provider_ref": provider_ref,
                "claim_owner": "",
                "claim_expires_at": 0.0,
            }, merge=True)

        txn(transaction)

    def release_outbox_claim(self, case_id, claimant_id):
        claimant = str(claimant_id or "").strip()
        if not claimant:
            return
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
                t.set(ref, {"claim_owner": "", "claim_expires_at": 0.0}, merge=True)

        txn(transaction)


def build_case_store(kind: str, project: str = ""):
    return FirestoreCaseStore(project or None) if kind.lower() == "firestore" else InMemoryCaseStore()
