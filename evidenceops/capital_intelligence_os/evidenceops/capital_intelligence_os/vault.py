from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import hashlib,json,re,sqlite3,uuid
from .models import InformationClass,canonical_json,utc_now_iso
from .tenancy import TenantContext
@dataclass(frozen=True)
class DocumentRecord:
    document_id:str; tenant_id:str; logical_key:str; filename:str; document_type:str; content_type:str; sha256:str; size_bytes:int; information_class:InformationClass; version_no:int; previous_document_id:str|None; source_id:str; created_at:str; tags:tuple[str,...]=()
class InformationAccessPolicy:
    ROLE_REQUIREMENTS={InformationClass.CONFIDENTIAL:{'deal_member','admin'},InformationClass.CLEAN_TEAM:{'clean_team','admin'},InformationClass.POTENTIALLY_MNPI:{'restricted_access','admin'},InformationClass.RESTRICTED:{'restricted_access','admin'},InformationClass.PRIVILEGED:{'legal_privileged','admin'}}
    def allowed(self,ctx:TenantContext,classification:InformationClass)->bool:
        if classification==InformationClass.UNKNOWN:return False
        if classification==InformationClass.PUBLIC:return True
        return bool(set(ctx.roles)&self.ROLE_REQUIREMENTS.get(classification,{'admin'}))
    def assert_allowed(self,ctx,classification):
        if not self.allowed(ctx,classification):raise PermissionError('DOCUMENT_CLASSIFICATION_ACCESS_DENIED')
class DocumentVault:
    def __init__(self,path:str|Path=':memory:')->None:
        self.path=str(path); self.conn=sqlite3.connect(self.path,isolation_level=None,check_same_thread=False); self.conn.row_factory=sqlite3.Row; self.access=InformationAccessPolicy(); self.conn.executescript('CREATE TABLE IF NOT EXISTS documents(document_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,logical_key TEXT NOT NULL,filename TEXT NOT NULL,document_type TEXT NOT NULL,content_type TEXT NOT NULL,sha256 TEXT NOT NULL,size_bytes INTEGER NOT NULL,information_class TEXT NOT NULL,version_no INTEGER NOT NULL,previous_document_id TEXT,source_id TEXT NOT NULL,created_at TEXT NOT NULL,tags_json TEXT NOT NULL,extracted_text TEXT NOT NULL); CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_tenant_hash ON documents(tenant_id,sha256); CREATE INDEX IF NOT EXISTS idx_doc_logical ON documents(tenant_id,logical_key,version_no);')
    def close(self):self.conn.close()
    def ingest(self,ctx:TenantContext,*,logical_key:str,filename:str,document_type:str,content_type:str,content:bytes,information_class:InformationClass,source_id:str,extracted_text:str='',tags:Iterable[str]=())->tuple[DocumentRecord,bool]:
        ctx.validate(); self.access.assert_allowed(ctx,information_class)
        if not logical_key or not filename or not document_type or not source_id:raise ValueError('document identity fields required')
        digest=hashlib.sha256(content).hexdigest(); existing=self.conn.execute('SELECT * FROM documents WHERE tenant_id=? AND sha256=?',(ctx.tenant_id,digest)).fetchone()
        if existing:return self._row(existing),True
        prior=self.conn.execute('SELECT * FROM documents WHERE tenant_id=? AND logical_key=? ORDER BY version_no DESC LIMIT 1',(ctx.tenant_id,logical_key)).fetchone(); version=(prior['version_no']+1) if prior else 1; previous=prior['document_id'] if prior else None; document_id=str(uuid.uuid4()); created=utc_now_iso(); tags_tuple=tuple(sorted(set(str(t) for t in tags))); self.conn.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(document_id,ctx.tenant_id,logical_key,filename,document_type,content_type,digest,len(content),information_class.value,version,previous,source_id,created,canonical_json(tags_tuple),extracted_text or '')); return DocumentRecord(document_id,ctx.tenant_id,logical_key,filename,document_type,content_type,digest,len(content),information_class,version,previous,source_id,created,tags_tuple),False
    def latest(self,ctx,logical_key):
        ctx.validate(); row=self.conn.execute('SELECT * FROM documents WHERE tenant_id=? AND logical_key=? ORDER BY version_no DESC LIMIT 1',(ctx.tenant_id,logical_key)).fetchone()
        if not row:return None
        rec=self._row(row); self.access.assert_allowed(ctx,rec.information_class); return rec
    def search(self,ctx,query,limit=20):
        ctx.validate(); terms=[t for t in re.findall(r'[a-z0-9]+',query.lower()) if len(t)>1]
        if not terms:return []
        results=[]
        for row in self.conn.execute('SELECT * FROM documents WHERE tenant_id=?',(ctx.tenant_id,)):
            rec=self._row(row)
            if not self.access.allowed(ctx,rec.information_class):continue
            text=(row['filename']+' '+row['document_type']+' '+row['extracted_text']+' '+' '.join(rec.tags)).lower(); score=sum(text.count(t) for t in terms)
            if score:results.append({'document_id':rec.document_id,'logical_key':rec.logical_key,'version_no':rec.version_no,'filename':rec.filename,'document_type':rec.document_type,'score':score,'sha256':rec.sha256})
        return sorted(results,key=lambda x:(-int(x['score']),str(x['filename'])))[:limit]
    def document_types(self,ctx):
        ctx.validate(); result=set()
        for row in self.conn.execute('SELECT * FROM documents WHERE tenant_id=?',(ctx.tenant_id,)):
            rec=self._row(row)
            if self.access.allowed(ctx,rec.information_class):result.add(rec.document_type)
        return result
    def _row(self,row):return DocumentRecord(row['document_id'],row['tenant_id'],row['logical_key'],row['filename'],row['document_type'],row['content_type'],row['sha256'],row['size_bytes'],InformationClass(row['information_class']),row['version_no'],row['previous_document_id'],row['source_id'],row['created_at'],tuple(json.loads(row['tags_json'])))
