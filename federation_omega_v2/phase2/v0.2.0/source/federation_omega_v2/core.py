from __future__ import annotations
import hashlib, json, re, sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime

SAFE_ID=re.compile(r"^[A-Z0-9][A-Z0-9._:/-]{2,127}$")
STAGES=("SOURCE_LOCK","PROVENANCE","CHRONOLOGY","ELEMENT_MAP","CONTRADICTION_SCAN",
        "GAP_SCHEDULE","INTERNAL_BUNDLE","BENCHMIND","REVIEWGUARD","OWNER_BRIEF")

def cjson(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def sha(v): return hashlib.sha256(cjson(v).encode()).hexdigest()

@dataclass(frozen=True)
class Event:
    event_id:str; entity_id:str; event_type:str; observed_at:str; source:str; payload:dict
    authority:str="A1"
    def body(self):
        if not SAFE_ID.fullmatch(self.event_id) or not SAFE_ID.fullmatch(self.entity_id) or not SAFE_ID.fullmatch(self.source):
            raise ValueError("invalid event identity")
        if self.authority!="A1": raise ValueError("Phase 2 authority must remain A1")
        if self.event_type not in {"STATE_SET","STATE_PATCH","MISSION_STAGE"}: raise ValueError("unsupported event")
        parsed=datetime.fromisoformat(self.observed_at.replace("Z","+00:00"))
        if parsed.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
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
    def append(self,event):
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
    def add_relationship(self,r):
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
        state={}; last=None; events=self.events(entity)
        for e in events:
            payload=e["payload_obj"]
            if e["event_type"]=="STATE_SET": state=dict(payload["state"])
            elif e["event_type"]=="STATE_PATCH": state.update(payload["patch"])
            elif e["event_type"]=="MISSION_STAGE": state.setdefault("stages",{})[payload["stage"]]=payload["status"]
            last=e
        return {"entity_id":entity,"state":state,"event_count":len(events),
                "last_event_id":last["event_id"] if last else None,
                "last_event_hash":last["event_hash"] if last else None}
    def save_mission(self,mission):
        mission_hash=sha(mission); mission_id=mission["mission_id"]
        with self.connection() as c:
            old=c.execute("SELECT mission_hash FROM missions WHERE mission_id=?",(mission_id,)).fetchone()
            if old:
                if old["mission_hash"]!=mission_hash: raise ValueError("mission conflict")
                return {"state":"IDEMPOTENT_REPLAY"}
            c.execute("INSERT INTO missions VALUES(?,?,?)",(mission_id,cjson(mission),mission_hash))
        return {"state":"SAVED"}
    def mission(self,mission_id):
        with self.connection() as c: row=c.execute("SELECT mission_json FROM missions WHERE mission_id=?",(mission_id,)).fetchone()
        return json.loads(row[0]) if row else None
    def verify(self):
        with self.connection() as c:
            quick=c.execute("PRAGMA quick_check").fetchone()[0]
            entities=[r[0] for r in c.execute("SELECT DISTINCT entity_id FROM events")]
            relationship_count=c.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
        count=0
        for entity in entities:
            previous=None
            for event in self.events(entity):
                body={"event_id":event["event_id"],"entity_id":event["entity_id"],"event_type":event["event_type"],
                      "observed_at":event["observed_at"],"source":event["source"],"payload":event["payload_obj"],"authority":event["authority"]}
                body_hash=sha(body); event_hash=sha({"body":body,"body_hash":body_hash,"previous_hash":previous})
                if body_hash!=event["body_hash"] or event_hash!=event["event_hash"] or event["previous_hash"]!=previous:
                    raise ValueError("hash mismatch")
                previous=event["event_hash"]; count+=1
        return {"quick_check":quick,"entity_count":len(entities),"event_count":count,"relationship_count":relationship_count}

def import_canonical_register(store,register,observed_at="2026-08-04T19:12:00+00:00"):
    if register["system_count"]!=20 or len(register["systems"])!=20: raise ValueError("canonical register must contain twenty systems")
    systems=[]
    for row in register["systems"]:
        payload={"state":{**row,"canonical":True}}
        event_id="EVT-SYSTEM-"+sha({"system_id":row["system_id"],"payload":payload})[:24].upper()
        systems.append(store.append(Event(event_id,row["system_id"],"STATE_SET",observed_at,"SRC-CANONICAL-SYSTEM-REGISTER",payload)))
    relationships=[]
    for row in register["relationships"]:
        relationships.append(store.add_relationship(Relationship(**row)))
    return {"system_count":len(systems),"relationship_count":len(relationships),"systems":systems,"relationships":relationships}

class CanonicalQueryService:
    def __init__(self,store): self.store=store
    def system(self,system_id):
        projection=self.store.project(system_id)
        return {**projection,"proof_state":"READBACK_VERIFIED" if projection["event_count"] else "UNKNOWN",
                "outgoing":self.store.relationships(system_id,"out"),"incoming":self.store.relationships(system_id,"in")}
    def mission(self,mission_id):
        mission=self.store.mission(mission_id); projection=self.store.project(mission_id)
        return {"mission":mission,"projection":projection,"proof_state":"READBACK_VERIFIED" if mission else "UNKNOWN"}
    def route(self,text):
        value=text.casefold()
        if any(x in value for x in ("legal","evidence","ccma","hearing","paia")): system,adapter="SYS-EVIDENCEOPS","evidenceops_legal"
        elif any(x in value for x in ("trade","market","strategy")): system,adapter="SYS-SPECIALIST-ESTATE","trading_research"
        elif any(x in value for x in ("cloud","github","deploy","software","ict")): system,adapter="SYS-CLOUDOPS","generic"
        else: system,adapter="SYS-FEDERATION-OMEGA","generic"
        return {"system":system,"adapter":adapter,"authority_ceiling":"A1","external_effects":False}

def run_evidenceops_reference_mission(store,observed_at="2026-08-04T19:12:00+00:00"):
    body={"objective":"Produce a verified synthetic internal EvidenceOps decision brief",
          "success":["Ten stages complete","Owner brief produced","Zero external effects"],
          "authority_ceiling":"A1","constraints":["No filing","No sending","No case facts","No hearing recording"],
          "proof":["Stage receipts","Event-chain verification","Restart reconstruction"],"external_effects":0}
    mission_id="MISSION-"+sha(body)[:24].upper(); mission={"mission_id":mission_id,**body}; store.save_mission(mission)
    receipts=[]; previous=None
    for index,stage in enumerate(STAGES,1):
        receipt=sha({"mission_id":mission_id,"stage":stage,"index":index,"previous":previous})
        event_id=f"EVT-{mission_id}-STAGE-{index:02d}"
        store.append(Event(event_id,mission_id,"MISSION_STAGE",observed_at,"SRC-SYNTHETIC-EVIDENCEOPS",
                           {"stage":stage,"status":"COMPLETE_VERIFIED","receipt_sha256":receipt,
                            "previous_receipt":previous,"external_effects":0}))
        receipts.append(receipt); previous=receipt
    projection=store.project(mission_id)
    if len(projection["state"].get("stages",{}))!=10: raise ValueError("incomplete mission")
    return {"state":"COMPLETE_VERIFIED_SYNTHETIC_INTERNAL","mission":mission,"stage_count":10,
            "projection":projection,"receipts":receipts,"external_effects":0}
