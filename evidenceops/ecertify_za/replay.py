from __future__ import annotations
import importlib,os,sqlite3,time
from pathlib import Path
from typing import Callable,Protocol,runtime_checkable

@runtime_checkable
class ReplayGuard(Protocol):
    """Atomic provider/transaction uniqueness contract.

    Production implementations must persist across process restarts and be atomic
    across all active service instances. `claim` returns True exactly once for a
    provider/transaction pair.
    """
    def claim(self,provider:str,transaction_id:str)->bool: ...

class SQLiteReplayGuard:
    """Single-node/local reference implementation; not a distributed production store."""
    production_distributed=False
    def __init__(self,path:str|Path=":memory:"):
        self.db=sqlite3.connect(str(path),check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS seen(provider TEXT, transaction_id TEXT, seen_at INTEGER, PRIMARY KEY(provider,transaction_id))")
        self.db.commit()
    def claim(self,provider:str,transaction_id:str)->bool:
        try:
            self.db.execute("INSERT INTO seen(provider,transaction_id,seen_at) VALUES(?,?,?)",(provider,transaction_id,int(time.time())))
            self.db.commit();return True
        except sqlite3.IntegrityError:return False
    def close(self):self.db.close()

class PostgresReplayGuard:
    """Production-capable atomic replay guard using an injected DB-API connection factory.

    The deployment layer supplies a factory backed by Cloud SQL/PostgreSQL or an
    equivalent managed PostgreSQL service. No database credentials live in this module.
    """
    production_distributed=True
    def __init__(self,connection_factory:Callable[[],object]):self.connection_factory=connection_factory
    def claim(self,provider:str,transaction_id:str)->bool:
        conn=self.connection_factory()
        try:
            cur=conn.cursor()
            cur.execute("INSERT INTO ecertify_receipt_replay(provider,transaction_id,seen_at) VALUES(%s,%s,%s) ON CONFLICT(provider,transaction_id) DO NOTHING RETURNING transaction_id",(provider,transaction_id,int(time.time())))
            row=cur.fetchone();conn.commit();return row is not None
        except Exception:
            try:conn.rollback()
            except Exception:pass
            raise
        finally:
            try:conn.close()
            except Exception:pass

class ProductionReplayGuardRequired(RuntimeError):pass

def require_distributed_replay(guard:ReplayGuard)->None:
    if not bool(getattr(guard,"production_distributed",False)):
        raise ProductionReplayGuardRequired("DISTRIBUTED_REPLAY_GUARD_NOT_BOUND")

def _load_factory(spec:str)->Callable[[],object]:
    if ":" not in spec:raise ValueError("ECERTIFY_DB_FACTORY_MUST_BE_MODULE_COLON_CALLABLE")
    module_name,callable_name=spec.split(":",1);obj=getattr(importlib.import_module(module_name),callable_name)
    if not callable(obj):raise TypeError("ECERTIFY_DB_FACTORY_NOT_CALLABLE")
    return obj

def load_replay_guard(*,production:bool=False)->ReplayGuard:
    backend=os.environ.get("ECERTIFY_REPLAY_BACKEND","sqlite").strip().lower()
    if backend=="postgres":
        spec=os.environ.get("ECERTIFY_DB_FACTORY","").strip()
        if not spec:raise ProductionReplayGuardRequired("ECERTIFY_DB_FACTORY_NOT_CONFIGURED")
        guard=PostgresReplayGuard(_load_factory(spec))
    elif backend=="sqlite":
        guard=SQLiteReplayGuard(os.environ.get("ECERTIFY_REPLAY_DB","/tmp/ecertify-replay.sqlite"))
    else:raise ValueError("UNSUPPORTED_REPLAY_BACKEND")
    if production:require_distributed_replay(guard)
    return guard
