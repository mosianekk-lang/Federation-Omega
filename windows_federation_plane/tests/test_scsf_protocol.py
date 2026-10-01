from __future__ import annotations

from datetime import datetime, timedelta, timezone
import copy
import json
import unittest

from federation_windows_plane.relay_protocol import canonical_json, sha256_hex
from federation_windows_plane.scsf_protocol import (
    P256SoftwareControlSigner, SCSFRuntime, SCSF_PROTOCOL, SCSF_DEVICE_AUTH_MODE,
    device_id_from_jwk, make_task_envelope, scsf_signing_payload, verify_task_envelope,
)
from federation_windows_plane.trust_spine_v21 import ECDSASigner

NOW = datetime(2026, 9, 15, 3, 0, tzinfo=timezone.utc)
z = lambda d: d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Store:
    def __init__(self): self.d = {"enrollments": {}, "devices": {}, "nonces": {}, "tasks": {}}
    def get(self, c, k):
        v = self.d.setdefault(c, {}).get(k); return copy.deepcopy(v) if v is not None else None
    def create(self, c, k, v, *, replay_code):
        b = self.d.setdefault(c, {})
        if k in b: raise ValueError(replay_code)
        b[k] = copy.deepcopy(dict(v))
    def update(self, c, k, v):
        if k not in self.d.setdefault(c, {}): raise ValueError("MISSING_RECORD")
        self.d[c][k].update(copy.deepcopy(dict(v)))
    def list_for(self, c, field, value, *, limit=100):
        return [dict(copy.deepcopy(v), _id=k) for k, v in list(self.d.setdefault(c, {}).items())[:limit] if v.get(field) == value]
    def consume_enrollment(self, *, grant_key, token_digest, device_id, device_record, now):
        g = self.d["enrollments"].get(grant_key)
        if not g: raise ValueError("SCSF_PAIRING_GRANT_UNKNOWN")
        if g.get("used"): raise ValueError("SCSF_PAIRING_GRANT_ALREADY_USED")
        if now >= g["expires_at"]: raise ValueError("SCSF_PAIRING_GRANT_EXPIRED")
        if g.get("token_digest") != token_digest: raise ValueError("SCSF_PAIRING_GRANT_INVALID")
        g["used"] = True; g["used_at"] = now; g["device_id"] = device_id
        self.d["devices"][device_id] = copy.deepcopy(dict(device_record))
        return copy.deepcopy(g)
    def create_task(self, task_id, record):
        old = self.d["tasks"].get(task_id)
        if old is not None:
            if canonical_json(old.get("envelope")) != canonical_json(record.get("envelope")) or old.get("device_id") != record.get("device_id"):
                raise ValueError("SCSF_TASK_ID_CONFLICT")
            return
        self.d["tasks"][task_id] = copy.deepcopy(dict(record))
    def complete_task(self, *, task_id, device_id, attestation, now):
        r = self.d["tasks"].get(task_id)
        if not r: raise ValueError("SCSF_TASK_UNKNOWN")
        if r.get("protocol") != SCSF_PROTOCOL: raise ValueError("SCSF_TASK_PROTOCOL_INVALID")
        if r.get("device_id") != device_id: raise PermissionError("SCSF_TASK_DEVICE_MISMATCH")
        if r.get("completed"):
            if canonical_json(r.get("result_attestation")) == canonical_json(dict(attestation)): return True
            raise ValueError("SCSF_RESULT_CONFLICT")
        r["completed"] = True; r["completed_at"] = now; r["result_attestation"] = copy.deepcopy(dict(attestation)); return False


