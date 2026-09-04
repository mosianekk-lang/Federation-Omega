from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from hashlib import sha256
from collections import defaultdict
import json, sqlite3


def _json(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), default=str)


def digest(v):
    return sha256(_json(v).encode("utf-8")).hexdigest()


class Proof(str, Enum):
    DESCRIBED="DESCRIBED"; BUILT="BUILT"; TESTED="TESTED"; SOURCE_ADMITTED="SOURCE_ADMITTED"; PROVIDER_READBACK="PROVIDER_READBACK"; BEHAVIOUR_VERIFIED="BEHAVIOUR_VERIFIED"; VALUE_OBSERVED="VALUE_OBSERVED"


class Authority(str, Enum):
    A0="A0_OBSERVE"; A1="A1_INTERNAL"; A2="A2_PROVIDER_REVERSIBLE"; A3="A3_OWNER_RESERVED"


class Effect(str, Enum):
    NONE="NONE"; INTERNAL="INTERNAL_REVERSIBLE"; PROVIDER="PROVIDER_REVERSIBLE"; CONSEQUENTIAL="CONSEQUENTIAL"


PROOF_RANK={p:i for i,p in enumerate(Proof)}
AUTH_RANK={a:i for i,a in enumerate(Authority)}
EFFECT_RANK={e:i for i,e in enumerate(Effect)}


class Disposition(str, Enum):
    ADOPT="ADOPT"; ADAPT="ADAPT"; ALREADY_PRESENT="ALREADY_PRESENT"; NOT_APPLICABLE="NOT_APPLICABLE"; HELD="HELD"; REJECTED_WITH_REASON="REJECTED_WITH_REASON"; APPLIED="APPLIED"; READBACK_VERIFIED="READBACK_VERIFIED"; BEHAVIOUR_VERIFIED="BEHAVIOUR_VERIFIED"; VALUE_OBSERVED="VALUE_OBSERVED"; STALE_PENDING_REVALIDATION="STALE_PENDING_REVALIDATION"


@dataclass(frozen=True)
class KnowledgeDelta:
    delta_id:str
    sequence:int
    source_system:str
    source_epoch:str
    domain:str
    finding:str
    proof:Proof
    authority:Authority
    effect:Effect
    priority:str="P1"
    privacy:str="P1"
    matter_scope:tuple[str,...]=()
    tags:tuple[str,...]=()
    supersedes:tuple[str,...]=()

    def content_hash(self):
        d=asdict(self); d.pop("delta_id", None); return digest(d)


@dataclass(frozen=True)
class Receiver:
    receiver_id:str
    domains:tuple[str,...]
    tags:tuple[str,...]
    authority:Authority
    effect:Effect
    minimum_proof:Proof=Proof.TESTED
    privacy:tuple[str,...]=( "P0", "P1" )
    matter_scopes:tuple[str,...]=()


@dataclass(frozen=True)
class PolicyDecision:
    allow:bool
    code:str


class PolicyEngine:
    def evaluate(self, d:KnowledgeDelta, r:Receiver):
        if d.domain not in r.domains and not set(d.tags)&set(r.tags): return PolicyDecision(False,"NOT_APPLICABLE")
        if d.privacy not in r.privacy: return PolicyDecision(False,"PRIVACY_HELD")
        if d.matter_scope and r.matter_scopes and not set(d.matter_scope)&set(r.matter_scopes): return PolicyDecision(False,"MATTER_WALL")
        if PROOF_RANK[d.proof] < PROOF_RANK[r.minimum_proof]: return PolicyDecision(False,"PROOF_HELD")
        if AUTH_RANK[d.authority] > AUTH_RANK[r.authority]: return PolicyDecision(False,"AUTHORITY_HELD")
        if EFFECT_RANK[d.effect] > EFFECT_RANK[r.effect]: return PolicyDecision(False,"EFFECT_HELD")
        return PolicyDecision(True,"ALLOW")


