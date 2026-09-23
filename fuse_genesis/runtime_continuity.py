from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json, re, sqlite3
from pathlib import Path
from typing import Any, Callable, Mapping

SCHEMA="FUSE-GENESIS-RUNTIME-CONTINUITY-V1"
HEX64=re.compile(r"^[0-9a-f]{64}$")

class ContinuityError(ValueError): pass
class DispatchRejected(ContinuityError): pass
class DispatchCollision(ContinuityError): pass
class EffectCollision(ContinuityError): pass
class UnknownEffect(ContinuityError): pass

def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(x): return sha256(canon(x).encode()).hexdigest()
def payload_digest(x): return sha256(canon(x).encode()).hexdigest()
def _required(v,label):
    value=str(v).strip()
    if not value: raise ContinuityError(f"{label}_REQUIRED")
    return value
def _hex64(v,label):
    value=str(v).lower()
    if not HEX64.fullmatch(value): raise ContinuityError(f"{label}_INVALID")
    return value

@dataclass(frozen=True,slots=True)
class DispatchEnvelope:
    dispatch_id:str
    task_id:str
    idempotency_key:str
    mission_id:str
    scheduler_id:str
    source_epoch_digest:str
    payload_sha256:str
    authority_ref:str
    provider_event_id:str
    issued_at:int
    expires_at:int
    effect_class:str="A1_INTERNAL"

    def validate(self):
        for value,label in (
            (self.dispatch_id,"DISPATCH_ID"),(self.task_id,"TASK_ID"),
            (self.idempotency_key,"IDEMPOTENCY_KEY"),(self.mission_id,"MISSION_ID"),
            (self.authority_ref,"AUTHORITY_REF"),(self.provider_event_id,"PROVIDER_EVENT_ID")):
            _required(value,label)
        if self.scheduler_id!="GOOGLE_APPS_SCRIPT":
            raise DispatchRejected("SCHEDULER_AUTHORITY_MUST_BE_GOOGLE_APPS_SCRIPT")
        _hex64(self.source_epoch_digest,"SOURCE_EPOCH_DIGEST")
        _hex64(self.payload_sha256,"PAYLOAD_SHA256")
        if isinstance(self.issued_at,bool) or not isinstance(self.issued_at,int):
            raise ContinuityError("ISSUED_AT_INVALID")
        if isinstance(self.expires_at,bool) or not isinstance(self.expires_at,int) or self.expires_at<=self.issued_at:
            raise ContinuityError("EXPIRES_AT_INVALID")
        if self.effect_class not in {"A0_READ_ONLY","A1_INTERNAL","A2_EXACT_PREAUTHORIZED"}:
            raise DispatchRejected("EFFECT_CLASS_INVALID")
        return self

    @property
    def semantic_sha256(self):
        self.validate()
        return digest({
            "dispatch_id":self.dispatch_id,"task_id":self.task_id,
            "idempotency_key":self.idempotency_key,"mission_id":self.mission_id,
            "scheduler_id":self.scheduler_id,"source_epoch_digest":self.source_epoch_digest,
            "payload_sha256":self.payload_sha256,"authority_ref":self.authority_ref,
            "provider_event_id":self.provider_event_id,"issued_at":self.issued_at,
            "expires_at":self.expires_at,"effect_class":self.effect_class,
        })

