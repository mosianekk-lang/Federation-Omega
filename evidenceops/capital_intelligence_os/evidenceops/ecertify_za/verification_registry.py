from __future__ import annotations
import sqlite3,time
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class PublicVerification:
    verification_code:str
    status:str
    legal_label:str
    document_sha256:str
    issued_at:int
    expires_at:int|None

class SQLiteVerificationRegistry:
    """Reference minimal public-verification registry; contains no raw identity evidence."""
    production_durable=False
    def __init__(self,path:str|Path=":memory:"):
        self.db=sqlite3.connect(str(path),check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS verification(code TEXT PRIMARY KEY,status TEXT,legal_label TEXT,document_sha256 TEXT,issued_at INTEGER,expires_at INTEGER)")
        self.db.commit()
    def publish(self,record:PublicVerification)->None:
        self.db.execute("INSERT OR REPLACE INTO verification(code,status,legal_label,document_sha256,issued_at,expires_at) VALUES(?,?,?,?,?,?)",(record.verification_code,record.status,record.legal_label,record.document_sha256,record.issued_at,record.expires_at));self.db.commit()
    def get(self,code:str,now:int|None=None)->PublicVerification|None:
        row=self.db.execute("SELECT code,status,legal_label,document_sha256,issued_at,expires_at FROM verification WHERE code=?",(code,)).fetchone()
        if not row:return None
        result=PublicVerification(*row);current=int(time.time()) if now is None else int(now)
        if result.expires_at is not None and result.expires_at<current:return PublicVerification(result.verification_code,"EXPIRED",result.legal_label,result.document_sha256,result.issued_at,result.expires_at)
        return result
    def close(self):self.db.close()