class Ledger:
    def __init__(self, path=":memory:"):
        self.db=sqlite3.connect(path)
        self.db.row_factory=sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS deltas(seq INTEGER PRIMARY KEY, delta_id TEXT UNIQUE, content_hash TEXT UNIQUE, payload TEXT, superseded_by TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS acks(delta_id TEXT, receiver_id TEXT, disposition TEXT, proof_ref TEXT DEFAULT '', PRIMARY KEY(delta_id,receiver_id));
        CREATE TABLE IF NOT EXISTS watermarks(receiver_id TEXT PRIMARY KEY, seq INTEGER, state TEXT);
        CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY, payload_hash TEXT, state TEXT);
        CREATE TABLE IF NOT EXISTS workflow_events(mission_id TEXT, ordinal INTEGER, state TEXT, payload TEXT, PRIMARY KEY(mission_id,ordinal));
        """)
        self.db.commit()

    def head(self): return int(self.db.execute("SELECT COALESCE(MAX(seq),0) h FROM deltas").fetchone()["h"])

    def publish(self, d:KnowledgeDelta):
        if d.sequence != self.head()+1: raise RuntimeError("NON_MONOTONIC_SEQUENCE")
        self.db.execute("INSERT INTO deltas VALUES(?,?,?,?,?)",(d.sequence,d.delta_id,d.content_hash(),_json(asdict(d)),"")); self.db.commit()

    def ack(self, delta_id, receiver_id, disposition, proof_ref=""):
        self.db.execute("INSERT INTO acks VALUES(?,?,?,?) ON CONFLICT(delta_id,receiver_id) DO UPDATE SET disposition=excluded.disposition,proof_ref=excluded.proof_ref",(delta_id,receiver_id,disposition.value if hasattr(disposition,'value') else disposition,proof_ref)); self.db.commit()

    def watermark(self, receiver_id):
        row=self.db.execute("SELECT * FROM watermarks WHERE receiver_id=?",(receiver_id,)).fetchone(); return dict(row) if row else {"receiver_id":receiver_id,"seq":0,"state":"ACTIVE_STALE"}

    def set_watermark(self, receiver_id, seq, state):
        self.db.execute("INSERT INTO watermarks VALUES(?,?,?) ON CONFLICT(receiver_id) DO UPDATE SET seq=excluded.seq,state=excluded.state",(receiver_id,seq,state)); self.db.commit()

    def reserve(self, key, payload_hash):
        try: self.db.execute("INSERT INTO idempotency VALUES(?,?,?)",(key,payload_hash,"RESERVED")); self.db.commit(); return True
        except sqlite3.IntegrityError: return False

    def append_state(self, mission_id, state, payload=None):
        n=int(self.db.execute("SELECT COALESCE(MAX(ordinal),0)+1 n FROM workflow_events WHERE mission_id=?",(mission_id,)).fetchone()["n"])
        self.db.execute("INSERT INTO workflow_events VALUES(?,?,?,?)",(mission_id,n,state,_json(payload or {}))); self.db.commit(); return n

    def restore_state(self, mission_id):
        row=self.db.execute("SELECT state FROM workflow_events WHERE mission_id=? ORDER BY ordinal DESC LIMIT 1",(mission_id,)).fetchone(); return row["state"] if row else "CREATED"

    def supersede(self, old_id, new_id):
        self.db.execute("UPDATE deltas SET superseded_by=? WHERE delta_id=?",(new_id,old_id)); self.db.execute("UPDATE acks SET disposition=? WHERE delta_id=? AND disposition NOT IN (?,?)",(Disposition.STALE_PENDING_REVALIDATION.value,old_id,Disposition.NOT_APPLICABLE.value,Disposition.REJECTED_WITH_REASON.value)); self.db.commit()


@dataclass
class BusMessage:
    subject:str; seq:int; message_id:str; payload:dict; acked:set[str]


class ReplayBus:
    def __init__(self): self.seq=0; self.by_subject=defaultdict(list); self.ids={}
    def publish(self, subject, payload, message_id):
        if message_id in self.ids: return self.ids[message_id]
        self.seq+=1; m=BusMessage(subject,self.seq,message_id,payload,set()); self.by_subject[subject].append(m); self.ids[message_id]=m; return m
    def consume(self, subject, consumer, after=0): return [m for m in self.by_subject[subject] if m.seq>after and consumer not in m.acked]
    def ack(self, message, consumer): message.acked.add(consumer)


class Propagator:
    def __init__(self, ledger, bus, policy=None): self.ledger=ledger; self.bus=bus; self.policy=policy or PolicyEngine()
    def publish(self, delta, receivers):
        self.ledger.publish(delta)
        self.bus.publish(f"federation.knowledge.{delta.priority.lower()}.{delta.domain.lower()}", {"delta_id":delta.delta_id,"hash":delta.content_hash()}, delta.delta_id)
        result={"adopted":0,"held":0,"not_applicable":0}
        for r in receivers:
            p=self.policy.evaluate(delta,r)
            if p.code in {"NOT_APPLICABLE","MATTER_WALL"}: disp=Disposition.NOT_APPLICABLE; result["not_applicable"]+=1
            elif not p.allow: disp=Disposition.HELD; result["held"]+=1
            else: disp=Disposition.ADAPT if delta.domain in r.domains else Disposition.ADOPT; result["adopted"]+=1
            self.ledger.ack(delta.delta_id,r.receiver_id,disp)
        return result


@dataclass(frozen=True)
class MissionIR:
    mission_id:str; objective:str; domain:str; required_capabilities:tuple[str,...]; authority:Authority; effect:Effect; screen_first:bool; idempotency_key:str


def compile_mission(objective, domain, capabilities, authority=Authority.A1, effect=Effect.INTERNAL, screen_first=True):
    seed={"objective":objective,"domain":domain,"capabilities":capabilities,"authority":authority.value,"effect":effect.value}
    mid="MIS-"+digest(seed)[:16].upper(); return MissionIR(mid,objective,domain,tuple(capabilities),authority,effect,screen_first,"IDEM-"+digest(mid)[:20].upper())


WORKFLOW={"CREATED":{"SOURCE_GROUNDED"},"SOURCE_GROUNDED":{"PROPAGATION_PREFLIGHT"},"PROPAGATION_PREFLIGHT":{"SCREEN_REVIEW"},"SCREEN_REVIEW":{"USER_APPROVED"},"USER_APPROVED":{"ARTIFACT_BUILT","COMPLETE"},"ARTIFACT_BUILT":{"ARTIFACT_QA_PASSED"},"ARTIFACT_QA_PASSED":{"EFFECT_APPROVED","COMPLETE"},"EFFECT_APPROVED":{"EFFECT_EXECUTING"},"EFFECT_EXECUTING":{"PROVIDER_READBACK"},"PROVIDER_READBACK":{"INDEPENDENT_VERIFIED"},"INDEPENDENT_VERIFIED":{"VALUE_MEASURED","COMPLETE"},"VALUE_MEASURED":{"COMPLETE"},"COMPLETE":set()}


def advance(ledger, mission_id, new_state):
    current=ledger.restore_state(mission_id)
    if new_state not in WORKFLOW[current]: raise RuntimeError(f"ILLEGAL_TRANSITION:{current}->{new_state}")
    ledger.append_state(mission_id,new_state)
    return new_state


@dataclass(frozen=True)
class AgentSkill: skill_id:str; name:str; description:str
@dataclass(frozen=True)
class AgentCard:
    name:str; url:str; version:str; skills:tuple[AgentSkill,...]; protocol_version:str="1.0"
    def validate(self):
        if self.protocol_version!="1.0": raise ValueError("A2A_1_0_REQUIRED")
        if not self.skills: raise ValueError("SKILLS_REQUIRED")


@dataclass(frozen=True)
class MCPBoundary:
    server_id:str; allowed_tools:tuple[str,...]; denied_tools:tuple[str,...]; authority:Authority; effect:Effect; require_readback:bool=True; no_raw_secret_values:bool=True


@dataclass(frozen=True)
class IdentityEnvelope:
    spiffe_id:str; mission_id:str; authority:Authority; effect:Effect
    def validate(self):
        if not self.spiffe_id.startswith("spiffe://"): raise ValueError("BAD_SPIFFE_ID")


@dataclass(frozen=True)
class ArtifactAttestation:
    artifact_sha256:str; source_commit:str; builder_identity:str; test_receipt:str; signature_bundle_ref:str=""; transparency_log_ref:str=""
    def statement_hash(self): return digest(asdict(self))


class RetryRouter:
    def classify(self, error):
        s=error.lower()
        if "stale" in s and any(x in s for x in ("grid","revision","etag","version")): return ("STALE_PROVIDER_ID",False,"REFRESH_PROVIDER_METADATA_AND_RECOMPILE")
        if "403" in s or "forbidden" in s: return ("PERMISSION",False,"CHANGE_AUTHORITY_OR_ROUTE")
        if "effect_unknown" in s: return ("EFFECT_UNKNOWN",False,"PROBE_PROVIDER_BEFORE_RETRY")
        if any(x in s for x in ("timeout","502","503")): return ("TRANSIENT",True,"ONE_BOUNDED_RETRY")
        return ("UNKNOWN",False,"DIAGNOSE_BEFORE_RETRY")


class ReleaseCourt:
    def check(self, *, source_grounded, screen_review, semantic_diff, metadata_ok, idempotent, consequential, owner_approval, provider_readback, independent_verification):
        failures=[]
        for ok,code in [(source_grounded,"SOURCE_GROUNDING"),(screen_review,"SCREEN_REVIEW"),(semantic_diff,"SEMANTIC_DIFF"),(metadata_ok,"METADATA"),(idempotent,"IDEMPOTENCY")]:
            if not ok: failures.append(code)
        if consequential and not owner_approval: failures.append("OWNER_APPROVAL")
        if consequential and not provider_readback: failures.append("PROVIDER_READBACK")
        if consequential and not independent_verification: failures.append("INDEPENDENT_VERIFICATION")
        return {"passed":not failures,"failures":failures}
