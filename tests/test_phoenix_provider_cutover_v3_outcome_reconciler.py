from __future__ import annotations

import io
import json
import tarfile
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from phoenix.provider_cutover_outcome_reconciler import (
    GitHubReadOnlyAPI,
    ReconciliationError,
    archive_inventory,
    authority_preflight,
    blob_sha1,
    canonical_sha256,
    reconcile,
    sha256_file,
    write_atomic,
)

OWNER = "mosianekk-lang"
LEGACY = "Federation-Omega"
CORE = "Federation-Omega-Core"
OPS = "Federation-Omega-Ops"
NOW = datetime(2026, 8, 5, 0, 5, tzinfo=timezone.utc)


def make_archive(path: Path, files: dict[str, tuple[bytes, int]]) -> None:
    with tarfile.open(path, "w:gz") as bundle:
        for name, (content, mode) in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = mode
            info.mtime = 0
            bundle.addfile(info, io.BytesIO(content))


def provider_tree(files: dict[str, tuple[bytes, int]]) -> list[dict]:
    return [
        {
            "path": name,
            "type": "blob",
            "mode": "100755" if mode & 0o100 else "100644",
            "sha": blob_sha1(content),
            "size": len(content),
        }
        for name, (content, mode) in sorted(files.items())
    ]


class FakeReadOnlyAPI:
    def __init__(self, core_files, ops_files):
        self.calls: list[str] = []
        self.core_sha = "c" * 40
        self.ops_sha = "d" * 40
        common = {"permissions": {"admin": True}, "default_branch": "main"}
        self.responses = {
            "/user": {"login": OWNER},
            f"/repos/{OWNER}/{LEGACY}": {
                **common,
                "full_name": f"{OWNER}/{LEGACY}",
                "private": False,
                "is_template": False,
                "archived": False,
            },
            f"/repos/{OWNER}/{LEGACY}/actions/permissions": {"enabled": False},
            f"/repos/{OWNER}/{CORE}": {
                **common,
                "full_name": f"{OWNER}/{CORE}",
                "private": True,
            },
            f"/repos/{OWNER}/{OPS}": {
                **common,
                "full_name": f"{OWNER}/{OPS}",
                "private": True,
            },
            f"/repos/{OWNER}/{CORE}/actions/permissions": {"enabled": False},
            f"/repos/{OWNER}/{OPS}/actions/permissions": {"enabled": False},
            f"/repos/{OWNER}/{CORE}/actions/permissions/workflow": {
                "default_workflow_permissions": "read",
                "can_approve_pull_request_reviews": False,
            },
            f"/repos/{OWNER}/{OPS}/actions/permissions/workflow": {
                "default_workflow_permissions": "read",
                "can_approve_pull_request_reviews": False,
            },
            f"/repos/{OWNER}/{CORE}/git/ref/heads/main": {
                "object": {"sha": self.core_sha}
            },
            f"/repos/{OWNER}/{OPS}/git/ref/heads/main": {
                "object": {"sha": self.ops_sha}
            },
            f"/repos/{OWNER}/{CORE}/git/trees/{self.core_sha}?recursive=1": {
                "truncated": False,
                "tree": provider_tree(core_files),
            },
            f"/repos/{OWNER}/{OPS}/git/trees/{self.ops_sha}?recursive=1": {
                "truncated": False,
                "tree": provider_tree(ops_files),
            },
            f"/repos/{OWNER}/{CORE}/rulesets?includes_parents=false": [
                {"enforcement": "active", "target": "branch"}
            ],
            f"/repos/{OWNER}/{OPS}/rulesets?includes_parents=false": [
                {"enforcement": "active", "target": "branch"}
            ],
        }
        self.optional_responses = {
            f"/repos/{OWNER}/{CORE}/contents/.github/workflows?ref=main": None,
            f"/repos/{OWNER}/{OPS}/contents/.github/workflows?ref=main": None,
        }

    def get(self, path: str):
        self.calls.append(path)
        if path not in self.responses:
            raise AssertionError(f"unexpected GET {path}")
        return self.responses[path]

    def optional(self, path: str):
        self.calls.append(path)
        if path in self.optional_responses:
            return self.optional_responses[path]
        return self.get(path)


class ProviderOutcomeReconcilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.core_files = {
            "README.md": (b"# Core\n", 0o644),
            "bin/run.sh": (b"#!/bin/sh\necho core\n", 0o755),
        }
        self.ops_files = {
            "README.md": (b"# Ops\n", 0o644),
            "provider_cutover.py": (b"print('ops')\n", 0o755),
        }
        self.core_archive = self.root / "core.tar.gz"
        self.ops_archive = self.root / "ops.tar.gz"
        make_archive(self.core_archive, self.core_files)
        make_archive(self.ops_archive, self.ops_files)
        self.api = FakeReadOnlyAPI(self.core_files, self.ops_files)

    def tearDown(self):
        self.temp.cleanup()

    def perform_reconciliation(self):
        preflight = authority_preflight(
            self.api, owner=OWNER, legacy=LEGACY, requested="user"
        )
        return reconcile(
            self.api,
            owner=OWNER,
            legacy=LEGACY,
            core=CORE,
            ops=OPS,
            core_archive=self.core_archive,
            ops_archive=self.ops_archive,
            expected_core_sha256=sha256_file(self.core_archive),
            expected_ops_sha256=sha256_file(self.ops_archive),
            preflight=preflight,
            observed_at=NOW,
        )

    def test_exact_readback_reconstructs_compatible_receipt(self):
        receipt = self.perform_reconciliation()
        self.assertEqual("FEDOMEGA-PHOENIX-PROVIDER-CUTOVER-3", receipt["schema"])
        self.assertEqual("VERIFIED", receipt["status"])
        self.assertEqual(
            "READ_ONLY_PROVIDER_OUTCOME_RECONCILIATION", receipt["mode"]
        )
        self.assertTrue(receipt["core_readback"]["verified"])
        self.assertTrue(receipt["ops_readback"]["verified"])
        self.assertFalse(receipt["provider_apply_replayed"])
        self.assertFalse(receipt["provider_mutation_performed"])
        self.assertFalse(receipt["automatic_retry_performed"])
        claimed = receipt["receipt_sha256"]
        body = dict(receipt)
        body.pop("receipt_sha256")
        self.assertEqual(canonical_sha256(body), claimed)

    def test_changed_provider_blob_fails_closed(self):
        path = f"/repos/{OWNER}/{CORE}/git/trees/{self.api.core_sha}?recursive=1"
        self.api.responses[path]["tree"][0]["sha"] = "e" * 40
        with self.assertRaisesRegex(ReconciliationError, "content mismatch"):
            self.perform_reconciliation()

    def test_unexpected_provider_file_fails_closed(self):
        path = f"/repos/{OWNER}/{OPS}/git/trees/{self.api.ops_sha}?recursive=1"
        self.api.responses[path]["tree"].append(
            {
                "path": "unexpected.txt",
                "type": "blob",
                "mode": "100644",
                "sha": blob_sha1(b"x"),
                "size": 1,
            }
        )
        with self.assertRaisesRegex(ReconciliationError, "unexpected="):
            self.perform_reconciliation()

    def test_enabled_actions_fail_closed(self):
        self.api.responses[f"/repos/{OWNER}/{CORE}/actions/permissions"] = {
            "enabled": True
        }
        with self.assertRaisesRegex(
            ReconciliationError, "actions_disabled_at_bootstrap"
        ):
            self.perform_reconciliation()

    def test_missing_active_ruleset_fails_closed(self):
        self.api.responses[
            f"/repos/{OWNER}/{OPS}/rulesets?includes_parents=false"
        ] = []
        with self.assertRaisesRegex(ReconciliationError, "active_branch_ruleset"):
            self.perform_reconciliation()

    def test_wrong_archive_digest_fails_before_target_readback(self):
        preflight = authority_preflight(
            self.api, owner=OWNER, legacy=LEGACY, requested="user"
        )
        calls_before = list(self.api.calls)
        with self.assertRaisesRegex(ReconciliationError, "SHA-256 mismatch"):
            reconcile(
                self.api,
                owner=OWNER,
                legacy=LEGACY,
                core=CORE,
                ops=OPS,
                core_archive=self.core_archive,
                ops_archive=self.ops_archive,
                expected_core_sha256="0" * 64,
                expected_ops_sha256=sha256_file(self.ops_archive),
                preflight=preflight,
                observed_at=NOW,
            )
        self.assertEqual(calls_before, self.api.calls)

    def test_unsafe_archive_path_is_rejected(self):
        unsafe = self.root / "unsafe.tar.gz"
        make_archive(unsafe, {"../escape": (b"x", 0o644)})
        with self.assertRaisesRegex(
            ReconciliationError, "unsafe archive/provider path"
        ):
            archive_inventory(unsafe, "Core")

    def test_atomic_receipt_write_preserves_integrity(self):
        receipt = self.perform_reconciliation()
        path = self.root / "state" / "provider-receipt.json"
        write_atomic(path, receipt)
        self.assertEqual(receipt, json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual(0o600, path.stat().st_mode & 0o777)
        self.assertFalse(any(path.parent.glob(f".{path.name}.*")))

    def test_client_surface_exposes_no_write_method(self):
        methods = {
            name
            for name in dir(GitHubReadOnlyAPI)
            if callable(getattr(GitHubReadOnlyAPI, name))
        }
        for prohibited in ("request", "post", "patch", "put", "delete"):
            self.assertNotIn(prohibited, methods)


if __name__ == "__main__":
    unittest.main()
