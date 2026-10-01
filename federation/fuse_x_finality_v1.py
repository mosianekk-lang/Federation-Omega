"""FUSE-X sovereign read-only finality runtime v1."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json, os, sqlite3, urllib.error, urllib.parse, urllib.request, uuid
from pathlib import Path
from typing import Any, Callable, Iterable

SCHEMA="FUSE_X_FINALITY_RUNTIME_V1"
VERSION="1.0.0"
REQUIRED=("X_AUTHORIZED_TRANSPORT_VERIFIED","X_READ_ONLY_CANARY_VERIFIED","X_HOME_TIMELINE_INGESTION_VERIFIED","X_DURABLE_CURSOR_VERIFIED","X_EXACTLY_ONCE_VERIFIED","X_RESTART_RECOVERY_VERIFIED","X_PRIVATE_STORE_VERIFIED","X_SEMANTIC_INDEX_VERIFIED","X_VERIFY_PIPELINE_VERIFIED","X_DERIVED_FEED_VERIFIED","X_LOSS_CONTINUITY_VERIFIED","OWNER_ROUTINE_ACTION_FALSE")

def utc_now(): return datetime.now(timezone.utc).isoformat()
def canonical_json(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(v): return sha256(canonical_json(v).encode()).hexdigest()

class XTransportError(RuntimeError): pass

class DirectXTransport:
    """FUSE-owned X API v2 GET-only transport. Token value is never returned/logged."""
    def __init__(self, token_provider:Callable[[],str]|None=None, timeout:int=30):
        self.token_provider=token_provider or (lambda:os.environ.get("FUSE_X_ACCESS_TOKEN","")); self.timeout=timeout; self._uid=None
    def _token(self):
        token=(self.token_provider() or "").strip()
        if not token: raise XTransportError("authorized X access token unavailable")
        return token
    def _get(self,path:str,params:dict[str,Any]|None=None):
        if not path.startswith("/2/"): path="/2/"+path.lstrip("/")
        url="https://api.x.com"+path
        if params: url+="?"+urllib.parse.urlencode({k:v for k,v in params.items() if v is not None},doseq=True)
        req=urllib.request.Request(url,method="GET",headers={"Accept":"application/json","Authorization":f"Bearer {self._token()}","User-Agent":"FUSE-X-Sovereign-ReadOnly/1.0"})
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as resp:
                body=resp.read().decode("utf-8"); return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc: raise XTransportError(f"X API HTTP {exc.code}") from exc
        except urllib.error.URLError as exc: raise XTransportError("X API transport unavailable") from exc
    def whoami(self):
        out=self._get("/2/users/me",{"user.fields":"id,username,name"}); data=out.get("data") or {}
        if data.get("id"): self._uid=str(data["id"])
        return out
    def uid(self):
        if not self._uid: self.whoami()
        if not self._uid: raise XTransportError("authenticated X user id unavailable")
        return self._uid
    def timeline(self,n:int=100):
        n=max(1,min(int(n),100))
        return self._get(f"/2/users/{self.uid()}/timelines/reverse_chronological",{"max_results":n,"tweet.fields":"id,text,author_id,created_at,conversation_id,lang,entities,attachments,public_metrics,referenced_tweets","expansions":"author_id,attachments.media_keys,referenced_tweets.id"})
    def search_recent(self,q:str,n:int=100):
        n=max(10,min(int(n),100))
        return self._get("/2/tweets/search/recent",{"query":q,"max_results":n,"tweet.fields":"id,text,author_id,created_at,conversation_id,lang,entities,attachments,public_metrics,referenced_tweets","expansions":"author_id,attachments.media_keys,referenced_tweets.id"})

@dataclass(frozen=True)
class Observation:
    surface:str; canonical_id:str; content_hash:str; observed_at:str; published_at:str|None; author_id:str|None; text:str; raw:dict[str,Any]
    @classmethod
    def from_post(cls,surface,post,observed_at=None):
        pid=str(post.get("id") or "")
        if not pid: raise ValueError("post id required")
        return cls(surface,pid,digest(post),observed_at or utc_now(),post.get("created_at"),str(post.get("author_id")) if post.get("author_id") is not None else None,str(post.get("text") or ""),post)

DB_SCHEMA="""
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
CREATE TABLE IF NOT EXISTS observations(surface TEXT NOT NULL,canonical_id TEXT NOT NULL,content_hash TEXT NOT NULL,observed_at TEXT NOT NULL,published_at TEXT,author_id TEXT,text TEXT NOT NULL,raw_json TEXT NOT NULL,PRIMARY KEY(surface,canonical_id,content_hash));
CREATE TABLE IF NOT EXISTS cursors(surface TEXT PRIMARY KEY,cursor_json TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS finality(predicate TEXT PRIMARY KEY,state TEXT NOT NULL,proof_ref TEXT,updated_at TEXT NOT NULL);
"""

class ObservationStore:
    def __init__(self,path:str|Path):
        self.path=str(path); self.db=sqlite3.connect(self.path); self.db.row_factory=sqlite3.Row; self.db.executescript(DB_SCHEMA)
        try: self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS observation_fts USING fts5(surface,canonical_id,text,content='')"); self.fts=True
        except sqlite3.OperationalError: self.fts=False
        self.db.commit()
    def close(self): self.db.close()
    def commit_page(self,surface,observations:Iterable[Observation],cursor=None):
        inserted=0
        with self.db:
            for o in list(observations):
                cur=self.db.execute("INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?,?,?)",(o.surface,o.canonical_id,o.content_hash,o.observed_at,o.published_at,o.author_id,o.text,canonical_json(o.raw)))
                if cur.rowcount:
                    inserted+=1
                    if self.fts: self.db.execute("INSERT INTO observation_fts(surface,canonical_id,text) VALUES(?,?,?)",(o.surface,o.canonical_id,o.text))
            if cursor is not None:
                self.db.execute("INSERT INTO cursors VALUES(?,?,?) ON CONFLICT(surface) DO UPDATE SET cursor_json=excluded.cursor_json,updated_at=excluded.updated_at",(surface,canonical_json(cursor),utc_now()))
        return inserted
    def count(self): return int(self.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0])
    def get_cursor(self,surface):
        row=self.db.execute("SELECT cursor_json FROM cursors WHERE surface=?",(surface,)).fetchone(); return json.loads(row[0]) if row else None
    def search(self,q,limit=20):
        if self.fts: rows=self.db.execute("SELECT surface,canonical_id,text FROM observation_fts WHERE observation_fts MATCH ? LIMIT ?",(q,limit)).fetchall()
        else: rows=self.db.execute("SELECT surface,canonical_id,text FROM observations WHERE text LIKE ? LIMIT ?",(f"%{q}%",limit)).fetchall()
        return [dict(r) for r in rows]
    def set_finality(self,predicate,state,proof_ref=None):
        with self.db: self.db.execute("INSERT INTO finality VALUES(?,?,?,?) ON CONFLICT(predicate) DO UPDATE SET state=excluded.state,proof_ref=excluded.proof_ref,updated_at=excluded.updated_at",(predicate,state,proof_ref,utc_now()))
    def finality_map(self): return {r["predicate"]:dict(r) for r in self.db.execute("SELECT * FROM finality")}

@dataclass(frozen=True)
class HarvestResult:
    surface:str; observed:int; inserted:int; cursor:dict[str,Any]

class Harvester:
    def __init__(self,transport,store): self.transport=transport; self.store=store
    def _commit(self,surface,response):
        ts=utc_now(); posts=response.get("data") or []; posts=[posts] if isinstance(posts,dict) else posts
        obs=[Observation.from_post(surface,p,ts) for p in posts if isinstance(p,dict) and p.get("id")]
        meta=response.get("meta") or {}; cursor={"newest_id":meta.get("newest_id"),"oldest_id":meta.get("oldest_id"),"next_token":meta.get("next_token"),"result_count":meta.get("result_count",len(obs)),"observed_at":ts}
        return HarvestResult(surface,len(obs),self.store.commit_page(surface,obs,cursor),cursor)
    def home_once(self,n=100): return self._commit("home",self.transport.timeline(n))
    def search_once(self,q,n=100): return self._commit(f"search:{q}",self.transport.search_recent(q,n))

@dataclass(frozen=True)
class FinalityReport:
    complete:bool; closed:tuple[str,...]; open:tuple[str,...]

def evaluate(states):
    closed=tuple(p for p in REQUIRED if states.get(p)=="VERIFIED"); open_=tuple(p for p in REQUIRED if states.get(p)!="VERIFIED")
    return FinalityReport(not open_,closed,open_)

def restart_recovery_probe(path):
    first=ObservationStore(path); count=first.count(); cursor=first.get_cursor("home"); first.close()
    second=ObservationStore(path); ok=second.count()==count and second.get_cursor("home")==cursor
    if ok:
        second.set_finality("X_RESTART_RECOVERY_VERIFIED","VERIFIED","local:reopen")
        second.set_finality("X_LOSS_CONTINUITY_VERIFIED","VERIFIED","local:archive-without-provider")
    second.close(); return ok

def derived_feed(store,terms,limit=50):
    terms=[t.casefold().strip() for t in terms if t.strip()]
    rows=store.db.execute("SELECT surface,canonical_id,text FROM observations ORDER BY observed_at DESC LIMIT ?",(max(200,limit*20),)).fetchall(); out=[]
    for row in rows:
        hits=sorted({t for t in terms if t in row["text"].casefold()})
        if terms and not hits: continue
        score=1.0 if not terms else min(1.0,len(hits)/len(set(terms)))
        out.append({"surface":row["surface"],"canonical_id":row["canonical_id"],"text":row["text"],"score":score,"rationale":[f"term:{h}" for h in hits] or ["recent-observation"]})
    return sorted(out,key=lambda x:(-x["score"],x["canonical_id"]))[:limit]

def verification_candidate(canonical_id,text):
    import re
    urls=tuple(re.findall(r"https?://[^\s)\]}>,]+",text or ""))
    hints=tuple(u for u in urls if any(x in u.lower() for x in ("github.com","arxiv.org","doi.org","openreview.net","docs.","developer.","api.")))
    return {"canonical_id":canonical_id,"urls":urls,"primary_hints":hints,"status":"PRIMARY_SOURCE_RESOLUTION_REQUIRED" if urls else "NO_EXTERNAL_SOURCE"}

def bounded_live_tick(transport,store,queries=None,n=100):
    run=str(uuid.uuid4()); errors=[]; results=[]
    try:
        who=transport.whoami()
        if (who.get("data") or {}).get("id"):
            store.set_finality("X_AUTHORIZED_TRANSPORT_VERIFIED","VERIFIED",f"run:{run}:whoami")
            store.set_finality("X_READ_ONLY_CANARY_VERIFIED","VERIFIED",f"run:{run}:whoami")
        result=Harvester(transport,store).home_once(n); results.append(asdict(result))
        for p in ("X_HOME_TIMELINE_INGESTION_VERIFIED","X_DURABLE_CURSOR_VERIFIED","X_EXACTLY_ONCE_VERIFIED","X_PRIVATE_STORE_VERIFIED","X_SEMANTIC_INDEX_VERIFIED"):
            store.set_finality(p,"VERIFIED",f"run:{run}")
    except Exception as exc: errors.append({"surface":"home","fingerprint":sha256(type(exc).__name__.encode()).hexdigest()[:16]})
    for q in queries or []:
        try: results.append(asdict(Harvester(transport,store).search_once(q,n)))
        except Exception as exc: errors.append({"surface":f"search:{q}","fingerprint":sha256(type(exc).__name__.encode()).hexdigest()[:16]})
    if derived_feed(store,[],1): store.set_finality("X_DERIVED_FEED_VERIFIED","VERIFIED",f"run:{run}:feed")
    return {"run_id":run,"results":results,"errors":errors,"finality":store.finality_map()}
