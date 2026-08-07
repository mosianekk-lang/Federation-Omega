from __future__ import annotations
import sqlite3,time
from pathlib import Path
from typing import Protocol,runtime_checkable

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
    def __init__(self,path: str|Path=":memory:"):
        self.db=sqlite3.connect(str(path),check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS seen(provider TEXT, transaction_id TEXT, seen_at INTEGER, PRIMARY KEY(provider,transaction_id))")
        self.db.commit()
    def claim(self,provider:str,transaction_id:str)->bool:
        try:
            self.db.execute("INSERT INTO seen(provider,transaction_id,seen_at) VALUES(?,?,?)",(provider,transaction_id,int(time.time())))
            self.db.commit();return True
        except sqlite3.IntegrityError:return False
    def close(self):self.db.close()

class ProductionReplayGuardRequired(RuntimeError):pass

def require_distributed_replay(guard:ReplayGuard)->None:
    """Fail closed before production/horizontal-scale promotion."""
    if not bool(getattr(guard,"production_distributed",False)):
        raise ProductionReplayGuardRequired("DISTRIBUTED_REPLAY_GUARD_NOT_BOUND")