class DispatchIngress:
    """Durable admission. Authority must be verified by the provider adapter."""
    def __init__(self,path):
        self.path=Path(path)
        self.db=sqlite3.connect(str(self.path),isolation_level=None,timeout=5)
        self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS dispatches(
            dispatch_id TEXT PRIMARY KEY,idempotency_key TEXT UNIQUE NOT NULL,task_id TEXT NOT NULL,
            semantic_sha256 TEXT NOT NULL,payload_sha256 TEXT NOT NULL,source_epoch_digest TEXT NOT NULL,
            scheduler_id TEXT NOT NULL,authority_ref TEXT NOT NULL,provider_event_id TEXT NOT NULL,
            accepted_at INTEGER NOT NULL)""")
    def close(self): self.db.close()
    def row(self,dispatch_id):
        r=self.db.execute("SELECT * FROM dispatches WHERE dispatch_id=?",(dispatch_id,)).fetchone()
        return dict(r) if r else None
    def accept(self,envelope:DispatchEnvelope,payload:Mapping[str,Any],*,current_epoch_digest:str,now:int,
               authority_verifier:Callable[[str,str],bool]):
        envelope.validate()
        _hex64(current_epoch_digest,"CURRENT_EPOCH_DIGEST")
        if now<envelope.issued_at or now>=envelope.expires_at:
            raise DispatchRejected("DISPATCH_EXPIRED_OR_NOT_YET_VALID")
        if envelope.source_epoch_digest!=current_epoch_digest:
            raise DispatchRejected("STALE_SOURCE_EPOCH")
        if payload_digest(payload)!=envelope.payload_sha256:
            raise DispatchRejected("PAYLOAD_HASH_MISMATCH")
        if not authority_verifier(envelope.authority_ref,envelope.provider_event_id):
            raise DispatchRejected("PROVIDER_AUTHORITY_READBACK_REQUIRED")
        existing=self.db.execute(
            "SELECT * FROM dispatches WHERE dispatch_id=? OR idempotency_key=?",
            (envelope.dispatch_id,envelope.idempotency_key)).fetchone()
        if existing:
            if existing["semantic_sha256"]!=envelope.semantic_sha256:
                raise DispatchCollision("DISPATCH_IDEMPOTENCY_COLLISION")
            return dict(existing)
        self.db.execute("""INSERT INTO dispatches VALUES(?,?,?,?,?,?,?,?,?,?)""",(
            envelope.dispatch_id,envelope.idempotency_key,envelope.task_id,envelope.semantic_sha256,
            envelope.payload_sha256,envelope.source_epoch_digest,envelope.scheduler_id,
            envelope.authority_ref,envelope.provider_event_id,now))
        return self.row(envelope.dispatch_id)

class EffectJournal:
    def __init__(self,path):
        self.path=Path(path)
        self.db=sqlite3.connect(str(self.path),isolation_level=None,timeout=5)
        self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS effects(
          effect_id TEXT PRIMARY KEY,idempotency_key TEXT UNIQUE NOT NULL,request_sha256 TEXT NOT NULL,
          state TEXT NOT NULL,result_sha256 TEXT,readback_json TEXT,updated_at INTEGER NOT NULL)""")
    def close(self): self.db.close()
    def row(self,effect_id):
        r=self.db.execute("SELECT * FROM effects WHERE effect_id=?",(effect_id,)).fetchone()
        return dict(r) if r else None
    def prepare(self,effect_id,idempotency_key,request,now):
        req=payload_digest(request)
        existing=self.db.execute("SELECT * FROM effects WHERE effect_id=? OR idempotency_key=?",
                                 (effect_id,idempotency_key)).fetchone()
        if existing:
            if existing["request_sha256"]!=req:
                raise EffectCollision("EFFECT_IDEMPOTENCY_COLLISION")
            return dict(existing)
        self.db.execute("INSERT INTO effects VALUES(?,?,?,'PREPARED',NULL,NULL,?)",
                        (effect_id,idempotency_key,req,now))
        return self.row(effect_id)
    def _state(self,effect_id,state,now,*,result=None,readback=None):
        if not self.row(effect_id): raise KeyError(effect_id)
        result_sha=None if result is None else payload_digest(result)
        rb=None if readback is None else canon(readback)
        self.db.execute("""UPDATE effects SET state=?,result_sha256=COALESCE(?,result_sha256),
                           readback_json=COALESCE(?,readback_json),updated_at=? WHERE effect_id=?""",
                        (state,result_sha,rb,now,effect_id))
        return self.row(effect_id)
    def start(self,effect_id,now):
        row=self.row(effect_id)
        if not row: raise KeyError(effect_id)
        if row["state"]=="UNKNOWN": raise UnknownEffect("READBACK_EFFECT_BEFORE_RETRY")
        if row["state"] in {"APPLIED","READBACK_VERIFIED","COMPENSATED"}:
            return row
        if row["state"]!="PREPARED": raise ContinuityError("EFFECT_STATE_INVALID")
        return self._state(effect_id,"EXECUTING",now)
    def mark_unknown(self,effect_id,now,reason):
        return self._state(effect_id,"UNKNOWN",now,readback={"reason":str(reason)})
    def mark_applied(self,effect_id,result,now):
        return self._state(effect_id,"APPLIED",now,result=result)
    def readback(self,effect_id,*,applied:bool,now:int,evidence:Mapping[str,Any]):
        row=self.row(effect_id)
        if not row: raise KeyError(effect_id)
        if applied:
            return self._state(effect_id,"READBACK_VERIFIED",now,readback=dict(evidence))
        if row["state"]=="UNKNOWN":
            return self._state(effect_id,"PREPARED",now,readback=dict(evidence))
        return self._state(effect_id,"UNKNOWN",now,readback=dict(evidence))
    def compensate(self,effect_id,now,evidence):
        return self._state(effect_id,"COMPENSATED",now,readback=dict(evidence))
    def retry_allowed(self,effect_id):
        row=self.row(effect_id)
        return bool(row and row["state"]=="PREPARED")

