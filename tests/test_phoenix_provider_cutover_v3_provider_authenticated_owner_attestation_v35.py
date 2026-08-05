from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tarfile
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PACKET_PATH = ROOT / "phoenix" / "ops-template" / "owner_sealed_packet.py"
PACKET_SPEC = importlib.util.spec_from_file_location(
    "owner_sealed_packet_v35", PACKET_PATH
)
assert PACKET_SPEC and PACKET_SPEC.loader
PACKET = importlib.util.module_from_spec(PACKET_SPEC)
sys.modules[PACKET_SPEC.name] = PACKET
PACKET_SPEC.loader.exec_module(PACKET)

CUSTODY_PATH = ROOT / "phoenix" / "ops-template" / "owner_custody_ceremony.py"
CUSTODY_SPEC = importlib.util.spec_from_file_location(
    "owner_custody_ceremony_v35", CUSTODY_PATH
)
assert CUSTODY_SPEC and CUSTODY_SPEC.loader
CUSTODY = importlib.util.module_from_spec(CUSTODY_SPEC)
sys.modules[CUSTODY_SPEC.name] = CUSTODY
CUSTODY_SPEC.loader.exec_module(CUSTODY)

ATTEST_PATH = ROOT / "phoenix" / "ops-template" / "owner_custody_attestation.py"
ATTEST_SPEC = importlib.util.spec_from_file_location(
    "owner_custody_attestation_v35", ATTEST_PATH
)
assert ATTEST_SPEC and ATTEST_SPEC.loader
ATTEST = importlib.util.module_from_spec(ATTEST_SPEC)
sys.modules[ATTEST_SPEC.name] = ATTEST
ATTEST_SPEC.loader.exec_module(ATTEST)

PROVIDER_PATH = (
    ROOT / "phoenix" / "ops-template" / "provider_authenticated_owner_attestation.py"
)
PROVIDER_SPEC = importlib.util.spec_from_file_location(
    "provider_authenticated_owner_attestation_v35", PROVIDER_PATH
)
assert PROVIDER_SPEC and PROVIDER_SPEC.loader
PROVIDER = importlib.util.module_from_spec(PROVIDER_SPEC)
sys.modules[PROVIDER_SPEC.name] = PROVIDER
PROVIDER_SPEC.loader.exec_module(PROVIDER)

CHECKPOINT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_provider_authenticated_owner_attestation_checkpoint_v35.json"
)
PROJECTION = (
    ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v35.json"
)
CONTRACT = (
    ROOT
    / "phoenix"
    / "ops-template"
    / "governance"
    / "PROVIDER_AUTHENTICATED_OWNER_ATTESTATION_CONTRACT.json"
)
POLICY = ROOT / "phoenix" / "export_policy.json"


def build_archive(path: Path, *, target: str) -> None:
    manifest_name = (
        "PHOENIX_CORE_MANIFEST.json"
        if target == "Federation-Omega-Core"
        else "PHOENIX_OPS_MANIFEST.json"
    )
    invariants = (
        {
            "workflow_count": 0,
            "runtime_state_count": 0,
            "migration_control_test_count": 0,
            "secret_marker_count": 0,
        }
        if target == "Federation-Omega-Core"
        else {
            "active_workflow_count": 0,
            "legacy_workflow_count": 0,
            "long_lived_credentials": 0,
        }
    )
    files = {
        manifest_name: json.dumps(
            {"target": target, "invariants": invariants},
            sort_keys=True,
            separators=(",", ":"),
        ).encode(),
        "README.md": target.encode(),
    }
    with tarfile.open(path, "w:gz") as archive:
        for name, content in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))


