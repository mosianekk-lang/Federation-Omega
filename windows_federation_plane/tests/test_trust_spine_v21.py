from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from federation_windows_plane import trust_spine_v21 as t

NOW=datetime(2026,9,12,7,20,0,tzinfo=timezone.utc)
def z(v):return v.isoformat().replace('+00:00','Z')

class TrustSpineV21Tests(unittest.TestCase):
    def test_relay_modes_fail_closed(self):
        self.assertEqual(t.relay_mode(oidc_issuer=None,oidc_jwks_url=None),'AGENT_ONLY_BOOTSTRAP')
        self.assertEqual(t.relay_mode(oidc_issuer='https://issuer',oidc_jwks_url='https://jwks'),'FULL_MCP_AGENT')
        with self.assertRaisesRegex(ValueError,'MIXED'):t.relay_mode(oidc_issuer='https://issuer',oidc_jwks_url=None)
        with self.assertRaisesRegex(ValueError,'HTTPS'):t.relay_mode(oidc_issuer='http://issuer',oidc_jwks_url='https://jwks')
    def test_agent_only_denies_mcp_and_shell(self):
        self.assertFalse(t.agent_only_route_allowed('/mcp'))
        self.assertTrue(t.agent_only_route_allowed('/node'))
        self.assertNotIn('shell',t.ALLOWLISTED_CAPABILITIES)
        self.assertNotIn('powershell',t.ALLOWLISTED_CAPABILITIES)
        self.assertEqual(t.B0_ALLOWLISTED_CAPABILITIES,frozenset({'health','inventory'}))
    def test_signed_capability_fences_and_replay(self):
        s=t.ECDSASigner.generate();args={'x':1};e=t.CapabilityEnvelope('cap','dev',2,'m','task','health',t.sha256_hex(t.canonical_bytes(args)),'s','p','d'*64,'READ_ONLY',50,'n',z(NOW-timedelta(seconds=1)),z(NOW+timedelta(minutes=5)),'lease');cap=t.SignedCapability.issue(e,s);seen=set()
        cap.verify(authority_spki_b64=s.public_spki_b64(),expected_device_id='dev',expected_device_generation=2,expected_source_epoch='s',expected_policy_epoch='p',expected_manifest_digest='d'*64,actual_args=args,allowed_capabilities={'health'},actual_posture_score=90,now=NOW,seen_nonces=seen)
        with self.assertRaisesRegex(PermissionError,'NONCE_REPLAY'):cap.verify(authority_spki_b64=s.public_spki_b64(),expected_device_id='dev',expected_device_generation=2,expected_source_epoch='s',expected_policy_epoch='p',expected_manifest_digest='d'*64,actual_args=args,allowed_capabilities={'health'},actual_posture_score=90,now=NOW,seen_nonces=seen)
    def test_posture_caps_authority(self):
        p=t.PostureEnvelope('p','d',1,'TPM_PLATFORM',True,True,True,True,'1',1,'2.1','a'*64,0,'ACTIVE','UNLOCKED','AC',z(NOW));self.assertEqual(p.score(),100)
        q=t.PostureEnvelope('p','d',1,'SOFTWARE',False,False,False,False,'1',90,'2.1','a'*64,600,'BAD','UNLOCKED','BATTERY',z(NOW));self.assertLess(q.score(),50)
    def test_execution_lease_and_prepare_commit(self):
        lease=t.ExecutionLease('l','task','dev',1,'s','p',z(NOW),z(NOW+timedelta(seconds=1)));lease.verify(task_id='task',device_id='dev',device_generation=1,source_epoch='s',policy_epoch='p',now=NOW)
        with self.assertRaisesRegex(PermissionError,'LEASE_EXPIRED'):lease.verify(task_id='task',device_id='dev',device_generation=1,source_epoch='s',policy_epoch='p',now=NOW+timedelta(seconds=2))
        prep=t.PreparedEffect('x','a'*64,'b'*64,'s','p');permit=t.CommitPermit(prep.digest(),z(NOW),z(NOW+timedelta(minutes=1)));permit.verify(prep,NOW)
        with self.assertRaisesRegex(PermissionError,'PREPARE_DIGEST_MISMATCH'):permit.verify(t.PreparedEffect('y','a'*64,'b'*64,'s','p'),NOW)
    def test_receipt_chain_and_encrypted_spool(self):
        chain=t.ReceiptChain();chain.append({'a':1});chain.append({'b':2});t.ReceiptChain.verify(chain.receipts)
        bad=chain.receipts;bad[1]['body']['b']=3
        with self.assertRaises(ValueError):t.ReceiptChain.verify(bad)
        spool=t.EncryptedReceiptSpool(b'k'*32);blob=spool.seal([{'x':1}]);self.assertEqual(spool.open(blob),[{'x':1}])
        with self.assertRaises(Exception):spool.open(blob[:-1]+bytes([blob[-1]^1]))
    def test_quarantine_rotation_and_update_rollback(self):
        d=t.DeviceLifecycle();d.transition(t.DeviceState.ACTIVE);d.transition(t.DeviceState.ROTATED);self.assertEqual(d.generation,2)
        with self.assertRaises(ValueError):d.transition(t.DeviceState.ACTIVE)
        s=t.ECDSASigner.generate();state=t.UpdateState(2,1,'b'*64);m=t.UpdateManifest(3,'c'*64,z(NOW),z(NOW+timedelta(minutes=5)),2);sig=s.sign_b64(t.canonical_bytes(m.payload()));state.stage(m,sig,s.public_spki_b64(),now=NOW,observed_binary_sha256='c'*64);state.promote(m)
        rollback=t.UpdateManifest(2,'b'*64,z(NOW),z(NOW+timedelta(minutes=5)),3);rsig=s.sign_b64(t.canonical_bytes(rollback.payload()))
        with self.assertRaisesRegex(PermissionError,'ROLLBACK'):state.stage(rollback,rsig,s.public_spki_b64(),now=NOW,observed_binary_sha256='b'*64)
    def test_canary_001_v3_evidence_gate(self):
        c=t.Canary001V3()
        with self.assertRaisesRegex(ValueError,'CANARY_EVIDENCE_MISSING'):c.advance(set())
        c.advance(set(t._REQUIRED_CANARY_EVIDENCE[t.CanaryPhase.UNLOCKED]));self.assertEqual(c.phase,t.CanaryPhase.LOCK_TRANSITION)
    def test_capsule_loader_and_resource_governor(self):
        payload=b'abc';m=t.ArtifactCapsuleManifest('c','1','windows','x64','native','run','https://example/c',len(payload),t.sha256_hex(payload),'sig','s','p',('health',),'READ_ONLY',{},z(NOW+timedelta(minutes=5)));m.verify_bytes(payload,now=NOW)
        with self.assertRaisesRegex(ValueError,'DIGEST'):m.verify_bytes(b'abd',now=NOW)
        with self.assertRaisesRegex(ValueError,'HTTPS'):t.ArtifactCapsuleManifest('c','1','w','x','n','r','http://bad',1,'0'*64,'sig','s','p',(), 'READ_ONLY',{},z(NOW+timedelta(minutes=1))).validate(now=NOW)
        node=t.NodeCapabilities('B0_EPHEMERAL_LOW_TRUST',8,2048,'WEBGPU',True,False,256,50,'AC','visible');g=t.ResourceSovereigntyGovernor().grant(node,requested_workers=20,requested_memory_mb=9999,requested_gpu=True,max_seconds=9999);self.assertLessEqual(g.cpu_workers,4);self.assertEqual(g.memory_mb,2048);self.assertTrue(g.gpu_allowed);self.assertEqual(g.max_seconds,900);self.assertGreater(t.placement_score(node,needs_gpu=True,min_memory_mb=512),0)

if __name__=='__main__':unittest.main()
