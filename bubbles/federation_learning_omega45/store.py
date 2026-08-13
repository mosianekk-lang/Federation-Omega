from __future__ import annotations
import json, sqlite3, threading, time, uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional

def _now() -> float: return time.time()

@dataclass(frozen=True)
class Observation:
    project_id: str
    mission_type: str
    metric: str
    value: float
    connector: str = ""
    outcome: str = ""
    ts: float = 0.0

class LearningStore:
    """Sanitized numeric operational learning store. No raw chat/email/document text."""
    ALLOWED_PREFIXES = ("latency.", "retrieval.", "cache.", "connector.", "context.", "shim.", "stall.", "repair.", "proof.", "mission.", "reuse.")
    def __init__(self, path: str = "bubbles_federation_learning_omega45.sqlite3"):
        self.path = path; self._local = threading.local(); self._bootstrap()
    def _conn(self):
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
            c.row_factory = sqlite3.Row; c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=FULL"); self._local.conn = c
        return c
    def _bootstrap(self):
        c = sqlite3.connect(self.path)
        c.executescript("""
        PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
        CREATE TABLE IF NOT EXISTS observations(observation_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, mission_type TEXT NOT NULL, metric TEXT NOT NULL, value REAL NOT NULL, connector TEXT NOT NULL, outcome TEXT NOT NULL, ts REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS policies(policy_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL, state TEXT NOT NULL, sample_count INTEGER NOT NULL, confidence REAL NOT NULL, promoted_at REAL, updated_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS repair_outcomes(signature TEXT NOT NULL, strategy TEXT NOT NULL, successes INTEGER NOT NULL DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0, avg_latency_ms REAL NOT NULL DEFAULT 0, updated_at REAL NOT NULL, PRIMARY KEY(signature,strategy));
        CREATE INDEX IF NOT EXISTS idx_obs_scope ON observations(project_id,mission_type,metric,ts);
        """); c.close()
    def add(self, obs: Observation) -> str:
        if not obs.metric.startswith(self.ALLOWED_PREFIXES): raise ValueError(f"Metric not allowed for learning store: {obs.metric}")
        if not isinstance(obs.value, (int,float)): raise TypeError("Operational observations must be numeric")
        oid = "obs_" + uuid.uuid4().hex; ts = obs.ts or _now()
        with self._conn() as c: c.execute("INSERT INTO observations VALUES(?,?,?,?,?,?,?,?)", (oid, obs.project_id, obs.mission_type, obs.metric, float(obs.value), obs.connector, obs.outcome, ts))
        return oid
    def values(self, *, project_id: str, mission_type: str, metric: str, connector: str = "", limit: int = 500) -> List[float]:
        q = "SELECT value FROM observations WHERE project_id=? AND mission_type=? AND metric=?"; args = [project_id, mission_type, metric]
        if connector: q += " AND connector=?"; args.append(connector)
        q += " ORDER BY ts DESC LIMIT ?"; args.append(limit)
        return [float(r["value"]) for r in self._conn().execute(q, args).fetchall()]
    def count(self, *, project_id: str, mission_type: str, metric: str) -> int:
        r = self._conn().execute("SELECT COUNT(*) c FROM observations WHERE project_id=? AND mission_type=? AND metric=?", (project_id,mission_type,metric)).fetchone(); return int(r["c"])
    def save_policy(self, key: str, payload: Dict[str,Any], state: str, sample_count: int, confidence: float, promoted: bool = False):
        with self._conn() as c: c.execute("INSERT OR REPLACE INTO policies VALUES(?,?,?,?,?,?,?)", (key,json.dumps(payload,sort_keys=True),state,sample_count,float(confidence),_now() if promoted else None,_now()))
    def policy(self, key: str) -> Optional[Dict[str,Any]]:
        r = self._conn().execute("SELECT * FROM policies WHERE policy_key=?", (key,)).fetchone()
        if not r: return None
        d = dict(r); d["payload"] = json.loads(d.pop("payload_json")); return d
    def record_repair(self, signature: str, strategy: str, success: bool, latency_ms: float):
        with self._conn() as c:
            r = c.execute("SELECT * FROM repair_outcomes WHERE signature=? AND strategy=?", (signature,strategy)).fetchone()
            if r:
                s,f = int(r["successes"]),int(r["failures"]); n=s+f; avg=(float(r["avg_latency_ms"])*n+float(latency_ms))/(n+1); s+=int(success); f+=int(not success)
            else: s,f,avg=int(success),int(not success),float(latency_ms)
            c.execute("INSERT OR REPLACE INTO repair_outcomes VALUES(?,?,?,?,?,?)", (signature,strategy,s,f,avg,_now()))
    def repair_stats(self, signature: str) -> List[Dict[str,Any]]:
        return [dict(r) for r in self._conn().execute("SELECT * FROM repair_outcomes WHERE signature=?",(signature,)).fetchall()]
    def close(self):
        c=getattr(self._local,"conn",None)
        if c is not None: c.close(); self._local.conn=None
