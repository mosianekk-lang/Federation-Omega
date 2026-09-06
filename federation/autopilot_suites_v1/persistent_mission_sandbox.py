from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json, shutil

class PersistentMissionSandbox:
    def __init__(self,root:str|Path,mission_id:str,ttl_seconds:int=86400,max_bytes:int=5_000_000):
        if not mission_id.strip() or ttl_seconds<=0 or max_bytes<=0: raise ValueError('SANDBOX_CONFIG_INVALID')
        self.root=Path(root).resolve()/mission_id; self.root.mkdir(parents=True,exist_ok=True)
        self.mission_id=mission_id; self.ttl_seconds=ttl_seconds; self.max_bytes=max_bytes
        self.meta=self.root/'sandbox_manifest.json'
        if not self.meta.exists(): self._save_meta({'mission_id':mission_id,'created_at':datetime.now(timezone.utc).isoformat(),'last_access':datetime.now(timezone.utc).isoformat(),'checkpoints':{}})
    def _load_meta(self): return json.loads(self.meta.read_text())
    def _save_meta(self,d): self.meta.write_text(json.dumps(d,indent=2,sort_keys=True))
    def _safe(self,rel):
        p=(self.root/rel).resolve()
        if self.root not in p.parents and p!=self.root: raise ValueError('PATH_TRAVERSAL')
        if p==self.meta: raise ValueError('RESERVED_PATH')
        return p
    def _current_bytes(self): return sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file() and p!=self.meta and '.checkpoints' not in p.parts)
    def put_text(self,rel,text):
        data=text.encode(); current=self._current_bytes(); old=self._safe(rel).stat().st_size if self._safe(rel).exists() else 0
        if current-old+len(data)>self.max_bytes: raise ValueError('SANDBOX_QUOTA_EXCEEDED')
        p=self._safe(rel); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data); self.touch(); return sha256(data).hexdigest()
    def read_text(self,rel): self.touch(); return self._safe(rel).read_text()
    def touch(self): d=self._load_meta(); d['last_access']=datetime.now(timezone.utc).isoformat(); self._save_meta(d)
    def file_hash(self,rel): return sha256(self._safe(rel).read_bytes()).hexdigest()
    def list_files(self): return tuple(sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_file() and p!=self.meta and '.checkpoints' not in p.parts))
    def checkpoint(self,label):
        if not label.strip(): raise ValueError('LABEL_REQUIRED')
        cp=self.root/'.checkpoints'/label
        if cp.exists(): shutil.rmtree(cp)
        cp.mkdir(parents=True)
        for rel in self.list_files():
            src=self.root/rel; dst=cp/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
        d=self._load_meta(); d['checkpoints'][label]={'created_at':datetime.now(timezone.utc).isoformat(),'files':list(self.list_files())}; self._save_meta(d); return label
    def restore(self,label):
        cp=self.root/'.checkpoints'/label
        if not cp.exists(): raise ValueError('CHECKPOINT_NOT_FOUND')
        for rel in self.list_files(): (self.root/rel).unlink()
        for src in cp.rglob('*'):
            if src.is_file():
                rel=src.relative_to(cp); dst=self.root/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
        self.touch()
    def expired(self,now:datetime|None=None):
        now=now or datetime.now(timezone.utc); last=datetime.fromisoformat(self._load_meta()['last_access']); return now-last>=timedelta(seconds=self.ttl_seconds)
    def cleanup_if_expired(self,now=None):
        if self.expired(now): shutil.rmtree(self.root); return True
        return False
