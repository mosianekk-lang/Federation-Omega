from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from federation_windows_plane.pairing_service import (
    BOUND_REQUEST_SCHEMA, EXECUTION_LEASE_SCHEMA, PAIRING_AUTH_MODE,
    POSTURE_SCHEMA, RESULT_ATTESTATION_SCHEMA, ZERO_CHAIN, PairingRuntime,
    _body_json,
)
from federation_windows_plane.relay_protocol import canonical_json, sha256_hex, signing_payload
from federation_windows_plane.trust_spine_v21 import ECDSASigner

NOW = datetime(2026, 9, 13, 6, 0, tzinfo=timezone.utc)
SOURCE, POLICY = "a" * 40, "WOAF_TRUST_SPINE_V21"
z = lambda d: d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Store:
    def __init__(self): self.d = {}
    def get(self, c, k):
        v = self.d.get(c, {}).get(k); return dict(v) if v is not None else None
    def create(self, c, k, v, *, replay_code):
        b = self.d.setdefault(c, {})
        if k in b: raise ValueError(replay_code)
        b[k] = dict(v)
    def update(self, c, k, v):
        if k not in self.d.setdefault(c, {}): raise ValueError("MISSING_RECORD")
        self.d[c][k].update(dict(v))


@dataclass
class Lease:
    task_id: str; device_id: str; lease_token: str; leased_at: str; expires_at: str


class Relay:
    def __init__(self): self.item = None; self.done = {}
    def poll(self, *, device_id, now=None): return self.item
    def complete(self, *, device_id, task_id, lease_token, receipt):
        v = dict(receipt); p = self.done.get(task_id)
        if p is not None and p != v: raise ValueError("TASK_ALREADY_COMPLETED")
        self.done[task_id] = v; return v


