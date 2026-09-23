from __future__ import annotations
import argparse, sqlite3, json, hashlib, os, time, socket, uuid
from pathlib import Path
from contextlib import contextmanager

SCHEMA="FUSE-GENESIS-RESIDENT-HOST-V1"
VERSION="1.0.1"

def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"))
def sha(x): return hashlib.sha256(canon(x).encode()).hexdigest()

class HostState:
    def __init__(self, root):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.root/"resident.db",isolation_level=None,timeout=5)
        self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS host(
          id INTEGER PRIMARY KEY CHECK(id=1), instance_id TEXT NOT NULL, fence INTEGER NOT NULL,
          started_at REAL NOT NULL, last_heartbeat REAL NOT NULL, state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(
          task_id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, payload_json TEXT NOT NULL,
          state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, checkpoint_json TEXT,
          result_json TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS ticks(
          tick_id TEXT PRIMARY KEY, fence INTEGER NOT NULL, at REAL NOT NULL, digest TEXT NOT NULL);
        """)
    def close(self): self.db.close()

    @contextmanager
    def tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK"); raise

    def claim_host(self, instance_id, fence, now):
        with self.tx():
            cur=self.db.execute("SELECT * FROM host WHERE id=1").fetchone()
            if cur and cur["state"]=="ACTIVE" and fence <= cur["fence"]:
                raise RuntimeError("STALE_OR_DUPLICATE_HOST_FENCE")
            if cur:
                self.db.execute("""UPDATE host SET instance_id=?,fence=?,started_at=?,last_heartbeat=?,state='ACTIVE'
                                  WHERE id=1""",(instance_id,fence,now,now))
            else:
                self.db.execute("""INSERT INTO host(id,instance_id,fence,started_at,last_heartbeat,state)
                                  VALUES(1,?,?,?,?,'ACTIVE')""",(instance_id,fence,now,now))
    def heartbeat(self, instance_id, fence, now):
        with self.tx():
            cur=self.db.execute("SELECT * FROM host WHERE id=1").fetchone()
            if not cur or cur["instance_id"]!=instance_id or cur["fence"]!=fence or cur["state"]!="ACTIVE":
                raise RuntimeError("HOST_FENCE_LOST")
            self.db.execute("UPDATE host SET last_heartbeat=? WHERE id=1",(now,))
            body={"instance_id":instance_id,"fence":fence,"at":now}
            tid=f"{instance_id}:{fence}:{now:.6f}"
            self.db.execute("INSERT INTO ticks(tick_id,fence,at,digest) VALUES(?,?,?,?)",
                            (tid,fence,now,sha(body)))
            return tid

    def release(self, instance_id, fence, now):
        with self.tx():
            cur=self.db.execute("SELECT * FROM host WHERE id=1").fetchone()
            if not cur or cur["instance_id"]!=instance_id or cur["fence"]!=fence:
                raise RuntimeError("HOST_FENCE_LOST")
            self.db.execute("UPDATE host SET state='RELEASED',last_heartbeat=? WHERE id=1",(now,))

    def enqueue(self, task_id, idempotency_key, payload, now):
        with self.tx():
            cur=self.db.execute("SELECT * FROM tasks WHERE idempotency_key=?",(idempotency_key,)).fetchone()
            if cur:
                if json.loads(cur["payload_json"]) != payload:
                    raise RuntimeError("IDEMPOTENCY_COLLISION")
                return cur["task_id"]
            self.db.execute("""INSERT INTO tasks(task_id,idempotency_key,payload_json,state,created_at,updated_at)
                             VALUES(?,?,?,'PENDING',?,?)""",(task_id,idempotency_key,canon(payload),now,now))
            return task_id

    def next_task(self):
        r=self.db.execute("""SELECT * FROM tasks WHERE state IN ('PENDING','RUNNING')
                            ORDER BY created_at,task_id LIMIT 1""").fetchone()
        return dict(r) if r else None

    def checkpoint(self, task_id, cp, now):
        with self.tx():
            self.db.execute("""UPDATE tasks SET state='RUNNING',attempts=attempts+1,checkpoint_json=?,updated_at=?
                              WHERE task_id=?""",(canon(cp),now,task_id))

    def complete(self, task_id, result, now):
        with self.tx():
            self.db.execute("""UPDATE tasks SET state='COMPLETE',result_json=?,updated_at=? WHERE task_id=?""",
                            (canon(result),now,task_id))

    def task(self, task_id):
        r=self.db.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
        return dict(r) if r else None

    def snapshot(self):
        host=self.db.execute("SELECT * FROM host WHERE id=1").fetchone()
        tasks=[dict(x) for x in self.db.execute("SELECT * FROM tasks ORDER BY task_id")]
        ticks=[dict(x) for x in self.db.execute("SELECT * FROM ticks ORDER BY at,tick_id")]
        return {"host":dict(host) if host else None,"tasks":tasks,"ticks":ticks}

class ResidentHost:
    def __init__(self, root, fence, interval=1.0):
        self.root=Path(root); self.fence=int(fence); self.interval=float(interval)
        self.instance_id=f"{socket.gethostname()}-{uuid.uuid4().hex[:12]}"
        self.state=HostState(root)
    def start(self, now=None):
        self.state.claim_host(self.instance_id,self.fence,now if now is not None else time.time())
    def tick(self, now=None):
        return self.state.heartbeat(self.instance_id,self.fence,now if now is not None else time.time())
    def close(self): self.state.close()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=os.environ.get("FUSE_GENESIS_HOST_ROOT","./fuse-host-state"))
    p.add_argument("--fence",type=int,default=int(os.environ.get("FUSE_GENESIS_HOST_FENCE","1")))
    p.add_argument("--once",action="store_true")
    args=p.parse_args()
    h=ResidentHost(args.root,args.fence)
    try:
        h.start()
        tid=h.tick()
        print(json.dumps({"state":"TICK_OK","tick_id":tid,"instance_id":h.instance_id}))
        h.state.release(h.instance_id,h.fence,time.time())
    finally:
        h.close()
if __name__=="__main__": main()
