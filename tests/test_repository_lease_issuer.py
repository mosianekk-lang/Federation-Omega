from __future__ import annotations

import json
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


def lease(source_head: str, token: int = 18) -> dict:
    return {
        "schema": LEASE_SCHEMA,
        "state": "ACTIVE",
        "fencing_token": token,
        "writer_node": "NODE-LEASE-ISSUER-TEST",
        "system": "FDOF/ProofOS",
        "workstream": "lease-issuer-test",
        "transaction_id": "TXN-LEASE-ISSUER-TEST",
        "idempotency_key": f"LEASE-ISSUER-TEST:F{token}",
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


def predecessor_commit(root: Path, source_head: str, *, state: str = "RELEASED", token: int = 17) -> str:
    tree = run_git(root, "show", "-s", "--format=%T", source_head)
    payload = {
        "schema": LEASE_SCHEMA,
        "state": state,
        "fencing_token": token,
        "source_head": source_head,
        "effect": "NONE",
    }
    message = LEASE_SCHEMA + "\n" + json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return run_git(root, "commit-tree", tree, "-p", source_head, "-m", message)


def publish_lock(root: Path, commit_sha: str) -> None:
    run_git(
        root,
        "push",
        "-q",
        "--force",
        "origin",
        f"{commit_sha}:refs/heads/locks/fdof-repository-critical-section",
    )


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
        provider = root / "provider.git"
        run_git(root, "init", "--bare", "-q", str(provider))
        run_git(root, "remote", "add", "origin", str(provider))
        return td, root, head, tree

    def test_policy_requires_tree_capture_and_explicit_terminal_predecessor(self):
        contract = self.policy["lease_issuer_contract"]
        self.assertEqual("EXACT_DECLARED_SOURCE_HEAD_TREE", contract["commit_tree_source"])
        self.assertEqual("PROVIDER_READBACK_VERIFIED_EXACT_ID", contract["turn_capture_precondition"])
        self.assertEqual("EXPLICIT_RELEASED_OR_ABORTED_PROVIDER_READBACK", contract["predecessor_terminal_precondition"])
        self.assertTrue(contract["fail_closed_on_nonterminal_predecessor"])
        self.assertEqual("GIT_LS_REMOTE_EXACT_REF_MATCH", contract["provider_current_lock_ref_precondition"])
        self.assertTrue(contract["fail_closed_on_stale_terminal_predecessor"])
        self.assertEqual(
            "proofos_omega.repository_lease_issuer.build_lease_commit_spec",
            contract["canonical_issuer"],
        )

    def test_commit_spec_uses_declared_source_head_tree_and_terminal_predecessor(self):
        td, root, head, tree = self.make_repo()
        try:
            predecessor = predecessor_commit(root, head, state="RELEASED", token=17)
            publish_lock(root, predecessor)
            spec = build_lease_commit_spec(
                root,
                lease(head, token=18),
                predecessor_lease_sha=predecessor,
                turn_capture_witness=witness(),
                policy=self.policy,
            )
            self.assertEqual(SCHEMA, spec["schema"])
            self.assertEqual(head, spec["source_head"])
            self.assertEqual(tree, spec["tree_sha"])
            self.assertEqual(predecessor, spec["parent_sha"])
            self.assertEqual("RELEASED", spec["predecessor_state"])
            self.assertEqual(17, spec["predecessor_fencing_token"])
            self.assertEqual(predecessor, spec["provider_lock_ref_sha"])
            self.assertTrue(spec["message"].startswith(LEASE_SCHEMA + "\n"))
            self.assertFalse(spec["provider_effect_authorized"])
        finally:
            td.cleanup()

    def test_aborted_predecessor_is_terminal(self):
        td, root, head, _ = self.make_repo()
        try:
            predecessor = predecessor_commit(root, head, state="ABORTED", token=17)
            publish_lock(root, predecessor)
            spec = build_lease_commit_spec(
                root,
                lease(head, token=18),
                predecessor_lease_sha=predecessor,
                turn_capture_witness=witness(),
                policy=self.policy,
            )
            self.assertEqual("ABORTED", spec["predecessor_state"])
        finally:
            td.cleanup()

    def test_active_predecessor_fails_even_if_wall_clock_expired(self):
        td, root, head, _ = self.make_repo()
        try:
            predecessor = predecessor_commit(root, head, state="ACTIVE", token=17)
            publish_lock(root, predecessor)
            with self.assertRaisesRegex(ValueError, "PREDECESSOR_LEASE_NOT_TERMINAL"):
                build_lease_commit_spec(
                    root,
                    lease(head, token=18),
                    predecessor_lease_sha=predecessor,
                    turn_capture_witness=witness(),
                    policy=self.policy,
                )
        finally:
            td.cleanup()

    def test_stale_terminal_predecessor_fails_when_provider_ref_is_newer_active(self):
        td, root, head, _ = self.make_repo()
        try:
            stale_terminal = predecessor_commit(root, head, state="RELEASED", token=17)
            current_active = predecessor_commit(root, head, state="ACTIVE", token=18)
            publish_lock(root, current_active)
            with self.assertRaisesRegex(ValueError, "PREDECESSOR_LEASE_NOT_CURRENT_LOCK_REF"):
                build_lease_commit_spec(
                    root,
                    lease(head, token=19),
                    predecessor_lease_sha=stale_terminal,
                    turn_capture_witness=witness(),
                    policy=self.policy,
                )
        finally:
            td.cleanup()

    def test_unresolved_provider_lock_ref_fails_closed(self):
        td, root, head, _ = self.make_repo()
        try:
            predecessor = predecessor_commit(root, head, state="RELEASED", token=17)
            with self.assertRaisesRegex(ValueError, "CURRENT_LOCK_REF_UNRESOLVED"):
                build_lease_commit_spec(
                    root,
                    lease(head, token=18),
                    predecessor_lease_sha=predecessor,
                    turn_capture_witness=witness(),
                    policy=self.policy,
                )
        finally:
            td.cleanup()

    def test_fencing_token_must_advance_past_terminal_predecessor(self):
        td, root, head, _ = self.make_repo()
        try:
            predecessor = predecessor_commit(root, head, state="RELEASED", token=18)
            publish_lock(root, predecessor)
            with self.assertRaisesRegex(ValueError, "LEASE_FENCING_TOKEN_NOT_MONOTONIC"):
                build_lease_commit_spec(
                    root,
                    lease(head, token=18),
                    predecessor_lease_sha=predecessor,
                    turn_capture_witness=witness(),
                    policy=self.policy,
                )
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
