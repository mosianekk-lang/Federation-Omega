from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from authority_acquisition import (
    AuthorityAcquisitionFabric,
    AuthorityEvidence,
    AuthorityRequirement,
    contains_secret_material,
    digest,
)


class AuthorityAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.fabric = AuthorityAcquisitionFabric(Path(self.temp.name) / "runtime")
        self.github = AuthorityRequirement(
            domain="github_actions",
            stage="C03",
            provider="github-actions",
            purpose="Provider proof",
            required_scopes=("ci_execution", "readback"),
            required_proofs=("provider_identity", "execution", "readback", "persistence"),
            max_age_seconds=86400,
        )
        self.fabric.register_requirement(self.github)
        self.cloud = AuthorityRequirement(
            domain="cloud_run",
            stage="C03",
            provider="google-cloud-run",
            purpose="Live cloud",
            required_scopes=("deploy", "readback", "rollback"),
            required_proofs=("provider_identity", "execution", "readback", "health", "persistence", "rollback"),
            max_age_seconds=86400,
            owner_reserved_actions=("consequential releases",),
            depends_on=("github_actions",),
        )
        self.fabric.register_requirement(self.cloud)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def evidence(self, **overrides):
        body = dict(
            evidence_id="github-1",
            domain="github_actions",
            provider="github-actions",
            provider_native=True,
            state="FRESH_VERIFIED",
            locator="github://repo/actions/1",
            observed_at="2026-08-03T20:00:00Z",
            captured_at="2026-08-03T20:01:00Z",
            scopes=("ci_execution", "readback"),
            proofs={"provider_identity": True, "execution": True, "readback": True, "persistence": True},
            content_sha256="a" * 64,
            owner_confirmations=(),
            evidence={"workflow_run": 1},
        )
        body.update(overrides)
        return AuthorityEvidence(**body)

    def test_provider_native_authority_is_admitted_and_persisted(self) -> None:
        decision = self.fabric.admit_authority(self.evidence(), now="2026-08-03T20:02:00Z")
        self.assertTrue(decision["admitted"])
        self.assertTrue(self.fabric.verify_ledger())
        reloaded = AuthorityAcquisitionFabric(self.fabric.root)
        reloaded.requirements = self.fabric.requirements
        projection = reloaded.project({"cloud_run": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"}, now="2026-08-03T20:02:00Z")
        self.assertEqual(projection["states"]["github_actions"], "FRESH_VERIFIED")
        self.assertEqual(projection["states"]["cloud_run"], "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY")

    def test_alternate_provider_conformance_never_grants_authority(self) -> None:
        result = self.fabric.record_conformance(
            "cloud_run",
            provider="github-actions-reference",
            provider_native=True,
            scopes=("deploy", "readback", "rollback"),
            proofs={name: True for name in self.cloud.required_proofs},
        )
        self.assertEqual(result["status"], "CONFORMANCE_VERIFIED_NOT_AUTHORITY_GRANTED")
        projection = self.fabric.project({"cloud_run": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"}, now="2026-08-03T20:02:00Z")
        self.assertEqual(projection["states"]["cloud_run"], "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY")

    def test_owner_confirmation_and_provider_match_are_required(self) -> None:
        evidence = self.evidence(
            evidence_id="cloud-1",
            domain="cloud_run",
            provider="github-actions-reference",
            scopes=("deploy", "readback", "rollback"),
            proofs={name: True for name in self.cloud.required_proofs},
        )
        decision = self.fabric.admit_authority(evidence, now="2026-08-03T20:02:00Z")
        self.assertFalse(decision["admitted"])
        self.assertIn("PROVIDER_MISMATCH", decision["reasons"])
        self.assertTrue(any(reason.startswith("OWNER_CONFIRMATION_REQUIRED") for reason in decision["reasons"]))

    def test_secret_shaped_material_is_rejected(self) -> None:
        evidence = self.evidence(evidence_id="secret-1", evidence={"password": "password='unsafe-value'"})
        decision = self.fabric.admit_authority(evidence, now="2026-08-03T20:02:00Z")
        self.assertFalse(decision["admitted"])
        self.assertIn("SECRET_MATERIAL_FORBIDDEN", decision["reasons"])
        self.assertTrue(contains_secret_material("client_secret='unsafe-value'"))

    def test_idempotency_and_conflict_detection(self) -> None:
        evidence = self.evidence()
        first = self.fabric.admit_authority(evidence, now="2026-08-03T20:02:00Z")
        second = self.fabric.admit_authority(evidence, now="2026-08-03T20:02:00Z")
        self.assertEqual(first, second)
        changed = self.evidence(content_sha256="b" * 64)
        conflict = self.fabric.admit_authority(changed, now="2026-08-03T20:02:00Z")
        self.assertIn("EVIDENCE_ID_CONFLICT", conflict["reasons"])

    def test_handoff_is_hash_bound_and_contains_no_secret_material(self) -> None:
        handoff = self.fabric.build_handoff("cloud_run", "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY")
        self.assertFalse(handoff["authority_granted"])
        self.assertEqual(handoff["handoff_sha256"], digest({k: v for k, v in handoff.items() if k != "handoff_sha256"}))
        self.assertFalse(contains_secret_material(handoff))
        self.assertTrue((self.fabric.handoff_root / "cloud_run.json").is_file())


if __name__ == "__main__":
    unittest.main()
