from __future__ import annotations
import argparse, sqlite3, json, hashlib, os, time, socket, uuid, threading
from pathlib import Path
from contextlib import contextmanager
from .currentness import SourceEpoch, resolve_source_epoch

SCHEMA="FUSE-GENESIS-RESIDENT-HOST-V2"
VERSION="2.0.0"

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
        CREATE TABLE IF NOT EXISTS source_epoch(
          id INTEGER PRIMARY KEY CHECK(id=1), main_sha TEXT NOT NULL, writer TEXT NOT NULL,
          fence INTEGER NOT NULL, mission_id TEXT NOT NULL, digest TEXT NOT NULL, bound_at REAL NOT NULL);
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

    def bind_epoch(self, epoch: SourceEpoch, now):
        with self.tx():
            current=self.db.execute("SELECT * FROM source_epoch WHERE id=1").fetchone()
            if current:
                if epoch.fence < int(current["fence"]):
                    raise RuntimeError("STALE_SOURCE_EPOCH")
                if epoch.fence == int(current["fence"]):
                    same=(epoch.main_sha==current["main_sha"] and epoch.writer==current["writer"] and epoch.mission_id==current["mission_id"] and epoch.digest==current["digest"])
                    if not same:
                        raise RuntimeError("SOURCE_EPOCH_COLLISION")
            self.db.execute("""INSERT INTO source_epoch(id,main_sha,writer,fence,mission_id,digest,bound_at)
                             VALUES(1,?,?,?,?,?,?)
                             ON CONFLICT(id) DO UPDATE SET main_sha=excluded.main_sha,writer=excluded.writer,
                             fence=excluded.fence,mission_id=excluded.mission_id,digest=excluded.digest,bound_at=excluded.bound_at""",
                            (epoch.main_sha,epoch.writer,epoch.fence,epoch.mission_id,epoch.digest,now))
        return self.epoch()

    def epoch(self):
        r=self.db.execute("SELECT * FROM source_epoch WHERE id=1").fetchone()
        return dict(r) if r else None

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
            epoch=self.epoch()
            body={"instance_id":instance_id,"fence":fence,"at":now,"source_epoch_digest":epoch["digest"] if epoch else None}
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
        return {"host":dict(host) if host else None,"source_epoch":self.epoch(),"tasks":tasks,"ticks":ticks}

class HostHeartbeatGuard:
    """Independent heartbeat while a task handler may block the main worker loop."""
    def __init__(self, root, instance_id, fence, interval=5.0, now_fn=time.time):
        self.root=Path(root); self.instance_id=instance_id; self.fence=int(fence)
        self.interval=float(interval); self.now_fn=now_fn
        if self.interval <= 0:
            raise ValueError("HEARTBEAT_GUARD_INTERVAL_INVALID")
        self._stop=threading.Event(); self._thread=None; self.error=None

    def _run(self):
        state=HostState(self.root)
        try:
            while not self._stop.wait(self.interval):
                state.heartbeat(self.instance_id,self.fence,self.now_fn())
        except Exception as exc:
            self.error=exc
        finally:
            state.close()

    def start(self):
        if self._thread is not None:
            raise RuntimeError("HEARTBEAT_GUARD_ALREADY_STARTED")
        self._thread=threading.Thread(target=self._run,name="fuse-genesis-heartbeat",daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0,self.interval*3))
        return self

    def assert_healthy(self):
        if self.error is not None:
            raise RuntimeError("HEARTBEAT_GUARD_FAILED") from self.error

