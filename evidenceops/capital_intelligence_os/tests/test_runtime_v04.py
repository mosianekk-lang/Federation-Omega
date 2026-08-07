from __future__ import annotations
from pathlib import Path
import json,secrets,tempfile,unittest
from evidenceops.capital_intelligence_os.audit import AuditLedger
from evidenceops.capital_intelligence_os.backup import BackupManager
from evidenceops.capital_intelligence_os.canary import run_local_canary
from evidenceops.capital_intelligence_os.local_runtime import LocalRuntimeApplication,LocalRuntimeServer
from evidenceops.capital_intelligence_os.models import Domain,Event,InformationClass
from evidenceops.capital_intelligence_os.policy import RuntimePolicy
from evidenceops.capital_intelligence_os.store import SqliteStateStore

class PolicyTests(unittest.TestCase):
    def setUp(self): self.token='x'*32; self.p=RuntimePolicy(self.token)
    def test_short_token_rejected(self):
        with self.assertRaises(ValueError): RuntimePolicy('short')
    def test_auth_requires_tenant_user(self):
        with self.assertRaises(PermissionError): self.p.authenticate('Bearer '+self.token,None,'u')
    def test_invalid_token_rejected(self):
        with self.assertRaises(PermissionError): self.p.authenticate('Bearer '+'y'*32,'t','u')
    def test_unknown_route_default_denied(self):
        with self.assertRaisesRegex(PermissionError,'ROUTE_DEFAULT_DENY'): self.p.authorize('GET','/admin')
    def test_trade_route_constitutionally_denied(self):
        with self.assertRaisesRegex(PermissionError,'CONSEQUENTIAL_ROUTE_NOT_EXPOSED'): self.p.authorize('POST','/trade/order')
class AuditTests(unittest.TestCase):
    def test_chain_and_tamper_detection(self):
        a=AuditLedger(':memory:'); a.append('t','u','GET','/health','ALLOW',{}); a.append('t','u','POST','/v1/events','ALLOW',{'x':1}); self.assertTrue(a.verify()); a.conn.execute("UPDATE audit_records SET outcome='TAMPERED' WHERE sequence_no=2"); self.assertFalse(a.verify()); a.close()
class BackupTests(unittest.TestCase):
    def test_backup_restore_preserves_state_digest(self):
        with tempfile.TemporaryDirectory() as td:
            source=SqliteStateStore(Path(td)/'source.sqlite3'); event=Event('X','s','sub',{'x':1},Domain.PRIVATE_MNA,InformationClass.CONFIDENTIAL,.2); source.append_event('t',event); before=source.tenant_state_digest('t'); rec=BackupManager().backup(source,Path(td)/'backup.sqlite3'); self.assertTrue(rec['quick_check']); source.close(); restored=BackupManager().open_verified(Path(td)/'backup.sqlite3'); self.assertEqual(before,restored.tenant_state_digest('t')); restored.close()
class RuntimeApplicationTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory(); self.token=secrets.token_urlsafe(32); self.app=LocalRuntimeApplication(Path(self.td.name)/'state.db',Path(self.td.name)/'audit.db',self.token); self.h={'Authorization':'Bearer '+self.token,'X-Tenant-ID':'t','X-User-ID':'u'}
    def tearDown(self): self.app.close(); self.td.cleanup()
    def test_health_requires_auth(self): self.assertEqual(self.app.handle('GET','/health',{})[0],401)
    def test_health_and_ready(self): self.assertEqual(self.app.handle('GET','/health',self.h)[0],200); self.assertTrue(self.app.handle('GET','/ready',self.h)[1]['ready'])
    def test_ingest_is_idempotent(self):
        body=json.dumps({'event_type':'X','subject_id':'s','payload':{},'domain':'PRIVATE_MNA','information_class':'CONFIDENTIAL','materiality':.2,'event_id':'fixed','occurred_at':'2026-08-07T09:00:00+00:00'}).encode(); h={**self.h,'Idempotency-Key':'k'}; first=self.app.handle('POST','/v1/events',h,body); second=self.app.handle('POST','/v1/events',h,body); self.assertEqual(first[0],200); self.assertTrue(second[1]['replayed'])
    def test_missing_occurred_at_rejected(self):
        body=json.dumps({'event_type':'X','subject_id':'s','payload':{},'domain':'PRIVATE_MNA','information_class':'CONFIDENTIAL','event_id':'x'}).encode(); self.assertEqual(self.app.handle('POST','/v1/events',self.h,body)[0],400)
    def test_consequential_route_not_exposed(self): self.assertEqual(self.app.handle('POST','/payments',self.h,b'{}')[0],403)
    def test_audit_records_requests(self): self.app.handle('GET','/health',self.h); self.assertEqual(self.app.audit.count(),1); self.assertTrue(self.app.audit.verify())
class ServerTests(unittest.TestCase):
    def test_non_loopback_bind_denied(self):
        with tempfile.TemporaryDirectory() as td:
            app=LocalRuntimeApplication(Path(td)/'s.db',Path(td)/'a.db','z'*32)
            try:
                with self.assertRaises(PermissionError): LocalRuntimeServer(app,'0.0.0.0',0)
            finally: app.close()
    def test_full_local_canary(self): self.assertTrue(all(run_local_canary().values()))
if __name__=='__main__': unittest.main()