class ProviderAuthenticatedOwnerAttestationV35Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        core = self.root / "Federation-Omega-Core.tar.gz"
        ops = self.root / "Federation-Omega-Ops.tar.gz"
        build_archive(core, target="Federation-Omega-Core")
        build_archive(ops, target="Federation-Omega-Ops")

        self.packet = self.root / "owner-packet.json"
        PACKET.build_packet_candidate(
            core_archive=core,
            ops_archive=ops,
            output=self.packet,
            metadata={
                "source_repository": "mosianekk-lang/Federation-Omega",
                "source_sha": "a" * 40,
                "export_policy_version": "test",
                "core": {
                    "sha256": PACKET.sha256_file(core),
                    "size": core.stat().st_size,
                },
                "ops": {
                    "sha256": PACKET.sha256_file(ops),
                    "size": ops.stat().st_size,
                },
            },
        )

        fingerprint = hashlib.sha256(
            b"owner-controlled-offline-destination"
        ).hexdigest()
        manifest = self.root / "manifest.json"
        CUSTODY.prepare_manifest(
            packet_path=self.packet,
            output=manifest,
            owner_reference="OWNER-KKM",
            destination_label="OWNER-OFFLINE-VAULT",
            destination_fingerprint=fingerprint,
        )
        vault = self.root / "vault"
        vault.mkdir()
        self.copied_packet = vault / "owner-packet.json"
        self.custody_receipt = self.root / "custody-receipt.json"
        CUSTODY.execute_local_copy(
            packet_path=self.packet,
            manifest_path=manifest,
            destination=self.copied_packet,
            receipt_output=self.custody_receipt,
            confirmation=CUSTODY.CONFIRMATION,
        )

        self.issued = datetime(2026, 8, 5, 7, 0, tzinfo=timezone.utc)
        self.expires = self.issued + timedelta(minutes=10)
        self.challenge = self.root / "challenge.json"
        ATTEST.prepare_challenge(
            custody_receipt_path=self.custody_receipt,
            copied_packet=self.copied_packet,
            output=self.challenge,
            execution_route="OWNER_ONLY_SEALED_PACKET",
            issued_at=self.issued,
            expires_at=self.expires,
        )
        self.attestation = self.root / "attestation.json"
        ATTEST.create_attestation(
            challenge_path=self.challenge,
            custody_receipt_path=self.custody_receipt,
            copied_packet=self.copied_packet,
            output=self.attestation,
            confirmation=ATTEST.CONFIRMATION,
            attested_at=self.issued + timedelta(minutes=1),
        )

        self.repository = "mosianekk-lang/Federation-Omega"
        self.owner = "mosianekk-lang"
        self.comment_id = 987654321
        self.comment_created = self.issued + timedelta(minutes=2)
        self.captured = self.issued + timedelta(minutes=3)
        self.message = PROVIDER.prepare_provider_message(
            attestation_path=self.attestation,
            challenge_path=self.challenge,
            custody_receipt_path=self.custody_receipt,
            copied_packet=self.copied_packet,
            now=self.captured,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fake_fetch(self, url: str, headers: dict[str, str]) -> dict[str, object]:
        self.assertEqual("application/vnd.github+json", headers["Accept"])
        self.assertNotIn("Authorization", headers)
        if url == "https://api.github.com/user":
            return {"login": self.owner, "id": 261966700, "type": "User"}
        if url == f"https://api.github.com/repos/{self.repository}":
            return {
                "full_name": self.repository,
                "private": False,
                "owner": {"login": self.owner, "id": 261966700},
            }
        if url == (
            f"https://api.github.com/repos/{self.repository}"
            f"/issues/comments/{self.comment_id}"
        ):
            timestamp = self.comment_created.isoformat().replace("+00:00", "Z")
            return {
                "id": self.comment_id,
                "body": self.message,
                "user": {"login": self.owner, "id": 261966700},
                "author_association": "OWNER",
                "created_at": timestamp,
                "updated_at": timestamp,
                "issue_url": (
                    f"https://api.github.com/repos/{self.repository}/issues/279"
                ),
                "html_url": (
                    f"https://github.com/{self.repository}/issues/279"
                    f"#issuecomment-{self.comment_id}"
                ),
            }
        raise AssertionError(url)

    def capture(self) -> Path:
        output = self.root / "provider-evidence.json"
        PROVIDER.capture_github_readback(
            repository_full_name=self.repository,
            comment_id=self.comment_id,
            owner_login=self.owner,
            output=output,
            captured_at=self.captured,
            fetch_json=self.fake_fetch,
        )
        return output

    def verify(self, evidence: Path, *, now: datetime | None = None):
        return PROVIDER.verify_github_readback(
            evidence,
            attestation_path=self.attestation,
            challenge_path=self.challenge,
            custody_receipt_path=self.custody_receipt,
            copied_packet=self.copied_packet,
            repository_full_name=self.repository,
            owner_login=self.owner,
            now=now or self.captured,
        )

    def test_message_is_deterministic_low_disclosure_and_non_authoritative(self):
        second = PROVIDER.prepare_provider_message(
            attestation_path=self.attestation,
            challenge_path=self.challenge,
            custody_receipt_path=self.custody_receipt,
            copied_packet=self.copied_packet,
            now=self.captured,
        )
        self.assertEqual(self.message, second)
        self.assertIn("challenge_sha256=", self.message)
        self.assertIn("attestation_sha256=", self.message)
        self.assertIn("authorization=NOT_GRANTED", self.message)
        self.assertIn("provider_apply=NOT_PERFORMED", self.message)
        self.assertNotIn("OWNER-OFFLINE-VAULT", self.message)
        self.assertNotIn("OWNER-KKM", self.message)

    def test_mock_readback_and_receipt_never_claim_owner_identity(self):
        evidence = self.capture()
        verified = self.verify(evidence)
        self.assertEqual("MOCK_CONFORMANCE", verified["capture_mode"])
        self.assertFalse(verified["owner_identity_authenticity_proven"])
        self.assertFalse(verified["owner_attestation_provider_authenticated"])
        self.assertFalse(verified["owner_authorization_present"])
        self.assertFalse(verified["provider_apply_performed"])

        receipt = self.root / "identity-receipt.json"
        created = PROVIDER.write_identity_receipt(
            receipt,
            evidence_path=evidence,
            attestation_path=self.attestation,
            challenge_path=self.challenge,
            custody_receipt_path=self.custody_receipt,
            copied_packet=self.copied_packet,
            repository_full_name=self.repository,
            owner_login=self.owner,
            now=self.captured,
        )
        self.assertEqual(
            "MOCK_PROVIDER_CONFORMANCE_VERIFIED_NO_OWNER_IDENTITY_CLAIM",
            created["status"],
        )
        self.assertFalse(created["owner_identity_authenticity_proven"])
        self.assertTrue(created["owner_authorization_required"])

    def test_actor_body_edit_freshness_and_mode_forgery_fail_closed(self):
        evidence = self.capture()
        base = json.loads(evidence.read_text())

        cases = []
        actor = json.loads(json.dumps(base))
        actor["comment"]["user"]["login"] = "another-owner"
        cases.append(actor)

        body = json.loads(json.dumps(base))
        body["comment"]["body"] = "different"
        cases.append(body)

        edited = json.loads(json.dumps(base))
        edited["comment"]["updated_at"] = (
            self.comment_created + timedelta(seconds=1)
        ).isoformat().replace("+00:00", "Z")
        cases.append(edited)

        for index, payload in enumerate(cases):
            path = self.root / f"bad-{index}.json"
            payload.pop("evidence_sha256", None)
            payload["evidence_sha256"] = PROVIDER.sha256_bytes(
                PROVIDER.canonical_bytes(payload)
            )
            path.write_bytes(PROVIDER.canonical_bytes(payload) + b"\n")
            with self.assertRaises(
                PROVIDER.ProviderAuthenticatedOwnerAttestationError
            ):
                self.verify(path)

        with self.assertRaises(
            PROVIDER.ProviderAuthenticatedOwnerAttestationError
        ):
            self.verify(
                evidence,
                now=self.captured + timedelta(minutes=6),
            )

        forged = json.loads(evidence.read_text())
        forged["capture_mode"] = "PROVIDER_NATIVE"
        forged["status"] = (
            "PROVIDER_NATIVE_GET_READBACK_CAPTURED_VERIFICATION_REQUIRED"
        )
        forged.pop("evidence_sha256", None)
        forged["evidence_sha256"] = PROVIDER.sha256_bytes(
            PROVIDER.canonical_bytes(forged)
        )
        forged_path = self.root / "forged-native.json"
        forged_path.write_bytes(PROVIDER.canonical_bytes(forged) + b"\n")
        result = self.verify(forged_path)
        self.assertEqual(
            "PROVIDER_NATIVE_EVIDENCE_CONTENT_VERIFIED_LIVE_TRANSPORT_REPLAY_REQUIRED",
            result["status"],
        )
        self.assertFalse(result["owner_identity_authenticity_proven"])
        with self.assertRaises(
            PROVIDER.ProviderAuthenticatedOwnerAttestationError
        ):
            PROVIDER.verify_github_readback(
                evidence,
                attestation_path=self.attestation,
                challenge_path=self.challenge,
                custody_receipt_path=self.custody_receipt,
                copied_packet=self.copied_packet,
                repository_full_name=self.repository,
                owner_login=self.owner,
                now=self.captured,
                _provider_native_transport=True,
            )

    def test_contract_policy_checkpoint_projection_and_truth_boundary(self):
        contract = json.loads(CONTRACT.read_text())
        policy = json.loads(POLICY.read_text())
        self.assertEqual("PREPARED_NOT_EXECUTED_OWNER_RESERVED", contract["status"])
        self.assertFalse(contract["controls"]["provider_mutation_allowed"])
        self.assertFalse(contract["controls"]["attestation_posting_performed"])
        self.assertFalse(contract["controls"]["mock_provider_can_prove_owner_identity"])
        self.assertFalse(contract["controls"]["owner_authorization_created"])
        self.assertFalse(contract["controls"]["provider_apply_performed"])
        self.assertIn(
            "provider_authenticated_owner_attestation.py",
            policy["ops"]["required_files"],
        )
        self.assertIn(
            "governance/PROVIDER_AUTHENTICATED_OWNER_ATTESTATION_CONTRACT.json",
            policy["ops"]["required_files"],
        )

        checkpoint = json.loads(CHECKPOINT.read_text())
        projection = json.loads(PROJECTION.read_text())
        for payload, field in (
            (checkpoint, "checkpoint_sha256"),
            (projection, "projection_sha256"),
        ):
            body = dict(payload)
            claimed = body.pop(field)
            calculated = hashlib.sha256(
                json.dumps(
                    body, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            self.assertEqual(claimed, calculated)

        self.assertEqual(
            [f"C{i:02d}" for i in range(1, 16)],
            projection["dependency_order"],
        )
        self.assertTrue(projection["service_enabled_platform_first"])
        self.assertTrue(projection["self_service_saas_held"])
        self.assertEqual(0, projection["verified_live_revenue_events"])
        self.assertFalse(projection["full_commercial_maturity"])
        self.assertFalse(
            checkpoint["attestation_truth"]["owner_identity_authenticity_proven"]
        )
        self.assertFalse(
            checkpoint["commercial_truth"]["full_commercial_maturity"]
        )


if __name__ == "__main__":
    unittest.main()
