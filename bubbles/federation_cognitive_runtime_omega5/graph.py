from __future__ import annotations
import enum, json, sqlite3, threading, time, uuid

class NodeState(str,enum.Enum):
    VERIFIED="VERIFIED"; ACTIVE="ACTIVE"; STALE="STALE"; REVALIDATION_REQUIRED="REVALIDATION_REQUIRED"; UNVERIFIED="UNVERIFIED"

class KnowledgeGraph:
    """Project-scoped proof/knowledge graph. Cross-project edges are blocked by default."""
    def __init__(self,path="bubbles_federation_cognitive_omega5.sqlite3"):
        self.path=path; self._local=threading.local(); self._bootstrap()
    def _conn(self):
        c=getattr(self._local,"conn",None)
        if c is None:
            c=sqlite3.connect(self.path,timeout=30,isolation_level=None,check_same_thread=False); c.row_factory=sqlite3.Row; c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=FULL"); self._local.conn=c
        return c
    def _bootstrap(self):
        c=sqlite3.connect(self.path); c.executescript("""
        PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
        CREATE TABLE IF NOT EXISTS nodes(project_id TEXT NOT NULL,node_id TEXT NOT NULL,node_type TEXT NOT NULL,label TEXT NOT NULL,state TEXT NOT NULL,version TEXT NOT NULL,source_pointer TEXT NOT NULL,updated_at REAL NOT NULL,PRIMARY KEY(project_id,node_id));
        CREATE TABLE IF NOT EXISTS edges(project_id TEXT NOT NULL,src TEXT NOT NULL,relation TEXT NOT NULL,dst TEXT NOT NULL,confidence REAL NOT NULL,updated_at REAL NOT NULL,PRIMARY KEY(project_id,src,relation,dst));
        CREATE TABLE IF NOT EXISTS invalidations(invalidation_id TEXT PRIMARY KEY,project_id TEXT NOT NULL,root_node TEXT NOT NULL,affected_json TEXT NOT NULL,reason TEXT NOT NULL,created_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(project_id,src); CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(project_id,dst);
        """); c.close()
    def upsert_node(self,project_id,node_id,node_type,label,state=NodeState.ACTIVE.value,version="",source_pointer=""):
        with self._conn() as c: c.execute("""INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(project_id,node_id) DO UPDATE SET node_type=excluded.node_type,label=excluded.label,state=excluded.state,version=excluded.version,source_pointer=excluded.source_pointer,updated_at=excluded.updated_at""",(project_id,node_id,node_type,label,str(state),version,source_pointer,time.time()))
    def add_edge(self,project_id,src,relation,dst,confidence=1.0):
        for n in (src,dst):
            if not self.node(project_id,n): raise KeyError(f"Missing project-scoped node: {n}")
        with self._conn() as c: c.execute("INSERT OR REPLACE INTO edges VALUES(?,?,?,?,?,?)",(project_id,src,relation,dst,float(confidence),time.time()))
    def node(self,project_id,node_id):
        r=self._conn().execute("SELECT * FROM nodes WHERE project_id=? AND node_id=?",(project_id,node_id)).fetchone(); return dict(r) if r else None
    def outgoing(self,project_id,node_id): return [dict(r) for r in self._conn().execute("SELECT * FROM edges WHERE project_id=? AND src=?",(project_id,node_id)).fetchall()]
    def incoming(self,project_id,node_id): return [dict(r) for r in self._conn().execute("SELECT * FROM edges WHERE project_id=? AND dst=?",(project_id,node_id)).fetchall()]
    def invalidate_version(self,project_id,source_node,new_version,reason="SOURCE_VERSION_CHANGED"):
        root=self.node(project_id,source_node)
        if not root: raise KeyError(source_node)
        if root["version"]==new_version: return {"changed":False,"affected":[]}
        with self._conn() as c: c.execute("UPDATE nodes SET version=?,state=?,updated_at=? WHERE project_id=? AND node_id=?",(new_version,NodeState.STALE.value,time.time(),project_id,source_node))
        affected=[]; queue=[source_node]; seen={source_node}
        while queue:
            cur=queue.pop(0)
            for e in self.outgoing(project_id,cur):
                if e["relation"] in ("SUPPORTS","DERIVES","REQUIRED_BY","EVIDENCE_FOR"):
                    dst=e["dst"]
                    if dst not in seen:
                        seen.add(dst); affected.append(dst); queue.append(dst)
                        with self._conn() as c: c.execute("UPDATE nodes SET state=?,updated_at=? WHERE project_id=? AND node_id=?",(NodeState.REVALIDATION_REQUIRED.value,time.time(),project_id,dst))
        iid="inv_"+uuid.uuid4().hex
        with self._conn() as c: c.execute("INSERT INTO invalidations VALUES(?,?,?,?,?,?)",(iid,project_id,source_node,json.dumps(affected),reason,time.time()))
        return {"changed":True,"invalidation_id":iid,"affected":affected}
    def dependency_closure(self,project_id,node_id):
        out=[]; q=[node_id]; seen={node_id}
        while q:
            cur=q.pop(0)
            for e in self.outgoing(project_id,cur):
                if e["dst"] not in seen: seen.add(e["dst"]); out.append(e["dst"]); q.append(e["dst"])
        return out
    def close(self):
        c=getattr(self._local,"conn",None)
        if c is not None: c.close(); self._local.conn=None