def raw_sign(signer: ECDSASigner, payload: bytes) -> str:
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    import base64
    der = signer._key.sign(payload, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return base64.urlsafe_b64encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")).decode().rstrip("=")


def device_jwk(signer: ECDSASigner):
    nums = signer._key.public_key().public_numbers()
    import base64
    enc = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    return {"kty":"EC","crv":"P-256","x":enc(nums.x.to_bytes(32,"big")),"y":enc(nums.y.to_bytes(32,"big"))}


class SCSFProtocolTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(); self.control = P256SoftwareControlSigner.generate(); self.device_key = ECDSASigner.generate()
        self.runtime = SCSFRuntime(store=self.store, control_signer=self.control)
        self.device_jwk = device_jwk(self.device_key); self.device_id = device_id_from_jwk(self.device_jwk)

    def pair(self):
        g = self.runtime.issue_pairing_grant(now=NOW)
        out = self.runtime.enroll({"schema":"FUSE-ENROLL-V1","pairing_grant":g["pairing_grant"],"device_id":self.device_id,"x":self.device_jwk["x"],"y":self.device_jwk["y"]}, now=NOW)
        self.assertEqual(out["state"], "PAIRED")
        self.assertEqual(out["control_signer_jwk"], self.control.public_jwk())
        return g, out

    def signed_request(self, path, body, *, nonce="dev-123456789abc", signed_at=NOW):
        raw = canonical_json(body); ts = z(signed_at)
        sig = raw_sign(self.device_key, scsf_signing_payload(method="POST", path=path, timestamp=ts, nonce=nonce, body=raw))
        return raw, ts, sig

    def auth(self, path, body, *, nonce="dev-123456789abc", signed_at=NOW, observed_at=NOW, x=None, y=None):
        raw, ts, sig = self.signed_request(path, body, nonce=nonce, signed_at=signed_at)
        return self.runtime.verify_request(device_id=self.device_id, method="POST", path=path, timestamp=ts, nonce=nonce,
            signature=sig, key_x=x or self.device_jwk["x"], key_y=y or self.device_jwk["y"], body=raw, now=observed_at)

    def task(self, tid="task-0001"):
        return {"schema":"FUSE-TASK-V1","task_id":tid,"mission_id":"m1","task_type":"system_status","issued_at":z(NOW-timedelta(seconds=1)),
                "expires_at":z(NOW+timedelta(minutes=5)),"nonce":"task-nonce-000001","effect_class":"A1","args":{}}

    def result(self, tid="task-0001", result=None):
        result = {"ok": True} if result is None else result
        payload = {"schema":"FUSE-RESULT-V1","task_id":tid,"device_id":self.device_id,"completed_at":z(NOW),"result":result,"chain_head":"a"*64}
        raw = canonical_json(payload)
        import base64
        return {"schema":"FUSE-RESULT-ATTESTATION-V1","device_id":self.device_id,"task_id":tid,
                "payload_b64":base64.urlsafe_b64encode(raw).decode().rstrip("="),"payload_sha256":sha256_hex(raw),
                "signature_b64":raw_sign(self.device_key, raw),"issued_at":z(NOW)}

    def test_exact_device_id_and_one_time_pairing_same_enrollments_devices_collections(self):
        g, _ = self.pair()
        self.assertTrue(self.device_id.startswith("fuse-dev-")); self.assertEqual(len(self.device_id), 41)
        d = self.store.get("devices", self.device_id)
        self.assertEqual(d["protocol"], SCSF_PROTOCOL); self.assertEqual(d["auth_mode"], SCSF_DEVICE_AUTH_MODE)
        self.assertTrue(any(k.startswith("scsf_") for k in self.store.d["enrollments"]))
        with self.assertRaisesRegex(ValueError, "ALREADY_USED"):
            self.runtime.enroll({"schema":"FUSE-ENROLL-V1","pairing_grant":g["pairing_grant"],"device_id":self.device_id,"x":self.device_jwk["x"],"y":self.device_jwk["y"]}, now=NOW)

    def test_control_signer_unconfigured_fails_closed_without_ephemeral_fallback(self):
        held = SCSFRuntime(store=Store(), control_signer=None)
        with self.assertRaisesRegex(RuntimeError, "SCSF_CONTROL_SIGNER_UNCONFIGURED"):
            held.issue_pairing_grant(now=NOW)

    def test_request_domain_signature_timestamp_key_and_replay_fences(self):
        self.pair(); body={"schema":"FUSE-POLL-V1","chain_head":"0"*64}
        self.auth("/v1/agent/poll", body, nonce="dev-good-123456")
        with self.assertRaisesRegex(ValueError, "REPLAY_DETECTED"): self.auth("/v1/agent/poll", body, nonce="dev-good-123456")
        with self.assertRaisesRegex(ValueError, "TIMESTAMP_OUTSIDE_WINDOW"): self.auth("/v1/agent/poll", body, nonce="dev-old-123456", signed_at=NOW, observed_at=NOW+timedelta(minutes=3))
        with self.assertRaisesRegex(PermissionError, "KEY_HEADER_MISMATCH"): self.auth("/v1/agent/poll", body, nonce="dev-key-1234567", x="A"*43)

    def test_control_signed_envelope_matches_scsf_endpoint_dialect(self):
        self.pair(); task=self.task(); env=self.runtime.queue_task(device_id=self.device_id, task=task, now=NOW)
        decoded=verify_task_envelope(env,self.control.public_jwk(),now=NOW)
        self.assertEqual(decoded,task); self.assertEqual(env["schema"],"FUSE-TASK-ENVELOPE-V1")
        self.assertEqual(self.store.d["tasks"][task["task_id"]]["protocol"],SCSF_PROTOCOL)
        self.assertIn("tasks",self.store.d); self.assertNotIn("scsf_tasks",self.store.d)

    def test_heartbeat_poll_use_same_device_and_task_truth(self):
        self.pair(); d=self.auth("/v1/agent/heartbeat",{"schema":"FUSE-HEARTBEAT-V1","capabilities":{"schema":"FUSE-CAPABILITY-ADVERTISEMENT-V1"},"chain_head":"0"*64},nonce="dev-heart-12345")
        out=self.runtime.heartbeat(device=d,data={"schema":"FUSE-HEARTBEAT-V1","capabilities":{"schema":"FUSE-CAPABILITY-ADVERTISEMENT-V1"},"chain_head":"0"*64},now=NOW)
        self.assertEqual(out["state"],"HEARTBEAT_ACCEPTED")
        self.runtime.queue_task(device_id=self.device_id,task=self.task(),now=NOW)
        d=self.auth("/v1/agent/poll",{"schema":"FUSE-POLL-V1","chain_head":"0"*64},nonce="dev-poll-123456")
        polled=self.runtime.poll(device=d,data={"schema":"FUSE-POLL-V1","chain_head":"0"*64})
        self.assertEqual(polled["state"],"PENDING"); self.assertEqual(polled["envelope"]["schema"],"FUSE-TASK-ENVELOPE-V1")

    def test_device_signed_completion_is_idempotent_and_conflict_fails_closed(self):
        self.pair(); self.runtime.queue_task(device_id=self.device_id,task=self.task(),now=NOW); att=self.result()
        d=self.auth("/v1/agent/complete",att,nonce="dev-done-123456")
        one=self.runtime.complete(device=d,attestation=att,now=NOW); self.assertFalse(one["duplicate"])
        d=self.auth("/v1/agent/complete",att,nonce="dev-done-123457")
        two=self.runtime.complete(device=d,attestation=att,now=NOW); self.assertTrue(two["duplicate"])
        bad=self.result(result={"ok":False})
        d=self.auth("/v1/agent/complete",bad,nonce="dev-done-123458")
        with self.assertRaisesRegex(ValueError,"RESULT_CONFLICT"): self.runtime.complete(device=d,attestation=bad,now=NOW)

    def test_task_id_collision_and_wrong_device_result_rejected(self):
        self.pair(); self.runtime.queue_task(device_id=self.device_id,task=self.task(),now=NOW)
        changed=self.task(); changed["args"]={"changed":True}
        with self.assertRaisesRegex(ValueError,"TASK_ID_CONFLICT"): self.runtime.queue_task(device_id=self.device_id,task=changed,now=NOW)
        att=self.result(); att["device_id"]="fuse-dev-"+"0"*32
        with self.assertRaisesRegex(PermissionError,"RESULT_DEVICE_MISMATCH"):
            self.runtime.complete(device=self.store.get("devices",self.device_id),attestation=att,now=NOW)


if __name__ == "__main__": unittest.main()
