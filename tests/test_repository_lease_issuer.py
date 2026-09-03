from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from proofos_omega.repository_lease_issuer import (
    LEASE_SCHEMA,
    SCHEMA,
    build_lease_commit_spec,
    load_policy,
)


def run_git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if process.returncode:
        raise AssertionError(process.stderr)
    return process.stdout.strip()


def lease(source_head: str) -> dict:
    return {
        "schema": LEASE_SCHEMA,
        "state": "ACTIVE",
        "fencing_token": 18,
        "writer_node": "NODE-LEASE-ISSUER-TEST",
        "system": "FDOF/ProofOS",
        "workstream": "lease-issuer-test",
        "transaction_id": "TXN-LEASE-ISSUER-TEST",
        "idempotency_key": "LEASE-ISSUER-TEST:F18",
        "source_head": source_head,
        "scope": ["repository:test"],
        "acquired_at": "2026-09-03T03:36:00+02:00",
        "expires_at": "2026-09-03T04:06:00+02:00",
        "turn_capture_id": "TC-LEASE-ISSUER-TEST",
        "effect": "NONE",
        "authority": "A1_INTERNAL_SOURCE_CI",
    }


def witness(capture_id: str = "TC-LEASE-ISSUER-TEST", verified: bool = True) -> dict:
    return {
        "provider": "FEDERATION_SYNC_BUS_TURN_CAPTURE",
        "capture_id": capture_id,
        "provider_readback_verified": verified,
    }


class RepositoryLeaseIssuerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_policy()

    def make_repo(self) -> tuple[tempfile.TemporaryDirectory, Path, str, str]:
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        run_git(root, "init", "-q")
        run_git(root, "config", "user.name", "Lease Issuer Test")
        run_git(root, "config", "user.email", "lease-issuer-test@example.invalid")
        (root / "seed.txt").write_text("source\n", encoding="utf-8")
        run_git(root, "add", "seed.txt")
        run_git(root, "commit", "-q", "-m", "source")
        head = run_git(root, "rev-parse", "HEAD")
        tree = run_git(root, "show", "-s", "--format=%T", head)
        return td, root, head, tree

    def test_policy_requires_tree_correct_issuer_and_capture_witness(self):
        contract = self.policy["lease_issuer_contract"]
        self.assertEqual("EXACT_DECLARED_SOURCE_HEAD_TREE", contract["commit_tree_source"])
        self.assertEqual("PROVIDER_READBACK_VERIFIED_EXACT_ID", contract["turn_capture_precondition"])
        self.assertEqual(
            "proofos_omega.repository_lease_issuer.build_lease_commit_spec",
            contract["canonical_issuer"],
        )

    def test_commit_spec_uses_declared_source_head_tree_not_predecessor_tree(self):
        td, root, head, tree = self.make_repo()
        try:
            spec = build_lease_commit_spec(
                root,
                lease(head),
                predecessor_lease_sha="2" * 40,
                turn_capture_witness=witness(),
                policy=self.policy,
            )
            self.assertEqual(SCHEMA, spec["schema"])
            self.assertEqual(head, spec["source_head"])
            self.assertEqual(tree, spec["tree_sha"])
            self.assertEqual("2" * 40, spec["parent_sha"])
            self.assertTrue(spec["message"].startswith(LEASE_SCHEMA + "\n"))
            self.assertFalse(spec["provider_effect_authorized"])
        finally:
            td.cleanup()

    def test_capture_id_mismatch_fails_closed_before_commit_spec(self):
        td, root, head, _ = self.make_repo()
        try:
            with self.assertRaisesRegex(ValueError, "TURN_CAPTURE_ID_MISMATCH"):
                build_lease_commit_spec(
                    root,
                    lease(head),
                    predecessor_lease_sha="2" * 40,
                    turn_capture_witness=witness("TC-OTHER"),
                    policy=self.policy,
                )
        finally:
            td.cleanup()

    def test_unverified_capture_fails_closed_before_commit_spec(self):
        td, root, head, _ = self.make_repo()
        try:
            with self.assertRaisesRegex(ValueError, "TURN_CAPTURE_REFERENCE_UNVERIFIED"):
                build_lease_commit_spec(
                    root,
                    lease(head),
                    predecessor_lease_sha="2" * 40,
                    turn_capture_witness=witness(verified=False),
                    policy=self.policy,
                )
        finally:
            td.cleanup()

    def test_wrong_turn_capture_provider_fails_closed(self):
        td, root, head, _ = self.make_repo()
        try:
            bad = witness()
            bad["provider"] = "UNVERIFIED_OTHER_LEDGER"
            with self.assertRaisesRegex(ValueError, "TURN_CAPTURE_PROVIDER_MISMATCH"):
                build_lease_commit_spec(
                    root,
                    lease(head),
                    predecessor_lease_sha="2" * 40,
                    turn_capture_witness=bad,
                    policy=self.policy,
                )
        finally:
            td.cleanup()

    def test_non_none_effect_is_rejected(self):
        td, root, head, _ = self.make_repo()
        try:
            payload = lease(head)
            payload["effect"] = "WRITE"
            with self.assertRaisesRegex(ValueError, "LEASE_EFFECT_SCOPE_INVALID"):
                build_lease_commit_spec(
                    root,
                    payload,
                    predecessor_lease_sha="2" * 40,
                    turn_capture_witness=witness(),
                    policy=self.policy,
                )
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
