from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
import json, threading
from .audit import AuditLedger
from .durable import DurableAutopilotRuntime
from .models import Domain, Event, InformationClass
from .policy import RuntimePolicy
from .store import SqliteStateStore
from .tenancy import TenantContext

class LocalRuntimeApplication:
    def __init__(self,db_path:str|Path,audit_path:str|Path,bearer_token:str)->None:
        self.store=SqliteStateStore(db_path); self.audit=AuditLedger(audit_path); self.runtime=DurableAutopilotRuntime(self.store); self.policy=RuntimePolicy(bearer_token)
    def close(self): self.store.close(); self.audit.close()
    def handle(self,method:str,path:str,headers:dict[str,str],body:bytes=b'')->tuple[int,dict[str,Any]]:
        normalized_headers={k.lower():v for k,v in headers.items()}
        def hv(name:str): return normalized_headers.get(name.lower())
        try: self.policy.authorize(method,path)
        except PermissionError as e:
            self.audit.append(hv('X-Tenant-ID') or 'UNKNOWN',hv('X-User-ID') or 'UNKNOWN',method,path,'DENY',{'reason':str(e)}); return 403,{'error':str(e)}
        try: principal=self.policy.authenticate(hv('Authorization'),hv('X-Tenant-ID'),hv('X-User-ID'))
        except PermissionError as e:
            self.audit.append(hv('X-Tenant-ID') or 'UNKNOWN',hv('X-User-ID') or 'UNKNOWN',method,path,'DENY',{'reason':str(e)}); return 401,{'error':str(e)}
        ctx=TenantContext(principal.tenant_id,principal.user_id,principal.roles)
        try:
            if method=='GET' and path=='/health': payload={'status':'ok','mode':'LOCAL_CANARY','database_quick_check':self.store.quick_check(),'audit_chain_valid':self.audit.verify(),'live_financial_effects':False}
            elif method=='GET' and path=='/ready': payload={'ready':self.store.quick_check() and self.audit.verify(),'authority_ceiling':'A1_INTERNAL'}
            elif method=='GET' and path=='/v1/verify':
                from .verify_release import verify
                payload=verify()
            elif method=='POST' and path=='/v1/events':
                data=json.loads(body.decode() or '{}')
                if not data.get('occurred_at'): raise ValueError('occurred_at is required for idempotent event ingestion')
                event=Event(data['event_type'],data.get('source','local-api'),data['subject_id'],data.get('payload',{}),Domain(data['domain']),InformationClass(data['information_class']),float(data.get('materiality',0.0)),event_id=data.get('event_id') or __import__('uuid').uuid4().hex,occurred_at=data['occurred_at'])
                payload=self.runtime.process(ctx,event,idempotency_key=hv('Idempotency-Key'))
            else: return 403,{'error':'ROUTE_DEFAULT_DENY'}
            self.audit.append(principal.tenant_id,principal.user_id,method,path,'ALLOW',{'status':200}); return 200,payload
        except Exception as e:
            self.audit.append(principal.tenant_id,principal.user_id,method,path,'ERROR',{'type':type(e).__name__}); return 400,{'error':type(e).__name__,'detail':str(e)}

class _Handler(BaseHTTPRequestHandler):
    server_version='CIOSLocalCanary/0.4'
    def _dispatch(self):
        length=int(self.headers.get('Content-Length','0')); body=self.rfile.read(length) if length else b''; headers={k:v for k,v in self.headers.items()}; status,payload=self.server.app.handle(self.command,self.path,headers,body); data=json.dumps(payload,sort_keys=True,default=str).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    do_GET=_dispatch; do_POST=_dispatch
    def log_message(self,*args): return

class LocalRuntimeServer(ThreadingHTTPServer):
    def __init__(self,app:LocalRuntimeApplication,host='127.0.0.1',port=0):
        if host not in {'127.0.0.1','localhost','::1'}: raise PermissionError('LOCAL_CANARY_LOOPBACK_ONLY')
        self.app=app; super().__init__((host,port),_Handler)
    def start_in_thread(self):
        thread=threading.Thread(target=self.serve_forever,daemon=True); thread.start(); return thread
