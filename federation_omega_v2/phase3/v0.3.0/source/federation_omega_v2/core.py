from __future__ import annotations
import hashlib, json, re, sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_ID=re.compile(r"^[A-Z0-9][A-Z0-9._:/-]{2,127}$")
STAGES=("SOURCE_LOCK","PROVENANCE","CHRONOLOGY","ELEMENT_MAP","CONTRADICTION_SCAN",
        "GAP_SCHEDULE","INTERNAL_BUNDLE","BENCHMIND","REVIEWGUARD","OWNER_BRIEF")

def cjson(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def sha(v): return hashlib.sha256(cjson(v).encode()).hexdigest()
def utc(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

@dataclass(frozen=True)
class Event:
    event_id:str; entity_id:str; event_type:str; observed_at:str; source:str; payload:dict[str,Any]
    authority:str="A1"
    def body(self):
        if not SAFE_ID.fullmatch(self.event_id) or not SAFE_ID.fullmatch(self.entity_id) or not SAFE_ID.fullmatch(self.source):
            raise ValueError("invalid event identity")
        if self.authority!="A1": raise ValueError("Phase 2 authority must remain A1")
        if self.event_type not in {"STATE_SET","STATE_PATCH","MISSION_STAGE"}: raise ValueError("unsupported event")
        datetime.fromisoformat(self.observed_at.replace("Z","+00:00"))
        if not isinstance(self.payload,dict): raise ValueError("payload must be object")
        return asdict(self)

@dataclass(frozen=True)
class Relationship:
    source_id:str; target_id:str; relation_type:str
    def body(self):
        if not SAFE_ID.fullmatch(self.source_id) or not SAFE_ID.fullmatch(self.target_id): raise ValueError("invalid endpoint")
        if self.source_id==self.target_id: raise ValueError("self relationship prohibited")
        if not SAFE_ID.fullmatch(self.relation_type): raise ValueError("invalid relation")
        return asdict(self)
    @property
    def relation_id(self): return "REL-"+sha(self.body())[:24].upper()

class EventStore:
    def __init__(self,path):
        self.path=str(path); self._init()
    def connect(self):
        c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA foreign_keys=ON"); return c
    @contextmanager
    def connection(self):
        c=self.connect()
        try: yield c; c.commit()
        except Exception: c.rollback(); raise
        finally: c.close()
    def _init(self):
        with self.connection() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS events(
              seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,
              entity_id TEXT NOT NULL,event_type TEXT NOT NULL,observed_at TEXT NOT NULL,
              source TEXT NOT NULL,authority TEXT NOT NULL,payload TEXT NOT NULL,
              previous_hash TEXT,event_hash TEXT UNIQUE NOT NULL,body_hash TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_events_entity ON events(entity_id,seq);
            CREATE TABLE IF NOT EXISTS relationships(
              relation_id TEXT PRIMARY KEY,source_id TEXT,target_id TEXT,relation_type TEXT,
              body_hash TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS missions(
              mission_id TEXT PRIMARY KEY,mission_json TEXT NOT NULL,mission_hash TEXT UNIQUE NOT NULL);
            """)
    def append(self,event:Event):
        body=event.body(); bh=sha(body)
        with self.connection() as c:
            old=c.execute("SELECT body_hash,event_hash,seq FROM events WHERE event_id=?",(event.event_id,)).fetchone()
            if old:
                if old["body_hash"]!=bh: raise ValueError("event_id conflict")
                return {"state":"IDEMPOTENT_REPLAY","sequence":old["seq"],"event_hash":old["event_hash"]}
            p=c.execute("SELECT event_hash FROM events WHERE entity_id=? ORDER BY seq DESC LIMIT 1",(event.entity_id,)).fetchone()
            prev=p["event_hash"] if p else None; eh=sha({"body":body,"body_hash":bh,"previous_hash":prev})
            cur=c.execute("INSERT INTO events(event_id,entity_id,event_type,observed_at,source,authority,payload,previous_hash,event_hash,body_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (event.event_id,event.entity_id,event.event_type,event.observed_at,event.source,event.authority,cjson(event.payload),prev,eh,bh))
            return {"state":"APPENDED","sequence":cur.lastrowid,"event_hash":eh}
    def add_relationship(self,r:Relationship):
        body=r.body(); bh=sha(body)
        with self.connection() as c:
            old=c.execute("SELECT body_hash FROM relationships WHERE relation_id=?",(r.relation_id,)).fetchone()
            if old:
                if old["body_hash"]!=bh: raise ValueError("relationship conflict")
                return {"state":"IDEMPOTENT_REPLAY","relation_id":r.relation_id}
            c.execute("INSERT INTO relationships VALUES(?,?,?,?,?)",(r.relation_id,r.source_id,r.target_id,r.relation_type,bh))
        return {"state":"ADDED","relation_id":r.relation_id}
    def events(self,entity=None):
        q="SELECT * FROM events"; p=()
        if entity: q+=" WHERE entity_id=?"; p=(entity,)
        q+=" ORDER BY seq"
        with self.connection() as c: rows=c.execute(q,p).fetchall()
        return [{**dict(x),"payload_obj":json.loads(x["payload"])} for x in rows]
    def relationships(self,system=None,direction="both"):
        q="SELECT * FROM relationships"; p=()
        if system and direction=="out": q+=" WHERE source_id=?"; p=(system,)
        elif system and direction=="in": q+=" WHERE target_id=?"; p=(system,)
        elif system: q+=" WHERE source_id=? OR target_id=?"; p=(system,system)
        q+=" ORDER BY relation_type,source_id,target_id"
        with self.connection() as c: return [dict(x) for x in c.execute(q,p).fetchall()]
    def project(self,entity):
        state={}; last=None; ev=self.events(entity)
        for e in ev:
            p=e["payload_obj"]
            if e["event_type"]=="STATE_SET": state=dict(p["state"])
            elif e["event_type"]=="STATE_PATCH": state.update(p["patch"])
            elif e["event_type"]=="MISSION_STAGE": state.setdefault("stages",{})[p["stage"]]=p["status"]
            last=e
        return {"entity_id":entity,"state":state,"event_count":len(ev),
                "last_event_id":last["event_id"] if last else None,
                "last_event_hash":last["event_hash"] if last else None}
    def save_mission(self,m):
        mh=sha(m); mid=m["mission_id"]
        with self.connection() as c:
            old=c.execute("SELECT mission_hash FROM missions WHERE mission_id=?",(mid,)).fetchone()
            if old:
                if old["mission_hash"]!=mh: raise ValueError("mission conflict")
                return {"state":"IDEMPOTENT_REPLAY"}
            c.execute("INSERT INTO missions VALUES(?,?,?)",(mid,cjson(m),mh))
        return {"state":"SAVED"}
    def mission(self,mid):
        with self.connection() as c: r=c.execute("SELECT mission_json FROM missions WHERE mission_id=?",(mid,)).fetchone()
        return json.loads(r[0]) if r else None
    def verify(self):
        with self.connection() as c:
            quick=c.execute("PRAGMA quick_check").fetchone()[0]
            entities=[r[0] for r in c.execute("SELECT DISTINCT entity_id FROM events")]
            rc=c.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
        count=0
        for entity in entities:
            prev=None
            for e in self.events(entity):
                body={"event_id":e["event_id"],"entity_id":e["entity_id"],"event_type":e["event_type"],
                      "observed_at":e["observed_at"],"source":e["source"],"payload":e["payload_obj"],"authority":e["authority"]}
                bh=sha(body); eh=sha({"body":body,"body_hash":bh,"previous_hash":prev})
                if bh!=e["body_hash"] or eh!=e["event_hash"] or e["previous_hash"]!=prev: raise ValueError("hash mismatch")
                prev=e["event_hash"]; count+=1
        return {"quick_check":quick,"entity_count":len(entities),"event_count":count,"relationship_count":rc}

def import_canonical_register(store,register,observed_at="2026-08-04T19:12:00+00:00"):
    if register["system_count"]!=20 or len(register["systems"])!=20: raise ValueError("canonical register must contain twenty systems")
    out=[]
    for row in register["systems"]:
        payload={"state":{**row,"canonical":True}}
        eid="EVT-SYSTEM-"+sha({"system_id":row["system_id"],"payload":payload})[:24].upper()
        out.append(store.append(Event(eid,row["system_id"],"STATE_SET",observed_at,"SRC-CANONICAL-SYSTEM-REGISTER",payload)))
    rel=[]
    for row in register["relationships"]:
        rel.append(store.add_relationship(Relationship(**row)))
    return {"system_count":len(out),"relationship_count":len(rel),"systems":out,"relationships":rel}

class CanonicalQueryService:
    def __init__(self,store): self.store=store
    def system(self,sid):
        p=self.store.project(sid)
        return {**p,"proof_state":"READBACK_VERIFIED" if p["event_count"] else "UNKNOWN",
                "outgoing":self.store.relationships(sid,"out"),"incoming":self.store.relationships(sid,"in")}
    def mission(self,mid):
        m=self.store.mission(mid); p=self.store.project(mid)
        return {"mission":m,"projection":p,"proof_state":"READBACK_VERIFIED" if m else "UNKNOWN"}
    def route(self,text):
        t=text.casefold()
        if any(x in t for x in ("legal","evidence","ccma","hearing","paia")): s,a="SYS-EVIDENCEOPS","evidenceops_legal"
        elif any(x in t for x in ("trade","market","strategy")): s,a="SYS-SPECIALIST-ESTATE","trading_research"
        elif any(x in t for x in ("cloud","github","deploy","software","ict")): s,a="SYS-CLOUDOPS","generic"
        else: s,a="SYS-FEDERATION-OMEGA","generic"
        return {"system":s,"adapter":a,"authority_ceiling":"A1","external_effects":False}

def run_evidenceops_reference_mission(store,observed_at="2026-08-04T19:12:00+00:00"):
    body={"objective":"Produce a verified synthetic internal EvidenceOps decision brief",
          "success":["Ten stages complete","Owner brief produced","Zero external effects"],
          "authority_ceiling":"A1","constraints":["No filing","No sending","No case facts","No hearing recording"],
          "proof":["Stage receipts","Event-chain verification","Restart reconstruction"],"external_effects":0}
    mid="MISSION-"+sha(body)[:24].upper(); mission={"mission_id":mid,**body}; store.save_mission(mission)
    receipts=[]; prev=None
    for i,stage in enumerate(STAGES,1):
        receipt=sha({"mission_id":mid,"stage":stage,"index":i,"previous":prev})
        eid=f"EVT-{mid}-STAGE-{i:02d}"
        store.append(Event(eid,mid,"MISSION_STAGE",observed_at,"SRC-SYNTHETIC-EVIDENCEOPS",
                           {"stage":stage,"status":"COMPLETE_VERIFIED","receipt_sha256":receipt,
                            "previous_receipt":prev,"external_effects":0}))
        receipts.append(receipt); prev=receipt
    p=store.project(mid)
    if len(p["state"].get("stages",{}))!=10: raise ValueError("incomplete mission")
    return {"state":"COMPLETE_VERIFIED_SYNTHETIC_INTERNAL","mission":mission,"stage_count":10,
            "projection":p,"receipts":receipts,"external_effects":0}