class EffectExecutor:
    """Exactly-once coordinator for one external effect identity."""
    def __init__(self,journal:EffectJournal):
        self.journal=journal
    def execute(self,*,effect_id,idempotency_key,request,now,effect_fn,readback_fn):
        row=self.journal.prepare(effect_id,idempotency_key,request,now)
        if row["state"]=="READBACK_VERIFIED":
            return {"state":"IDEMPOTENT_REPLAY","effect":row}
        if row["state"]=="UNKNOWN":
            observed=readback_fn()
            row=self.journal.readback(effect_id,applied=bool(observed.get("applied")),now=now,evidence=observed)
            if row["state"]=="READBACK_VERIFIED":
                return {"state":"READBACK_RECOVERED","effect":row}
        if not self.journal.retry_allowed(effect_id):
            if self.journal.row(effect_id)["state"]=="APPLIED":
                observed=readback_fn()
                row=self.journal.readback(effect_id,applied=bool(observed.get("applied")),now=now,evidence=observed)
                if row["state"]=="READBACK_VERIFIED":
                    return {"state":"READBACK_RECOVERED","effect":row}
            if not self.journal.retry_allowed(effect_id):
                raise UnknownEffect("EFFECT_NOT_RETRYABLE_WITHOUT_READBACK")
        self.journal.start(effect_id,now)
        try:
            result=effect_fn()
        except Exception as exc:
            self.journal.mark_unknown(effect_id,now,str(exc))
            raise
        self.journal.mark_applied(effect_id,result,now)
        observed=readback_fn()
        row=self.journal.readback(effect_id,applied=bool(observed.get("applied")),now=now,evidence=observed)
        if row["state"]!="READBACK_VERIFIED":
            raise UnknownEffect("POST_EFFECT_READBACK_NOT_VERIFIED")
        return {"state":"EXECUTED_AND_VERIFIED","effect":row,"result":result}

@dataclass(frozen=True,slots=True)
class WatchdogAssessment:
    state:str
    reasons:tuple[str,...]

def assess_runtime(*,last_heartbeat:float,now:float,max_gap_seconds:float,pending_tasks:int,
                   oldest_task_age_seconds:float,effect_state:str|None=None)->WatchdogAssessment:
    reasons=[]
    if max_gap_seconds<=0: raise ContinuityError("MAX_GAP_INVALID")
    if now-last_heartbeat>max_gap_seconds: reasons.append("HEARTBEAT_STALE")
    if pending_tasks>0 and oldest_task_age_seconds>max_gap_seconds: reasons.append("QUEUE_STALLED")
    if effect_state=="UNKNOWN": reasons.append("UNKNOWN_EFFECT")
    return WatchdogAssessment("HEALTHY" if not reasons else "DEGRADED",tuple(reasons))