class PairingTests(unittest.TestCase):
    def setUp(self):
        self.s, self.r = Store(), Relay()
        self.p = PairingRuntime(relay=self.r, store=self.s, source_epoch=SOURCE, policy_epoch=POLICY)
        self.k, self.badk = ECDSASigner.generate(), ECDSASigner.generate()

    def pair(self):
        g = self.p.issue_pairing_grant(now=NOW)
        c = self.p.start_pairing(pairing_grant_id=g["pairing_grant_id"], pairing_token=g["pairing_token"],
            device_label="owner-v6", public_key_spki_b64=self.k.public_spki_b64(), device_generation=1,
            source_epoch=SOURCE, policy_epoch=POLICY, now=NOW)["challenge"]
        x = self.p.complete_pairing(pairing_grant_id=g["pairing_grant_id"], pairing_token=g["pairing_token"],
            challenge_id=c["challenge_id"], challenge_signature_b64=self.k.sign_b64(canonical_json(c)),
            device_label="owner-v6", public_key_spki_b64=self.k.public_spki_b64(), now=NOW)
        return g, c, x

    def bind(self, x, **kw):
        return {"schema":BOUND_REQUEST_SCHEMA,"device_id":x["credential"]["device_id"],
            "identity_id":kw.get("identity_id",x["identity"]["identity_id"]),
            "device_generation":kw.get("generation",1),"source_epoch":kw.get("source",SOURCE),
            "policy_epoch":kw.get("policy",POLICY),"recovery_cursor":kw.get("cursor",ZERO_CHAIN)}

    def auth(self, x, b, *, nonce="n1", when=NOW, path="/agent/runtime/poll"):
        body = canonical_json({"binding":b}); ts = z(when)
        sig = self.k.sign_b64(signing_payload(method="POST",path=path,timestamp=ts,nonce=nonce,body=body))
        return self.p.verify_bound_request(device_id=x["credential"]["device_id"],method="POST",path=path,
            timestamp=ts,nonce=nonce,signature=sig,body=body,binding=b,now=when)

    def test_possession_proof_and_pairing_replay(self):
        g,c,x = self.pair(); d=self.s.get("devices",x["credential"]["device_id"])
        self.assertEqual(d["auth_mode"],PAIRING_AUTH_MODE)
        with self.assertRaisesRegex(ValueError,"ALREADY_USED|REPLAY"):
            self.p.complete_pairing(pairing_grant_id=g["pairing_grant_id"],pairing_token=g["pairing_token"],
                challenge_id=c["challenge_id"],challenge_signature_b64=self.k.sign_b64(canonical_json(c)),
                device_label="owner-v6",public_key_spki_b64=self.k.public_spki_b64(),now=NOW)

    def test_wrong_key_and_challenge_mismatch(self):
        g=self.p.issue_pairing_grant(now=NOW); c=self.p.start_pairing(pairing_grant_id=g["pairing_grant_id"],pairing_token=g["pairing_token"],
            device_label="owner-v6",public_key_spki_b64=self.k.public_spki_b64(),device_generation=1,source_epoch=SOURCE,policy_epoch=POLICY,now=NOW)["challenge"]
        with self.assertRaisesRegex(PermissionError,"KEY_MISMATCH"):
            self.p.complete_pairing(pairing_grant_id=g["pairing_grant_id"],pairing_token=g["pairing_token"],challenge_id=c["challenge_id"],
                challenge_signature_b64=self.badk.sign_b64(canonical_json(c)),device_label="owner-v6",public_key_spki_b64=self.badk.public_spki_b64(),now=NOW)
        with self.assertRaisesRegex(PermissionError,"DEVICE_MISMATCH"):
            self.p.complete_pairing(pairing_grant_id=g["pairing_grant_id"],pairing_token=g["pairing_token"],challenge_id=c["challenge_id"],
                challenge_signature_b64=self.k.sign_b64(canonical_json(c)),device_label="other",public_key_spki_b64=self.k.public_spki_b64(),now=NOW)

    def test_expired_grant_and_start_fences(self):
        g=self.p.issue_pairing_grant(now=NOW)
        with self.assertRaisesRegex(ValueError,"GRANT_EXPIRED"):
            self.p.start_pairing(pairing_grant_id=g["pairing_grant_id"],pairing_token=g["pairing_token"],device_label="owner-v6",
                public_key_spki_b64=self.k.public_spki_b64(),device_generation=1,source_epoch=SOURCE,policy_epoch=POLICY,now=NOW+timedelta(seconds=301))
        for k,v,code in [("device_generation",2,"GENERATION"),("source_epoch","b"*40,"SOURCE"),("policy_epoch","OLD","POLICY")]:
            g=self.p.issue_pairing_grant(now=NOW); a=dict(device_generation=1,source_epoch=SOURCE,policy_epoch=POLICY);a[k]=v
            with self.assertRaisesRegex(PermissionError,code):
                self.p.start_pairing(pairing_grant_id=g["pairing_grant_id"],pairing_token=g["pairing_token"],device_label="owner-v6",public_key_spki_b64=self.k.public_spki_b64(),now=NOW,**a)

    def test_nonce_replay_and_bound_generation_source_policy(self):
        _,_,x=self.pair(); b=self.bind(x); self.auth(x,b,nonce="same")
        with self.assertRaisesRegex(ValueError,"REPLAY_DETECTED"): self.auth(x,b,nonce="same")
        for i,(b2,code) in enumerate([(self.bind(x,generation=2),"GENERATION"),(self.bind(x,source="b"*40),"SOURCE"),(self.bind(x,policy="OLD"),"POLICY")]):
            with self.assertRaisesRegex(PermissionError,code): self.auth(x,b2,nonce=f"f{i}")

    def test_identity_renewal_and_expiry(self):
        _,_,x=self.pair(); d=self.s.get("devices",x["credential"]["device_id"])
        n=self.p.renew_identity(device=d,now=NOW+timedelta(seconds=1)); b=self.bind(x,identity_id=n["identity_id"])
        self.auth(x,b,nonce="ok",when=NOW+timedelta(seconds=2))
        with self.assertRaisesRegex(PermissionError,"IDENTITY_EXPIRED"): self.auth(x,b,nonce="late",when=NOW+timedelta(seconds=602))

    def test_tpm_posture_and_staleness(self):
        _,_,x=self.pair(); d=self.s.get("devices",x["credential"]["device_id"])
        p={"schema":POSTURE_SCHEMA,"device_id":d["device_id"],"device_generation":1,"tpm_state":"TPM_PLATFORM","secure_boot":True,
           "bitlocker":True,"defender":True,"firewall":True,"os_build":"26100","patch_age_days":1,"agent_version":"6","agent_sha256":"e"*64,
           "clock_skew_seconds":0,"key_status":"ACTIVE","session_state":"ACTIVE","power_state":"AC","observed_at":z(NOW)}
        self.assertGreaterEqual(self.p.accept_posture(device=d,posture=p,now=NOW)["posture_score"],90)
        q=dict(p);q["observed_at"]=z(NOW-timedelta(minutes=6))
        with self.assertRaisesRegex(PermissionError,"POSTURE_STALE"): self.p.accept_posture(device=d,posture=q,now=NOW)
        q=dict(p);q["tpm_state"]="SOFTWARE"
        with self.assertRaisesRegex(PermissionError,"TPM_PLATFORM_REQUIRED"): self.p.accept_posture(device=d,posture=q,now=NOW)

    def test_cursor_recovery_and_expired_execution_lease(self):
        _,_,x=self.pair(); d=self.s.get("devices",x["credential"]["device_id"]); b=self.bind(x)
        self.assertEqual(self.p.poll(device=d,binding=b,now=NOW)["state"],"EMPTY")
        with self.assertRaisesRegex(PermissionError,"CURSOR"): self.p.poll(device=d,binding=self.bind(x,cursor="1"*64),now=NOW)
        lease={"schema":EXECUTION_LEASE_SCHEMA,"task_id":"t","device_id":d["device_id"],"device_generation":1,"source_epoch":SOURCE,"policy_epoch":POLICY,
               "lease_token":"x","leased_at":z(NOW-timedelta(minutes=2)),"expires_at":z(NOW-timedelta(seconds=1))}
        with self.assertRaisesRegex(PermissionError,"LEASE_EXPIRED"): self.p.complete(device=d,binding=b,task_id="t",lease=lease,receipt={},result_attestation={},now=NOW)

    def test_device_signed_result_chain_and_duplicate_completion(self):
        _,_,x=self.pair(); d=self.s.get("devices",x["credential"]["device_id"]); b=self.bind(x); tid="t1"
        self.r.item=({"task_id":tid,"task_type":"health"},Lease(tid,d["device_id"],"lt",z(NOW),z(NOW+timedelta(minutes=2))))
        leased=self.p.poll(device=d,binding=b,now=NOW)
        r={"schema":"FEDERATION-WINDOWS-RECEIPT-V1","task_id":tid,"correlation_id":"c","task_type":"health","state":"COMPLETED_VERIFIED_LOCAL",
           "started_at":z(NOW),"completed_at":z(NOW+timedelta(seconds=1)),"runner":{"os":"Windows"},"task":{"task_id":tid},"result":{"ok":True},
           "task_sha256":sha256_hex(canonical_json({"task_id":tid})),"result_sha256":sha256_hex(canonical_json({"ok":True})),"effect":"READ_ONLY"}
        a={"schema":RESULT_ATTESTATION_SCHEMA,"device_id":d["device_id"],"device_generation":1,"identity_id":d["current_identity_id"],"task_id":tid,
           "source_epoch":SOURCE,"policy_epoch":POLICY,"result_sha256":r["result_sha256"],"receipt_sha256":sha256_hex(canonical_json(r)),
           "previous_receipt_sha256":ZERO_CHAIN,"issued_at":z(NOW+timedelta(seconds=1))}
        a["signature_b64"]=self.k.sign_b64(canonical_json(a))
        one=self.p.complete(device=d,binding=b,task_id=tid,lease=leased["lease"],receipt=r,result_attestation=a,now=NOW+timedelta(seconds=1))
        d2=self.s.get("devices",d["device_id"]); two=self.p.complete(device=d2,binding=b,task_id=tid,lease=leased["lease"],receipt=r,result_attestation=a,now=NOW+timedelta(seconds=2))
        self.assertFalse(one["duplicate"]); self.assertTrue(two["duplicate"]); self.assertEqual(one["recovery_cursor"],two["recovery_cursor"])

    def test_malformed_payload_entrypoint_and_no_shell_surface(self):
        with self.assertRaisesRegex(ValueError,"JSON_BODY_REQUIRED"): _body_json(b"{")
        with self.assertRaisesRegex(ValueError,"JSON_OBJECT_REQUIRED"): _body_json(b"[]")
        root=Path(__file__).resolve().parents[2]; py=(root/"windows_federation_plane"/"pyproject.toml").read_text(); src=(root/"windows_federation_plane"/"src"/"federation_windows_plane"/"pairing_service.py").read_text().lower()
        self.assertIn('federation-windows-relay = "federation_windows_plane.pairing_service:main"',py)
        self.assertNotIn('custom_route("/mcp"',src)
        for denied in ("subprocess.run","os.system","powershell","cmd.exe"): self.assertNotIn(denied,src)


if __name__ == "__main__": unittest.main()
