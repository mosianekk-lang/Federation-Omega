from __future__ import annotations
from pathlib import Path
import hashlib, sqlite3
from .store import SqliteStateStore

class BackupManager:
    def backup(self,store:SqliteStateStore,destination:str|Path)->dict[str,object]:
        destination=Path(destination); destination.parent.mkdir(parents=True,exist_ok=True); target=sqlite3.connect(str(destination)); store._connection.backup(target); target.close(); digest=hashlib.sha256(destination.read_bytes()).hexdigest(); check=sqlite3.connect(str(destination)).execute('PRAGMA quick_check').fetchone()[0]=='ok'; return {'path':str(destination),'sha256':digest,'quick_check':check,'bytes':destination.stat().st_size}
    def open_verified(self,path:str|Path)->SqliteStateStore:
        store=SqliteStateStore(path)
        if not store.quick_check(): store.close(); raise RuntimeError('BACKUP_QUICK_CHECK_FAILED')
        return store
