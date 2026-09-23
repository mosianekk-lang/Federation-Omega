from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sqlite3,json,hashlib,secrets

GENESIS="0"*64
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def sha(x): return hashlib.sha256(x if isinstance(x,bytes) else canon(x).encode()).hexdigest()
class StateError(Exception): pass
class StaleFence(StateError): pass
class DuplicateEffect(StateError): pass
class InvalidTransition(StateError): pass

class SovereignState:
 def __init__(self,p):
  self.db=sqlite3.connect(str(p),isolation_level=None); self.db.row_factory=sqlite3.Row
  self.db.execute("PRAGMA journal_mode=WAL"); self.db.execute("PRAGMA synchronous=FULL")
  self.db.executescript("""CREATE TABLE IF NOT EXISTS leases(scope TEXT PRIMARY KEY,writer TEXT,token INT,state TEXT);
  CREATE TABLE IF NOT EXISTS facts(id TEXT PRIMARY KEY,state TEXT,value TEXT);
  CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY,state TEXT,terminal TEXT,checkpoint TEXT);
  CREATE TABLE IF NOT EXISTS effects(id TEXT PRIMARY KEY,k TEXT UNIQUE,req TEXT,state TEXT,readback TEXT);
  CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE,payload TEXT,ph TEXT,prev TEXT,eh TEXT UNIQUE);""")
 def close(self): self.db.close()
 def lease(self,s):
  r=self.db.execute("SELECT * FROM leases WHERE scope=?",(s,)).fetchone(); return dict(r) if r else None
 def acquire_lease(self,s,w,t):
  r=self.lease(s)
  if r and r["state"] not in ("RELEASED","ABORTED") and int(t)<=int(r["token"]): raise StaleFence()
  self.db.execute("""INSERT INTO leases VALUES(?,?,?,'ACTIVE') ON CONFLICT(scope) DO UPDATE SET writer=excluded.writer,token=excluded.token,state='ACTIVE'""",(s,w,t))
 def expire(self,s):
  self.db.execute("UPDATE leases SET state='ACTIVE_EXPIRED_NONTERMINAL' WHERE scope=? AND state='ACTIVE'",(s,)); return self.lease(s)
 def release(self,s,w,t):
  r=self.lease(s)
  if not r or r["writer"]!=w or int(r["token"])!=int(t): raise StaleFence()
  self.db.execute("UPDATE leases SET state='RELEASED' WHERE scope=?",(s,))
 def put_fact(self,i,state,value=None):
  if state not in ("KNOWN","UNKNOWN","DISPUTED","SUPERSEDED","REVOKED"): raise ValueError(state)
  self.db.execute("INSERT OR REPLACE INTO facts VALUES(?,?,?)",(i,state,None if value is None else canon(value)))
 def fact(self,i):
  r=self.db.execute("SELECT * FROM facts WHERE id=?",(i,)).fetchone()
  if not r:return None
  d=dict(r); d["value"]=None if d["value"] is None else json.loads(d["value"]); return d
 def mission(self,i):
  r=self.db.execute("SELECT * FROM missions WHERE id=?",(i,)).fetchone()
  if not r:return None
  d=dict(r); d["checkpoint"]=json.loads(d.pop("checkpoint")); return d
 def upsert_mission(self,i,state,checkpoint):
  r=self.mission(i)
  if r and r["terminal"]: raise InvalidTransition()
  self.db.execute("""INSERT INTO missions VALUES(?,?,NULL,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,checkpoint=excluded.checkpoint""",(i,state,canon(checkpoint)))
 def terminalize(self,i,state):
  if state not in ("COMPLETE","ABORTED","CANCELLED","SUPERSEDED"): raise ValueError(state)
  self.db.execute("UPDATE missions SET state=?,terminal=? WHERE id=?",(state,state,i))
 def prepare_effect(self,i,k,request):
  rh=sha(request); r=self.db.execute("SELECT * FROM effects WHERE k=?",(k,)).fetchone()
  if r:
   if r["req"]!=rh: raise DuplicateEffect()
   return dict(r)
  self.db.execute("INSERT INTO effects VALUES(?,?,?,'PREPARED',NULL)",(i,k,rh)); return self.effect(i)
 def effect(self,i):
  r=self.db.execute("SELECT * FROM effects WHERE id=?",(i,)).fetchone(); return dict(r) if r else None
 def unknown_effect(self,i): self.db.execute("UPDATE effects SET state='UNKNOWN' WHERE id=?",(i,)); return self.effect(i)
 def readback_effect(self,i,match):
  self.db.execute("UPDATE effects SET state=?,readback=? WHERE id=?",("VERIFIED" if match else "UNKNOWN",canon({"match":match}),i)); return self.effect(i)
 def append_event(self,i,payload):
  old=self.db.execute("SELECT eh FROM events WHERE id=?",(i,)).fetchone()
  if old:return old["eh"]
  tail=self.db.execute("SELECT eh FROM events ORDER BY seq DESC LIMIT 1").fetchone(); prev=tail["eh"] if tail else GENESIS; ph=sha(payload); eh=sha({"id":i,"ph":ph,"prev":prev})
  self.db.execute("INSERT INTO events(id,payload,ph,prev,eh) VALUES(?,?,?,?,?)",(i,canon(payload),ph,prev,eh)); return eh
 def verify_chain(self):
  prev=GENESIS
  for r in self.db.execute("SELECT * FROM events ORDER BY seq"):
   if r["prev"]!=prev or sha(json.loads(r["payload"]))!=r["ph"] or sha({"id":r["id"],"ph":r["ph"],"prev":r["prev"]})!=r["eh"]: return False
   prev=r["eh"]
  return True

