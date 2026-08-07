from __future__ import annotations
from pathlib import Path
import json,secrets,tempfile,urllib.request
from .backup import BackupManager
from .local_runtime import LocalRuntimeApplication,LocalRuntimeServer

def run_local_canary()->dict[str,object]:
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); token=secrets.token_urlsafe(32); db=td/'state.sqlite3'; audit=td/'audit.sqlite3'; backup=td/'backup.sqlite3'; app=LocalRuntimeApplication(db,audit,token); server=LocalRuntimeServer(app); server.start_in_thread(); host,port=server.server_address; base=f'http://{host}:{port}'; headers={'Authorization':f'Bearer {token}','X-Tenant-ID':'canary-tenant','X-User-ID':'canary-user'}
        def call(path):
            req=urllib.request.Request(base+path,headers=headers); return json.loads(urllib.request.urlopen(req,timeout=3).read())
        health=call('/health'); ready=call('/ready'); verification=call('/v1/verify'); before=app.store.tenant_state_digest('canary-tenant'); receipt=BackupManager().backup(app.store,backup); server.shutdown(); server.server_close(); app.close(); restored=BackupManager().open_verified(backup); after=restored.tenant_state_digest('canary-tenant'); restored.close(); return {'health_ok':health['status']=='ok','ready':ready['ready'],'verify_passed':verification['passed'],'backup_quick_check':receipt['quick_check'],'state_digest_preserved':before==after,'loopback_only':host in {'127.0.0.1','::1'},'live_financial_effects_disabled':health['live_financial_effects'] is False}
if __name__=='__main__': print(json.dumps(run_local_canary(),indent=2,sort_keys=True))
