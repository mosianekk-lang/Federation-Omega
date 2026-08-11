from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import hashlib, sqlite3
from .models import canonical_json, utc_now_iso

@dataclass(frozen=True)
class AuditRecord:
    sequence_no:int; tenant_id:str; actor_id:str; action:str; resource:str; outcome:str; payload_hash:str; previous_hash:str; record_hash:str; created_at:str

class AuditLedger:
    def __init__(self,path:str|Path=':memory:')->None:
        self.path=str(path); self.conn=sqlite3.connect(self.path,isolation_level=None,check_same_thread=False); self.conn.row_factory=sqlite3.Row
        self.conn.execute('CREATE TABLE IF NOT EXISTS audit_records(sequence_no INTEGER PRIMARY KEY,tenant_id TEXT NOT NULL,actor_id TEXT NOT NULL,action TEXT NOT NULL,resource TEXT NOT NULL,outcome TEXT NOT NULL,payload_hash TEXT NOT NULL,previous_hash TEXT NOT NULL,record_hash TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL)')
    def close(self): self.conn.close()
    @staticmethod
    def _hash(seq,tenant,actor,action,resource,outcome,payload_hash,previous,created):
        return hashlib.sha256(canonical_json({'sequence_no':seq,'tenant_id':tenant,'actor_id':actor,'action':action,'resource':resource,'outcome':outcome,'payload_hash':payload_hash,'previous_hash':previous,'created_at':created}).encode()).hexdigest()
    def append(self,tenant_id:str,actor_id:str,action:str,resource:str,outcome:str,payload:Mapping[str,Any]|None=None)->AuditRecord:
        row=self.conn.execute('SELECT sequence_no,record_hash FROM audit_records ORDER BY sequence_no DESC LIMIT 1').fetchone(); seq=(row['sequence_no']+1) if row else 1; previous=row['record_hash'] if row else 'GENESIS'; created=utc_now_iso(); payload_hash=hashlib.sha256(canonical_json(dict(payload or {})).encode()).hexdigest(); digest=self._hash(seq,tenant_id,actor_id,action,resource,outcome,payload_hash,previous,created)
        self.conn.execute('INSERT INTO audit_records VALUES(?,?,?,?,?,?,?,?,?,?)',(seq,tenant_id,actor_id,action,resource,outcome,payload_hash,previous,digest,created)); return AuditRecord(seq,tenant_id,actor_id,action,resource,outcome,payload_hash,previous,digest,created)
    def verify(self)->bool:
        previous='GENESIS'
        for r in self.conn.execute('SELECT * FROM audit_records ORDER BY sequence_no'):
            expected=self._hash(r['sequence_no'],r['tenant_id'],r['actor_id'],r['action'],r['resource'],r['outcome'],r['payload_hash'],r['previous_hash'],r['created_at'])
            if r['previous_hash']!=previous or r['record_hash']!=expected: return False
            previous=r['record_hash']
        return True
    def count(self)->int: return int(self.conn.execute('SELECT COUNT(*) FROM audit_records').fetchone()[0])