class ObjectStore:
 def __init__(self,root): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
 def put(self,b):
  h=sha(b); p=self.root/h
  if not p.exists(): p.write_bytes(b)
  return "sha256:"+h
 def get(self,oid):
  h=oid.split(":",1)[1]; p=self.root/h
  if not p.exists(): raise KeyError(oid)
  b=p.read_bytes()
  if sha(b)!=h: raise IOError("corrupt")
  return b
 def verify(self,oid):
  try:self.get(oid); return True
  except Exception:return False

@dataclass(frozen=True)
class Event: id:str; key:str; payload:dict
class EventFabric:
 def __init__(self,p):
  self.db=sqlite3.connect(str(p),isolation_level=None); self.db.row_factory=sqlite3.Row; self.db.execute("PRAGMA journal_mode=WAL")
  self.db.executescript("CREATE TABLE IF NOT EXISTS q(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE,k TEXT UNIQUE,p TEXT);CREATE TABLE IF NOT EXISTS o(c TEXT PRIMARY KEY,n INT);")
 def close(self): self.db.close()
 def publish(self,e):
  r=self.db.execute("SELECT seq FROM q WHERE k=?",(e.key,)).fetchone()
  if r:return r["seq"]
  return self.db.execute("INSERT INTO q(id,k,p) VALUES(?,?,?)",(e.id,e.key,canon(e.payload))).lastrowid
 def poll(self,c):
  r=self.db.execute("SELECT n FROM o WHERE c=?",(c,)).fetchone(); n=r["n"] if r else 0
  return [dict(x) for x in self.db.execute("SELECT * FROM q WHERE seq>? ORDER BY seq",(n,))]
 def ack(self,c,row): self.db.execute("INSERT INTO o VALUES(?,?) ON CONFLICT(c) DO UPDATE SET n=MAX(n,excluded.n)",(c,row["seq"]))

@dataclass(frozen=True)
class Identity: id:str; key_ref:str
class IdentityRegistry:
 def __init__(self): self.ids={}
 def add(self,x):
  if "PRIVATE" in x.key_ref.upper() or "SECRET=" in x.key_ref.upper(): raise ValueError("raw secret")
  self.ids[x.id]=x
 def revoke(self,i): self.ids.pop(i,None)
class TokenIssuer:
 def __init__(self,r): self.r=r
 def issue(self,sub,aud,now,ttl=300):
  if sub not in self.r.ids or ttl<=0 or ttl>3600: raise PermissionError()
  t={"sub":sub,"aud":aud,"iat":now,"exp":now+ttl,"nonce":secrets.token_hex(8)}; t["proof"]=sha(t); return t
 def valid(self,t,aud,now): return t["sub"] in self.r.ids and t["aud"]==aud and t["iat"]<=now<t["exp"]

class SessionGateway:
 def __init__(self,main,writer,fence): self.main,self.writer,self.fence=main,writer,int(fence)
 def admit(self,main,writer,fence): return main==self.main and writer==self.writer and int(fence)==self.fence

@dataclass(frozen=True)
class Model: id:str; local:bool; caps:tuple[str,...]; current:bool
class ModelMarket:
 def __init__(self): self.m=[]
 def add(self,x): self.m.append(x)
 def choose(self,caps):
  req=set(caps); xs=[x for x in self.m if x.current and req<=set(x.caps)]
  xs.sort(key=lambda x:(not x.local,x.id)); return xs[0] if xs else None

@dataclass(frozen=True)
class Creative: id:str; local:bool; mods:tuple[str,...]; editable:bool; current:bool
class CreativeMarket:
 def __init__(self): self.m=[]
 def add(self,x): self.m.append(x)
 def choose(self,mods,editable=True):
  req=set(mods); xs=[x for x in self.m if x.current and req<=set(x.mods) and (not editable or x.editable)]
  xs.sort(key=lambda x:(not x.local,x.id)); return xs[0] if xs else None

MAIN="55fd191796327e0b4ab131c0faf2e09a8ad7b575"; WRITER="F320"; FENCE=320
def cold_boot_receipt(root):
 root=Path(root); root.mkdir(parents=True,exist_ok=True)
 s=SovereignState(root/"state.db"); scope="repo:main"; s.acquire_lease(scope,WRITER,FENCE); s.expire(scope); s.put_fact("FULL_KIM_DATAVERSE_BOUND","UNKNOWN"); s.upsert_mission("GENESIS","RUNNING",{"checkpoint":"F320"})
 o=ObjectStore(root/"objects"); oid=o.put(b"genesis-proof")
 e=EventFabric(root/"events.db"); seq=e.publish(Event("evt","k",{"object":oid})); row=e.poll("worker")[0]; e.ack("worker",row)
 ids=IdentityRegistry(); ids.add(Identity("worker","keyref:worker")); tok=TokenIssuer(ids).issue("worker","local",1000,300)
 g=SessionGateway(MAIN,WRITER,FENCE)
 mm=ModelMarket(); mm.add(Model("local-reasoner",True,("reason","code"),True))
 cm=CreativeMarket(); cm.add(Creative("local-renderer",True,("image",),True,True))
 r={"state_chain_valid":s.verify_chain(),"lease_state":s.lease(scope)["state"],"unknown_preserved":s.fact("FULL_KIM_DATAVERSE_BOUND")["state"],"object_verified":o.verify(oid),"event_seq":seq,"event_drained":e.poll("worker")==[],"identity_valid":TokenIssuer(ids).valid(tok,"local",1100),"session_admitted":g.admit(MAIN,WRITER,FENCE),"local_model":mm.choose(("reason",)).id,"local_creative":cm.choose(("image",)).id,"external_provider_required":False}
 r["digest"]=sha(r); e.close(); s.close(); return r
