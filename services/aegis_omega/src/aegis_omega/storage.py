from __future__ import annotations
from typing import Protocol
from .schemas import Assessment, SealedEvent
from .evidence_chain import compile_evidence_chain

class IdempotencyCollision(RuntimeError):
    pass

class CaseStore(Protocol):
    def put(self, assessment: Assessment, events: list[SealedEvent], request_id: str = "", request_hash: str = "") -> dict: ...
    def get(self, case_id: str) -> dict | None: ...
    def resolve_request(self, request_id: str, request_hash: str) -> dict | None: ...
    def outbox_state(self, case_id: str) -> dict | None: ...
    def mark_outbox_delivered(self, case_id: str, provider_ref: str = "") -> None: ...

class InMemoryCaseStore:
    def __init__(self):
        from threading import RLock
        self._lock = RLock(); self._cases={}; self._requests={}; self._outbox={}
    def put(self, assessment, events, request_id="", request_hash=""):
        with self._lock:
            if request_id:
                prior=self._requests.get(request_id)
                if prior:
                    prior_hash, prior_case=prior
                    if prior_hash != request_hash: raise IdempotencyCollision("AEGIS_IDEMPOTENCY_KEY_COLLISION")
                    return self._cases[prior_case]
            payload={"assessment":assessment.model_dump(mode="json"),"events":[e.model_dump(mode="json") for e in events],"evidence_chain":compile_evidence_chain(events),"request_id":request_id,"request_hash":request_hash}
            self._cases[assessment.case_id]=payload; self._outbox[assessment.case_id]={"delivered":False,"provider_ref":""}
            if request_id: self._requests[request_id]=(request_hash,assessment.case_id)
            return payload
    def get(self,case_id):
        with self._lock: return self._cases.get(case_id)
    def resolve_request(self,request_id,request_hash):
        if not request_id:return None
        with self._lock:
            prior=self._requests.get(request_id)
            if not prior:return None
            prior_hash,case_id=prior
            if prior_hash != request_hash: raise IdempotencyCollision("AEGIS_IDEMPOTENCY_KEY_COLLISION")
            return self._cases.get(case_id)
    def outbox_state(self,case_id):
        with self._lock:
            value=self._outbox.get(case_id); return dict(value) if value is not None else None
    def mark_outbox_delivered(self,case_id,provider_ref=""):
        with self._lock:
            if case_id not in self._outbox: raise RuntimeError("AEGIS_OUTBOX_CASE_MISSING")
            self._outbox[case_id]={"delivered":True,"provider_ref":provider_ref}

class FirestoreCaseStore:
    def __init__(self, project: str | None = None):
        from google.cloud import firestore
        self.firestore=firestore; self.client=firestore.Client(project=project or None)
    def put(self,assessment,events,request_id="",request_hash=""):
        payload={"assessment":assessment.model_dump(mode="json"),"events":[e.model_dump(mode="json") for e in events],"evidence_chain":compile_evidence_chain(events),"request_id":request_id,"request_hash":request_hash}
        case_ref=self.client.collection("aegis_cases").document(assessment.case_id)
        outbox_ref=self.client.collection("aegis_outbox").document(assessment.case_id)
        if not request_id:
            batch=self.client.batch(); batch.set(case_ref,payload); batch.set(outbox_ref,{"delivered":False,"provider_ref":""}); batch.commit(); return payload
        req_ref=self.client.collection("aegis_requests").document(request_id)
        transaction=self.client.transaction()
        @self.firestore.transactional
        def txn(t):
            req=req_ref.get(transaction=t)
            if req.exists:
                data=req.to_dict() or {}
                if data.get("request_hash") != request_hash: raise IdempotencyCollision("AEGIS_IDEMPOTENCY_KEY_COLLISION")
                existing_case=self.client.collection("aegis_cases").document(str(data.get("case_id"))).get(transaction=t)
                return existing_case.to_dict() if existing_case.exists else None
            t.set(case_ref,payload); t.set(req_ref,{"request_hash":request_hash,"case_id":assessment.case_id}); t.set(outbox_ref,{"delivered":False,"provider_ref":""}); return payload
        return txn(transaction)
    def get(self,case_id):
        doc=self.client.collection("aegis_cases").document(case_id).get(); return doc.to_dict() if doc.exists else None
    def resolve_request(self,request_id,request_hash):
        if not request_id:return None
        doc=self.client.collection("aegis_requests").document(request_id).get()
        if not doc.exists:return None
        data=doc.to_dict() or {}
        if data.get("request_hash") != request_hash: raise IdempotencyCollision("AEGIS_IDEMPOTENCY_KEY_COLLISION")
        return self.get(str(data.get("case_id")))
    def outbox_state(self,case_id):
        doc=self.client.collection("aegis_outbox").document(case_id).get(); return doc.to_dict() if doc.exists else None
    def mark_outbox_delivered(self,case_id,provider_ref=""):
        self.client.collection("aegis_outbox").document(case_id).set({"delivered":True,"provider_ref":provider_ref},merge=True)

def build_case_store(kind: str, project: str = ""):
    return FirestoreCaseStore(project or None) if kind.lower()=="firestore" else InMemoryCaseStore()
