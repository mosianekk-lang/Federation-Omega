from __future__ import annotations
import json, sqlite3, threading, time, uuid
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Sequence


def _now() -> float:
    return time.time()


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    name: str
    matter_wall: str
    governor_profile: str = "DEFAULT"
    active: bool = True


@dataclass
class EvidenceRecord:
    project_id: str
    source_id: str
    source_type: str
    version: str = ""
    modified_at: str = ""
    verified: bool = False
    sha256: str = ""
    claims: List[str] = field(default_factory=list)
    sensitivity: str = "PROJECT"


class FederationRegistry:
    """Durable shared registry. One DB can serve all governed projects/chats."""

    def __init__(self, path: str = "bubbles_federation_governor_omega4.sqlite3"):
        self.path = path
        self._local = threading.local()
        self._bootstrap()

    def _conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=FULL")
            c.execute("PRAGMA foreign_keys=ON")
            self._local.conn = c
        return c

    def _bootstrap(self) -> None:
        c = sqlite3.connect(self.path)
        c.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=FULL;
        CREATE TABLE IF NOT EXISTS projects(
          project_id TEXT PRIMARY KEY, name TEXT NOT NULL, matter_wall TEXT NOT NULL,
          governor_profile TEXT NOT NULL, active INTEGER NOT NULL, updated_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS missions(
          mission_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, origin_chat TEXT,
          objective TEXT NOT NULL, current_stage TEXT NOT NULL, active_lanes_json TEXT NOT NULL,
          blockers_json TEXT NOT NULL, next_gate TEXT, checkpoint_pointer TEXT,
          executable_next INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL,
          FOREIGN KEY(project_id) REFERENCES projects(project_id));
        CREATE TABLE IF NOT EXISTS chat_shims(
          chat_key TEXT PRIMARY KEY, project_id TEXT NOT NULL, mission_id TEXT,
          payload_json TEXT NOT NULL, payload_bytes INTEGER NOT NULL, governor_version TEXT NOT NULL,
          updated_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS evidence(
          project_id TEXT NOT NULL, source_id TEXT NOT NULL, payload_json TEXT NOT NULL,
          version TEXT, modified_at TEXT, verified INTEGER NOT NULL, sha256 TEXT,
          sensitivity TEXT NOT NULL, updated_at REAL NOT NULL,
          PRIMARY KEY(project_id, source_id));
        CREATE TABLE IF NOT EXISTS capabilities(
          capability_id TEXT PRIMARY KEY, role TEXT NOT NULL, tags_json TEXT NOT NULL,
          registry_pointer TEXT, active INTEGER NOT NULL, updated_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS work_receipts(
          fingerprint TEXT PRIMARY KEY, project_id TEXT NOT NULL, mission_id TEXT NOT NULL,
          state TEXT NOT NULL, source_version TEXT, result_pointer TEXT, semantic_ok INTEGER NOT NULL,
          updated_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS federation_events(
          event_id TEXT PRIMARY KEY, project_id TEXT, mission_id TEXT, chat_key TEXT,
          event_type TEXT NOT NULL, payload_json TEXT NOT NULL, proof_bearing INTEGER NOT NULL,
          created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS metrics(
          metric_key TEXT PRIMARY KEY, ewma REAL NOT NULL, samples INTEGER NOT NULL,
          last_value REAL NOT NULL, updated_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_mission_project ON missions(project_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_events_project ON federation_events(project_id, created_at DESC);
        """)
        c.close()

    def register_project(self, rec: ProjectRecord) -> None:
        with self._conn() as c:
            c.execute("""INSERT INTO projects VALUES(?,?,?,?,?,?)
              ON CONFLICT(project_id) DO UPDATE SET name=excluded.name, matter_wall=excluded.matter_wall,
              governor_profile=excluded.governor_profile, active=excluded.active, updated_at=excluded.updated_at""",
              (rec.project_id, rec.name, rec.matter_wall, rec.governor_profile, int(rec.active), _now()))

    def project(self, project_id: str) -> Optional[Dict[str, Any]]:
        r = self._conn().execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        return dict(r) if r else None

    def register_mission(self, *, mission_id: str, project_id: str, objective: str,
                         origin_chat: str = "", stage: str = "ACTIVE",
                         active_lanes: Sequence[str] = (), blockers: Sequence[str] = (),
                         next_gate: str = "", checkpoint_pointer: str = "",
                         executable_next: bool = False) -> None:
        if not self.project(project_id):
            raise KeyError(f"Unknown project: {project_id}")
        with self._conn() as c:
            c.execute("""INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(mission_id) DO UPDATE SET
                project_id=excluded.project_id, origin_chat=excluded.origin_chat,
                objective=excluded.objective, current_stage=excluded.current_stage,
                active_lanes_json=excluded.active_lanes_json, blockers_json=excluded.blockers_json,
                next_gate=excluded.next_gate, checkpoint_pointer=excluded.checkpoint_pointer,
                executable_next=excluded.executable_next, updated_at=excluded.updated_at""",
                (mission_id, project_id, origin_chat, objective, stage,
                 json.dumps(list(active_lanes)), json.dumps(list(blockers)), next_gate,
                 checkpoint_pointer, int(executable_next), _now()))

    def mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        r = self._conn().execute("SELECT * FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["active_lanes"] = json.loads(d.pop("active_lanes_json"))
        d["blockers"] = json.loads(d.pop("blockers_json"))
        return d

    def missions(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if project_id:
            rows = self._conn().execute("SELECT * FROM missions WHERE project_id=?", (project_id,)).fetchall()
        else:
            rows = self._conn().execute("SELECT * FROM missions").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["active_lanes"] = json.loads(d.pop("active_lanes_json"))
            d["blockers"] = json.loads(d.pop("blockers_json"))
            out.append(d)
        return out

    def save_shim(self, chat_key: str, project_id: str, mission_id: str,
                  payload: Dict[str, Any], governor_version: str) -> None:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._conn() as c:
            c.execute("""INSERT OR REPLACE INTO chat_shims
              VALUES(?,?,?,?,?,?,?)""",
              (chat_key, project_id, mission_id, raw, len(raw.encode()), governor_version, _now()))

    def put_evidence(self, rec: EvidenceRecord) -> None:
        if not self.project(rec.project_id):
            raise KeyError(f"Unknown project: {rec.project_id}")
        payload = json.dumps(asdict(rec), sort_keys=True)
        with self._conn() as c:
            c.execute("""INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?)
              ON CONFLICT(project_id,source_id) DO UPDATE SET
                payload_json=excluded.payload_json, version=excluded.version,
                modified_at=excluded.modified_at, verified=excluded.verified,
                sha256=excluded.sha256, sensitivity=excluded.sensitivity, updated_at=excluded.updated_at""",
                (rec.project_id, rec.source_id, payload, rec.version, rec.modified_at,
                 int(rec.verified), rec.sha256, rec.sensitivity, _now()))

    def evidence(self, project_id: str, source_id: str) -> Optional[EvidenceRecord]:
        r = self._conn().execute(
            "SELECT payload_json FROM evidence WHERE project_id=? AND source_id=?",
            (project_id, source_id)).fetchone()
        return EvidenceRecord(**json.loads(r["payload_json"])) if r else None

    def evidence_needs_refresh(self, project_id: str, source_id: str,
                               version: str = "", modified_at: str = "") -> bool:
        rec = self.evidence(project_id, source_id)
        if not rec or not rec.verified:
            return True
        if version and rec.version and version != rec.version:
            return True
        if modified_at and rec.modified_at and modified_at != rec.modified_at:
            return True
        return False

    def register_capability(self, capability_id: str, role: str,
                            tags: Sequence[str], registry_pointer: str = "") -> None:
        with self._conn() as c:
            c.execute("""INSERT OR REPLACE INTO capabilities VALUES(?,?,?,?,?,?)""",
              (capability_id, role, json.dumps(sorted(set(tags))), registry_pointer, 1, _now()))

    def resolve_capabilities(self, needed_tags: Sequence[str], max_results: int = 4) -> List[str]:
        needed = set(needed_tags)
        scored = []
        for r in self._conn().execute("SELECT * FROM capabilities WHERE active=1").fetchall():
            tags = set(json.loads(r["tags_json"]))
            score = len(tags & needed)
            if score:
                scored.append((score, r["capability_id"]))
        return [cid for _, cid in sorted(scored, key=lambda x: (-x[0], x[1]))[:max_results]]

    def receipt(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        r = self._conn().execute("SELECT * FROM work_receipts WHERE fingerprint=?", (fingerprint,)).fetchone()
        return dict(r) if r else None

    def save_receipt(self, *, fingerprint: str, project_id: str, mission_id: str,
                     state: str, source_version: str = "", result_pointer: str = "",
                     semantic_ok: bool = True) -> None:
        with self._conn() as c:
            c.execute("""INSERT OR REPLACE INTO work_receipts VALUES(?,?,?,?,?,?,?,?)""",
              (fingerprint, project_id, mission_id, state, source_version,
               result_pointer, int(semantic_ok), _now()))

    def event(self, *, event_type: str, payload: Dict[str, Any], project_id: str = "",
              mission_id: str = "", chat_key: str = "", proof_bearing: bool = False) -> str:
        eid = f"fe_{uuid.uuid4().hex}"
        with self._conn() as c:
            c.execute("INSERT INTO federation_events VALUES(?,?,?,?,?,?,?,?)",
              (eid, project_id, mission_id, chat_key, event_type,
               json.dumps(payload, sort_keys=True, default=str), int(proof_bearing), _now()))
        return eid

    def update_metric(self, key: str, value: float, alpha: float = 0.25) -> float:
        with self._conn() as c:
            r = c.execute("SELECT ewma,samples FROM metrics WHERE metric_key=?", (key,)).fetchone()
            if r:
                ewma = alpha * value + (1-alpha) * float(r["ewma"]); samples = int(r["samples"])+1
            else:
                ewma = value; samples = 1
            c.execute("INSERT OR REPLACE INTO metrics VALUES(?,?,?,?,?)",
              (key, ewma, samples, value, _now()))
        return ewma

    def metric(self, key: str) -> Optional[float]:
        r = self._conn().execute("SELECT ewma FROM metrics WHERE metric_key=?", (key,)).fetchone()
        return float(r["ewma"]) if r else None

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
