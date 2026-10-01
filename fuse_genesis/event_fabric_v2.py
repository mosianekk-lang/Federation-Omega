from __future__ import annotations
import sqlite3,json,hashlib
from dataclasses import dataclass
from pathlib import Path

def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"))
def sha(x): return hashlib.sha256(canon(x).encode()).hexdigest()

class EventError(Exception): pass
class StaleFence(EventError): pass
class IdempotencyCollision(EventError): pass
class ProducerOrderError(EventError): pass

@dataclass(frozen=True)
class EventEnvelope:
    event_id:str
    topic:str
    idempotency_key:str
    mission_id:str
    producer_id:str
    producer_seq:int
    fence_token:int
    payload:dict
    recorded_at:str

class EventFabric:
    def __init__(self,path,max_attempts=3):
        self.path=str(path); self.max_attempts=max_attempts
        self.db=sqlite3.connect(self.path,isolation_level=None,timeout=5)
        self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL"); self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS stream_fences(topic TEXT PRIMARY KEY, token INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS producer_state(producer_id TEXT PRIMARY KEY,last_seq INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS events(
          seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,topic TEXT NOT NULL,
          idempotency_key TEXT UNIQUE NOT NULL,mission_id TEXT NOT NULL,producer_id TEXT NOT NULL,
          producer_seq INTEGER NOT NULL,fence_token INTEGER NOT NULL,payload_json TEXT NOT NULL,
          payload_sha256 TEXT NOT NULL,recorded_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS consumers(
          consumer TEXT PRIMARY KEY,last_acked_seq INTEGER NOT NULL DEFAULT 0,paused INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS attempts(
          consumer TEXT NOT NULL,event_id TEXT NOT NULL,count INTEGER NOT NULL DEFAULT 0,last_error TEXT,
          PRIMARY KEY(consumer,event_id));
        CREATE TABLE IF NOT EXISTS acks(
          consumer TEXT NOT NULL,event_id TEXT NOT NULL,seq INTEGER NOT NULL,ack_sha256 TEXT NOT NULL,
          PRIMARY KEY(consumer,event_id));
        CREATE TABLE IF NOT EXISTS dlq(
          consumer TEXT NOT NULL,event_id TEXT NOT NULL,seq INTEGER NOT NULL,error TEXT NOT NULL,
          payload_sha256 TEXT NOT NULL,PRIMARY KEY(consumer,event_id));
        """)

    def close(self): self.db.close()

    def set_fence(self,topic,token):
        cur=self.db.execute("select token from stream_fences where topic=?",(topic,)).fetchone()
        if cur and token<cur["token"]: raise StaleFence("fence regression")
        self.db.execute("""insert into stream_fences(topic,token) values(?,?)
                           on conflict(topic) do update set token=max(token,excluded.token)""",(topic,token))
        return token

    def publish(self,e:EventEnvelope):
        current=self.db.execute("select token from stream_fences where topic=?",(e.topic,)).fetchone()
        if current and e.fence_token<current["token"]: raise StaleFence("stale publish fence")
        idem=self.db.execute("select * from events where idempotency_key=?",(e.idempotency_key,)).fetchone()
        ph=sha(e.payload)
        if idem:
            if idem["payload_sha256"]!=ph or idem["topic"]!=e.topic or idem["mission_id"]!=e.mission_id:
                raise IdempotencyCollision("same key different semantic event")
            return idem["seq"]
        ps=self.db.execute("select last_seq from producer_state where producer_id=?",(e.producer_id,)).fetchone()
        if ps and e.producer_seq<=ps["last_seq"]: raise ProducerOrderError("producer sequence not monotonic")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            cur=self.db.execute("""insert into events(event_id,topic,idempotency_key,mission_id,producer_id,producer_seq,
                 fence_token,payload_json,payload_sha256,recorded_at) values(?,?,?,?,?,?,?,?,?,?)""",
                 (e.event_id,e.topic,e.idempotency_key,e.mission_id,e.producer_id,e.producer_seq,e.fence_token,
                  canon(e.payload),ph,e.recorded_at))
            self.db.execute("""insert into producer_state(producer_id,last_seq) values(?,?)
               on conflict(producer_id) do update set last_seq=excluded.last_seq""",(e.producer_id,e.producer_seq))
            if not current:
                self.db.execute("insert or ignore into stream_fences(topic,token) values(?,?)",(e.topic,e.fence_token))
            self.db.execute("COMMIT")
            return cur.lastrowid
        except Exception:
            self.db.execute("ROLLBACK"); raise

    def ensure_consumer(self,c):
        self.db.execute("insert or ignore into consumers(consumer) values(?)",(c,))
    def pause(self,c): self.ensure_consumer(c); self.db.execute("update consumers set paused=1 where consumer=?",(c,))
    def resume(self,c): self.ensure_consumer(c); self.db.execute("update consumers set paused=0 where consumer=?",(c,))
    def offset(self,c):
        self.ensure_consumer(c); return self.db.execute("select last_acked_seq from consumers where consumer=?",(c,)).fetchone()["last_acked_seq"]

    def poll(self,c,limit=10,topic=None):
        self.ensure_consumer(c)
        st=self.db.execute("select * from consumers where consumer=?",(c,)).fetchone()
        if st["paused"]: return []
        q="""select e.* from events e
             left join acks a on a.consumer=? and a.event_id=e.event_id
             left join dlq d on d.consumer=? and d.event_id=e.event_id
             where e.seq>? and a.event_id is null and d.event_id is null"""
        params=[c,c,st["last_acked_seq"]]
        if topic is not None:
            q+=" and e.topic=?"; params.append(topic)
        q+=" order by e.seq limit ?"; params.append(limit)
        return [dict(r) for r in self.db.execute(q,params)]

    def fail(self,c,row,error):
        self.ensure_consumer(c)
        self.db.execute("""insert into attempts(consumer,event_id,count,last_error) values(?,?,1,?)
          on conflict(consumer,event_id) do update set count=count+1,last_error=excluded.last_error""",(c,row["event_id"],error))
        a=self.db.execute("select * from attempts where consumer=? and event_id=?",(c,row["event_id"])).fetchone()
        if a["count"]>=self.max_attempts:
            self.db.execute("insert or ignore into dlq values(?,?,?,?,?)",
                            (c,row["event_id"],row["seq"],error,row["payload_sha256"]))
            self._advance_offset(c,row["seq"])
            return "DLQ"
        return "RETRY"

    def _advance_offset(self,c,seq):
        self.ensure_consumer(c)
        cur=self.offset(c)
        if seq<cur: raise EventError("offset regression")
        self.db.execute("update consumers set last_acked_seq=max(last_acked_seq,?) where consumer=?",(seq,c))

    def ack(self,c,row):
        self.ensure_consumer(c)
        material={"consumer":c,"event_id":row["event_id"],"seq":row["seq"],"payload_sha256":row["payload_sha256"]}
        h=sha(material)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("insert or ignore into acks values(?,?,?,?)",(c,row["event_id"],row["seq"],h))
            self._advance_offset(c,row["seq"])
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK"); raise
        return h

    def replay(self,start_seq=1,end_seq=None,topic=None):
        q="select * from events where seq>=?"; params=[start_seq]
        if end_seq is not None: q+=" and seq<=?"; params.append(end_seq)
        if topic is not None: q+=" and topic=?"; params.append(topic)
        q+=" order by seq"
        return [dict(r) for r in self.db.execute(q,params)]

    def dlq_rows(self,c=None):
        if c is None: return [dict(r) for r in self.db.execute("select * from dlq order by seq")]
        return [dict(r) for r in self.db.execute("select * from dlq where consumer=? order by seq",(c,))]

    def state_digest(self):
        payload={}
        for t in ("stream_fences","producer_state","events","consumers","attempts","acks","dlq"):
            payload[t]=[dict(r) for r in self.db.execute(f"select * from {t} order by rowid")]
        return sha(payload)