class ResidentHost:
    """Long-running executor only. Scheduling remains external (for this estate: Google Apps Script)."""
    def __init__(self, root, epoch: SourceEpoch, interval=1.0, task_heartbeat_interval=5.0):
        self.root=Path(root); self.epoch=resolve_source_epoch(epoch); self.fence=self.epoch.fence; self.interval=float(interval)
        self.task_heartbeat_interval=float(task_heartbeat_interval)
        if self.interval < 0:
            raise ValueError("INTERVAL_INVALID")
        if self.task_heartbeat_interval <= 0:
            raise ValueError("TASK_HEARTBEAT_INTERVAL_INVALID")
        self.instance_id=f"{socket.gethostname()}-{uuid.uuid4().hex[:12]}"
        self.state=HostState(root)
        self._started=False

    def start(self, now=None):
        t=now if now is not None else time.time()
        self.state.bind_epoch(self.epoch,t)
        self.state.claim_host(self.instance_id,self.fence,t)
        self._started=True

    def tick(self, now=None):
        return self.state.heartbeat(self.instance_id,self.fence,now if now is not None else time.time())

    def process_next(self, handler, now=None):
        row=self.state.next_task()
        if row is None:
            return None
        if handler is None:
            return None
        t=now if now is not None else time.time()
        payload=json.loads(row["payload_json"])
        self.state.checkpoint(row["task_id"],{"source_epoch_digest":self.epoch.digest,"resident_instance":self.instance_id},t)
        guard=HostHeartbeatGuard(self.root,self.instance_id,self.fence,self.task_heartbeat_interval).start()
        try:
            result=handler(payload)
        finally:
            guard.stop()
        guard.assert_healthy()
        self.state.complete(row["task_id"],result,time.time() if now is None else now)
        return row["task_id"]

    def run(self, *, handler=None, max_ticks=None, stop_when=None, now_fn=time.time, sleep_fn=time.sleep, release_on_exit=True):
        if max_ticks is not None and (isinstance(max_ticks,bool) or int(max_ticks)<1):
            raise ValueError("MAX_TICKS_INVALID")
        if not self._started:
            self.start(now_fn())
        ticks=0; processed=0
        try:
            while True:
                self.tick(now_fn()); ticks+=1
                if self.process_next(handler,now_fn()) is not None:
                    processed+=1
                if max_ticks is not None and ticks>=int(max_ticks):
                    break
                if stop_when is not None and stop_when():
                    break
                sleep_fn(self.interval)
        finally:
            if release_on_exit:
                self.state.release(self.instance_id,self.fence,now_fn())
                self._started=False
        snap=self.state.snapshot()
        return {"ticks":ticks,"processed":processed,"host_state":snap["host"]["state"],"source_epoch_digest":self.epoch.digest}

    def close(self): self.state.close()

def _epoch_from_args(args):
    if args.source_main or args.writer or args.fence is not None:
        if not (args.source_main and args.writer and args.fence is not None):
            raise SystemExit("--source-main, --writer and --fence must be supplied together")
        return SourceEpoch(args.source_main,args.writer,args.fence,args.mission_id)
    return resolve_source_epoch()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=os.environ.get("FUSE_GENESIS_HOST_ROOT","./fuse-host-state"))
    p.add_argument("--source-main",default=None)
    p.add_argument("--writer",default=None)
    p.add_argument("--fence",type=int,default=None)
    p.add_argument("--mission-id",default=os.environ.get("FUSE_GENESIS_MISSION_ID","GENESIS"))
    p.add_argument("--interval",type=float,default=float(os.environ.get("FUSE_GENESIS_HOST_INTERVAL","1")))
    p.add_argument("--once",action="store_true",help="One heartbeat canary, then release. Default is resident execution.")
    p.add_argument("--max-ticks",type=int,default=None,help="Bounded court/debug mode only; omitted means resident until interrupted.")
    args=p.parse_args()
    epoch=_epoch_from_args(args)
    h=ResidentHost(args.root,epoch,args.interval)
    try:
        if args.once:
            h.start()
            tid=h.tick()
            h.state.release(h.instance_id,h.fence,time.time())
            h._started=False
            print(json.dumps({"state":"ONCE_OK","tick_id":tid,"instance_id":h.instance_id,"source_epoch_digest":epoch.digest}))
        else:
            try:
                receipt=h.run(max_ticks=args.max_ticks)
                print(json.dumps({"state":"RESIDENT_STOPPED",**receipt}))
            except KeyboardInterrupt:
                if h._started:
                    h.state.release(h.instance_id,h.fence,time.time())
                    h._started=False
                print(json.dumps({"state":"RESIDENT_STOPPED","reason":"INTERRUPT","source_epoch_digest":epoch.digest}))
    finally:
        h.close()
if __name__=="__main__": main()
