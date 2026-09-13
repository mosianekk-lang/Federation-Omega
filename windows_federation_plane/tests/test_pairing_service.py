from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from federation_windows_plane.pairing_service import (
    BOUND_REQUEST_SCHEMA,
    EXECUTION_LEASE_SCHEMA,
    PAIRING_AUTH_MODE,
    POSTURE_SCHEMA,
    RESULT_ATTESTATION_SCHEMA,
    ZERO_CHAIN,
    PairingRuntime,
    _body_json,
)
from federation_windows_plane.relay_protocol import canonical_json, sha256_hex, signing_payload
from federation_windows_plane.trust_spine_v21 import ECDSASigner

NOW = datetime(2026, 9, 13, 6, 0, 0, tzinfo=timezone.utc)
SOURCE = "a" * 40
POLICY = "WOAF_TRUST_SPINE_V21"


def z(v: datetime) -> str:
    return v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class FakeStore:
    def __init__(self):
        self.data: dict[str, dict[str, dict]] = {}

    def get(self, collection: str, key: str):
        value = self.data.get(collection, {}).get(key)
        return dict(value) if value is not None else None

    def create(self, collection: str, key: str, value, *, replay_code: str):
        bucket = self.data.setdefault(collection, {})
        if key in bucket:
            raise ValueError(replay_code)
        bucket[key] = dict(value)

    def update(self, collection: str, key: str, value):
        bucket = self.data.setdefault(collection, {})
        if key not in bucket:
            raise ValueError("MISSING_RECORD")
        bucket[key].update(dict(value))


@dataclass
class FakeLease:
    task_id: str
    device_id: str
    lease_token: str
    leased_at: str
    expires_at: str


class FakeRelay:
    def __init__(self):
        self.poll_item = None
        self.completed: dict[str, dict] = {}

    def poll(self, *, device_id: str, now=None):
        return self.poll_item

    def complete(self, *, device_id: str, task_id: str, lease_token: str, receipt):
        prior = self.completed.get(task_id)
        value = dict(receipt)
        if prior is not None and prior != value:
            raise ValueError("TASK_ALREADY_COMPLETED")
        self.completed[task_id] = value
        return value


class PairingServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.relay = FakeRelay()
        self.runtime = PairingRuntime(
            relay=self.relay,
            store=self.store,
            source_epoch=SOURCE,
            policy_epoch=POLICY,
            pairing_ttl_seconds=300,
            challenge_ttl_seconds=120,
            identity_ttl_seconds=600,
            request_skew_seconds=60,
        )
        self.signer = ECDSASigner.generate()
        self.other = ECDSASigner.generate()

    def pair(self, signer=None, *, now=NOW):
        signer = signer or self.signer
        grant = self.runtime.issue_pairing_grant(now=now)
        start = self.runtime.start_pairing(
            pairing_grant_id=grant["pairing_grant_id"],
            pairing_token=grant["pairing_token"],
            device_label="owner-v6",
            public_key_spki_b64=signer.public_spki_b64(),
            device_generation=1,
            source_epoch=SOURCE,
            policy_epoch=POLICY,
            now=now,
        )
        challenge = start["challenge"]
        complete = self.runtime.complete_pairing(
            pairing_grant_id=grant["pairing_grant_id"],
            pairing_token=grant["pairing_token"],
            challenge_id=challenge["challenge_id"],
            challenge_signature_b64=signer.sign_b64(canonical_json(challenge)),
            device_label="owner-v6",
            public_key_spki_b64=signer.public_spki_b64(),
            now=now,
        )
        return grant, start, complete

    def binding(self, paired, *, cursor=ZERO_CHAIN, generation=1, source=SOURCE, policy=POLICY, identity_id=None):
        return {
            "schema": BOUND_REQUEST_SCHEMA,
            "device_id": paired["credential"]["device_id"],
            "identity_id": identity_id or paired["identity"]["identity_id"],
            "device_generation": generation,
            "source_epoch": source,
            "policy_epoch": policy,
            "recovery_cursor": cursor,
        }

    def auth(self, paired, signer, path, body_obj, *, nonce="n-1", now=NOW):
        body = canonical_json(body_obj)
        timestamp = z(now)
        signature = signer.sign_b64(signing_payload(method="POST", path=path, timestamp=timestamp, nonce=nonce, body=body))
        return self.runtime.verify_bound_request(
            device_id=paired["credential"]["device_id"],
            method="POST", path=path, timestamp=timestamp, nonce=nonce, signature=signature,
            body=body, binding=body_obj["binding"], now=now,
        )

    def test_pairing_requires_private_key_possession_and_is_single_use(self):
        grant, start, paired = self.pair()
        self.assertEqual(paired["state"], "PAIRED")
        dev = self.store.get("devices", paired["credential"]["device_id"])
        self.assertEqual(dev["auth_mode"], PAIRING_AUTH_MODE)
        self.assertEqual(dev["receipt_chain_head"], ZERO_CHAIN)
        with self.assertRaisesRegex(ValueError, "PAIRING_GRANT_ALREADY_USED|PAIRING_CHALLENGE_ALREADY_USED|PAIRING_GRANT_REPLAY"):
            self.runtime.complete_pairing(
                pairing_grant_id=grant["pairing_grant_id"], pairing_token=grant["pairing_token"],
                challenge_id=start["challenge"]["challenge_id"],
                challenge_signature_b64=self.signer.sign_b64(canonical_json(start["challenge"])),
                device_label="owner-v6", public_key_spki_b64=self.signer.public_spki_b64(), now=NOW,
            )

    def test_wrong_key_and_challenge_mismatch_fail_closed(self):
        grant = self.runtime.issue_pairing_grant(now=NOW)
        start = self.runtime.start_pairing(
            pairing_grant_id=grant["pairing_grant_id"], pairing_token=grant["pairing_token"],
            device_label="owner-v6", public_key_spki_b64=self.signer.public_spki_b64(),
            device_generation=1, source_epoch=SOURCE, policy_epoch=POLICY, now=NOW,
        )
        c = start["challenge"]
        with self.assertRaisesRegex(PermissionError, "KEY_MISMATCH"):
            self.runtime.complete_pairing(
                pairing_grant_id=grant["pairing_grant_id"], pairing_token=grant["pairing_token"],
                challenge_id=c["challenge_id"], challenge_signature_b64=self.other.sign_b64(canonical_json(c)),
                device_label="owner-v6", public_key_spki_b64=self.other.public_spki_b64(), now=NOW,
            )
        with self.assertRaisesRegex(PermissionError, "DEVICE_MISMATCH"):
            self.runtime.complete_pairing(
                pairing_grant_id=grant["pairing_grant_id"], pairing_token=grant["pairing_token"],
                challenge_id=c["challenge_id"], challenge_signature_b64=self.signer.sign_b64(canonical_json(c)),
                device_label="different-label", public_key_spki_b64=self.signer.public_spki_b64(), now=NOW,
            )

    def test_expired_grant_and_stale_generation_source_policy_rejected(self):
        grant = self.runtime.issue_pairing_grant(now=NOW)
        with self.assertRaisesRegex(ValueError, "PAIRING_GRANT_EXPIRED"):
            self.runtime.start_pairing(
                pairing_grant_id=grant["pairing_grant_id"], pairing_token=grant["pairing_token"],
                device_label="owner-v6", public_key_spki_b64=self.signer.public_spki_b64(),
                device_generation=1, source_epoch=SOURCE, policy_epoch=POLICY, now=NOW + timedelta(seconds=301),
            )
        fresh = self.runtime.issue_pairing_grant(now=NOW)
        for kw, code in [
            ({"device_generation": 2, "source_epoch": SOURCE, "policy_epoch": POLICY}, "DEVICE_GENERATION_FENCE"),
            ({"device_generation": 1, "source_epoch": "b" * 40, "policy_epoch": POLICY}, "SOURCE_EPOCH_FENCE"),
            ({"device_generation": 1, "source_epoch": SOURCE, "policy_epoch": "OLD"}, "POLICY_EPOCH_FENCE"),
        ]:
            with self.assertRaisesRegex(PermissionError, code):
                self.runtime.start_pairing(
                    pairing_grant_id=fresh["pairing_grant_id"], pairing_token=fresh["pairing_token"],
                    device_label="owner-v6", public_key_spki_b64=self.signer.public_spki_b64(), now=NOW, **kw,
                )

    def test_request_nonce_replay_and_fences_rejected(self):
        _, _, paired = self.pair()
        body = {"binding": self.binding(paired)}
        self.auth(paired, self.signer, "/agent/runtime/poll", body, nonce="nonce-a")
        with self.assertRaisesRegex(ValueError, "REPLAY_DETECTED"):
            self.auth(paired, self.signer, "/agent/runtime/poll", body, nonce="nonce-a")
        cases = [
            (self.binding(paired, generation=2), "DEVICE_GENERATION_FENCE"),
            (self.binding(paired, source="b" * 40), "SOURCE_EPOCH_FENCE"),
            (self.binding(paired, policy="OLD"), "POLICY_EPOCH_FENCE"),
        ]
        for i, (binding, code) in enumerate(cases):
            with self.assertRaisesRegex(PermissionError, code):
                self.auth(paired, self.signer, "/agent/runtime/poll", {"binding": binding}, nonce=f"fence-{i}")

    def test_expired_identity_rejected_and_renewal_rotates_identity(self):
        _, _, paired = self.pair()
        device = self.store.get("devices", paired["credential"]["device_id"])
        renewed = self.runtime.renew_identity(device=device, now=NOW + timedelta(seconds=10))
        self.assertNotEqual(renewed["identity_id"], paired["identity"]["identity_id"])
        body = {"binding": self.binding(paired, identity_id=renewed["identity_id"])}
        self.auth(paired, self.signer, "/agent/runtime/poll", body, nonce="renewed", now=NOW + timedelta(seconds=20))
        with self.assertRaisesRegex(PermissionError, "IDENTITY_EXPIRED"):
            self.auth(paired, self.signer, "/agent/runtime/poll", body, nonce="expired", now=NOW + timedelta(seconds=611))

    def test_signed_tpm_posture_and_stale_posture_rejected(self):
        _, _, paired = self.pair()
        device = self.store.get("devices", paired["credential"]["device_id"])
        posture = {
            "schema": POSTURE_SCHEMA, "device_id": device["device_id"], "device_generation": 1,
            "tpm_state": "TPM_PLATFORM", "secure_boot": True, "bitlocker": True, "defender": True,
            "firewall": True, "os_build": "26100", "patch_age_days": 1, "agent_version": "6",
            "agent_sha256": "e" * 64, "clock_skew_seconds": 0, "key_status": "ACTIVE",
            "session_state": "ACTIVE", "power_state": "AC", "observed_at": z(NOW),
        }
        accepted = self.runtime.accept_posture(device=device, posture=posture, now=NOW)
        self.assertGreaterEqual(accepted["posture_score"], 90)
        stale = dict(posture); stale["observed_at"] = z(NOW - timedelta(minutes=6))
        with self.assertRaisesRegex(PermissionError, "POSTURE_STALE"):
            self.runtime.accept_posture(device=device, posture=stale, now=NOW)
        bad = dict(posture); bad["tpm_state"] = "SOFTWARE"
        with self.assertRaisesRegex(PermissionError, "TPM_PLATFORM_REQUIRED"):
            self.runtime.accept_posture(device=device, posture=bad, now=NOW)

    def test_reconnect_cursor_and_lease_expiry_fail_closed(self):
        _, _, paired = self.pair()
        device = self.store.get("devices", paired["credential"]["device_id"])
        binding = self.binding(paired)
        self.assertEqual(self.runtime.poll(device=device, binding=binding, now=NOW)["state"], "EMPTY")
        bad = dict(binding); bad["recovery_cursor"] = "1" * 64
        with self.assertRaisesRegex(PermissionError, "RECOVERY_CURSOR_MISMATCH"):
            self.runtime.poll(device=device, binding=bad, now=NOW)
        expired_lease = {
            "schema": EXECUTION_LEASE_SCHEMA, "task_id": "task-1", "device_id": device["device_id"],
            "device_generation": 1, "source_epoch": SOURCE, "policy_epoch": POLICY, "lease_token": "lease-token",
            "leased_at": z(NOW - timedelta(minutes=3)), "expires_at": z(NOW - timedelta(seconds=1)),
        }
        with self.assertRaisesRegex(PermissionError, "LEASE_EXPIRED"):
            self.runtime.complete(device=device, binding=binding, task_id="task-1", lease=expired_lease,
                                  receipt={}, result_attestation={}, now=NOW)

    def test_device_signed_result_chain_and_duplicate_completion(self):
        _, _, paired = self.pair()
        device = self.store.get("devices", paired["credential"]["device_id"])
        task_id = "task-chain-1"
        self.relay.poll_item = (
            {"task_id": task_id, "task_type": "health"},
            FakeLease(task_id, device["device_id"], "lease-token", z(NOW), z(NOW + timedelta(minutes=2))),
        )
        binding = self.binding(paired)
        leased = self.runtime.poll(device=device, binding=binding, now=NOW)
        receipt = {
            "schema": "FEDERATION-WINDOWS-RECEIPT-V1", "task_id": task_id, "correlation_id": "corr-1",
            "task_type": "health", "state": "COMPLETED_VERIFIED_LOCAL", "started_at": z(NOW),
            "completed_at": z(NOW + timedelta(seconds=1)),
            "runner": {"os": "Windows", "device_id": device["device_id"]},
            "task": {"task_id": task_id}, "result": {"status": "healthy"},
            "task_sha256": sha256_hex(canonical_json({"task_id": task_id})),
            "result_sha256": sha256_hex(canonical_json({"status": "healthy"})), "effect": "READ_ONLY",
        }
        att = {
            "schema": RESULT_ATTESTATION_SCHEMA, "device_id": device["device_id"], "device_generation": 1,
            "identity_id": device["current_identity_id"], "task_id": task_id, "source_epoch": SOURCE,
            "policy_epoch": POLICY, "result_sha256": receipt["result_sha256"],
            "receipt_sha256": sha256_hex(canonical_json(receipt)), "previous_receipt_sha256": ZERO_CHAIN,
            "issued_at": z(NOW + timedelta(seconds=1)),
        }
        att["signature_b64"] = self.signer.sign_b64(canonical_json(att))
        first = self.runtime.complete(device=device, binding=binding, task_id=task_id, lease=leased["lease"],
                                      receipt=receipt, result_attestation=att, now=NOW + timedelta(seconds=1))
        self.assertEqual(len(first["recovery_cursor"]), 64)
        self.assertFalse(first["duplicate"])
        device2 = self.store.get("devices", device["device_id"])
        second = self.runtime.complete(device=device2, binding=binding, task_id=task_id, lease=leased["lease"],
                                       receipt=receipt, result_attestation=att, now=NOW + timedelta(seconds=2))
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["recovery_cursor"], second["recovery_cursor"])

    def test_wrong_result_attestation_key_and_malformed_payload_rejected(self):
        self.assertRaisesRegex(ValueError, "JSON_BODY_REQUIRED", _body_json, b"{")
        self.assertRaisesRegex(ValueError, "JSON_OBJECT_REQUIRED", _body_json, b"[]")
        _, _, paired = self.pair()
        device = self.store.get("devices", paired["credential"]["device_id"])
        lease = {
            "schema": EXECUTION_LEASE_SCHEMA, "task_id": "task-x", "device_id": device["device_id"],
            "device_generation": 1, "source_epoch": SOURCE, "policy_epoch": POLICY,
            "lease_token": "x", "leased_at": z(NOW), "expires_at": z(NOW + timedelta(minutes=1)),
        }
        receipt = {"result_sha256": "f" * 64}
        att = {
            "schema": RESULT_ATTESTATION_SCHEMA, "device_id": device["device_id"], "device_generation": 1,
            "identity_id": device["current_identity_id"], "task_id": "task-x", "source_epoch": SOURCE,
            "policy_epoch": POLICY, "result_sha256": "f" * 64,
            "receipt_sha256": sha256_hex(canonical_json(receipt)), "previous_receipt_sha256": ZERO_CHAIN,
            "issued_at": z(NOW),
        }
        att["signature_b64"] = self.other.sign_b64(canonical_json(att))
        with self.assertRaisesRegex(PermissionError, "SIGNATURE_INVALID"):
            self.runtime.complete(device=device, binding=self.binding(paired), task_id="task-x", lease=lease,
                                  receipt=receipt, result_attestation=att, now=NOW)

    def test_source_contract_preserves_fail_closed_and_sets_exact_epochs(self):
        root = Path(__file__).resolve().parents[2]
        pyproject = (root / "windows_federation_plane" / "pyproject.toml").read_text(encoding="utf-8")
        workflow = (root / ".github" / "workflows" / "fuse-windows-relay-cloud-run-v1.yml").read_text(encoding="utf-8")
        source = (root / "windows_federation_plane" / "src" / "federation_windows_plane" / "pairing_service.py").read_text(encoding="utf-8")
        self.assertIn('federation-windows-relay = "federation_windows_plane.pairing_service:main"', pyproject)
        self.assertIn("FUSE_WINDOWS_SOURCE_EPOCH=$GITHUB_SHA", workflow)
        self.assertIn("FUSE_WINDOWS_POLICY_EPOCH=WOAF_TRUST_SPINE_V21", workflow)
        self.assertNotIn('custom_route("/mcp"', source)
        for denied in ("subprocess.run", "os.system", "powershell", "cmd.exe"):
            self.assertNotIn(denied, source.lower())


if __name__ == "__main__":
    unittest.main()
