from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "phoenix" / "ops-template" / "provider_authority_probe.py"
SPEC = importlib.util.spec_from_file_location("provider_authority_probe_test", PATH)
assert SPEC and SPEC.loader
PROBE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PROBE
SPEC.loader.exec_module(PROBE)
NOW = datetime(2026, 8, 5, 0, 0, tzinfo=timezone.utc)
HEAD = "a" * 40


class FakeClient:
    def __init__(
        self,
        *,
        mode="installation",
        selection="all",
        permissions=None,
        login="mosianekk-lang",
    ):
        self.mode = mode
        self.selection = selection
        self.permissions = permissions or {
            "administration": "write",
            "contents": "write",
            "metadata": "read",
        }
        self.login = login

    def get(self, path, allow=(200,)):
        if path == "/user":
            if self.mode == "user":
                return 200, {"login": self.login}
            raise PROBE.AuthorityProbeError(
                "GitHub GET /user failed with 403: installation token"
            )
        if path == "/installation":
            return 200, {
                "id": 149462480,
                "account": {"login": self.login},
                "repository_selection": self.selection,
                "permissions": self.permissions,
            }
        if path == "/repos/mosianekk-lang/Federation-Omega":
            return 200, {
                "permissions": {"admin": True},
                "owner": {"login": "mosianekk-lang"},
            }
        if path.endswith("/actions/permissions"):
            return 200, {"enabled": True}
        if "rulesets?includes_parents=false" in path:
            return 200, []
        if path.endswith("/git/ref/heads/main"):
            return 200, {"object": {"sha": HEAD}}
        raise AssertionError(path)

    def optional(self, path):
        if path.endswith("/Federation-Omega-Core") or path.endswith(
            "/Federation-Omega-Ops"
        ):
            return None
        raise AssertionError(path)


class AuthorityProbeTests(unittest.TestCase):
    def test_missing_private_credential_is_explicit(self):
        result = PROBE.missing_authority_receipt(now=NOW)
        self.assertEqual(
            "AUTHORITY_UNAVAILABLE_NO_PRIVATE_CREDENTIAL", result["status"]
        )
        self.assertFalse(result["credential_value_recorded"])
        self.assertFalse(result["provider_mutation_performed"])

    def test_user_scoped_owner_admin_is_ready_without_mutation(self):
        result = PROBE.probe_authority(FakeClient(mode="user"), now=NOW)
        self.assertEqual(
            "AUTHORITY_READY_FOR_FRESH_OWNER_AUTHORISED_APPLY", result["status"]
        )
        self.assertEqual("USER_SCOPED", result["route"]["authority_mode"])
        self.assertEqual("/user/repos", result["route"]["repository_creation_endpoint"])
        self.assertFalse(result["provider_mutation_performed"])

    def test_installation_all_repositories_with_write_permissions_is_ready(self):
        result = PROBE.probe_authority(FakeClient(), now=NOW)
        self.assertEqual(
            "AUTHORITY_READY_FOR_FRESH_OWNER_AUTHORISED_APPLY", result["status"]
        )
        self.assertEqual("INSTALLATION_TEMPLATE", result["route"]["authority_mode"])
        self.assertTrue(result["checks"]["all_repositories_selection"])

    def test_selected_repository_installation_is_blocked_exactly(self):
        result = PROBE.probe_authority(FakeClient(selection="selected"), now=NOW)
        self.assertEqual(
            "AUTHORITY_BLOCKED_EXACT_REMEDIATION_REQUIRED", result["status"]
        )
        self.assertIn(
            "INSTALLATION_SELECTED_REPOSITORIES_ONLY", result["blockers"]
        )
        self.assertFalse(result["provider_mutation_performed"])

    def test_missing_administration_write_is_blocked(self):
        result = PROBE.probe_authority(
            FakeClient(
                permissions={
                    "administration": "read",
                    "contents": "write",
                    "metadata": "read",
                }
            ),
            now=NOW,
        )
        self.assertIn(
            "INSTALLATION_ADMINISTRATION_WRITE_MISSING", result["blockers"]
        )
        self.assertEqual(
            "AUTHORITY_BLOCKED_EXACT_REMEDIATION_REQUIRED", result["status"]
        )

    def test_wrong_account_is_blocked(self):
        result = PROBE.probe_authority(FakeClient(login="other-owner"), now=NOW)
        self.assertIn("AUTHENTICATED_ACCOUNT_MISMATCH", result["blockers"])
        self.assertTrue(result["owner_authorization_still_required"])

    def test_receipt_is_hash_bound_and_contains_no_credential(self):
        result = PROBE.probe_authority(FakeClient(), now=NOW)
        claimed = result.pop("receipt_sha256")
        self.assertEqual(claimed, PROBE.canonical_sha256(result))
        text = str(result)
        self.assertNotIn("ghp_", text)
        self.assertNotIn("github_pat_", text)


if __name__ == "__main__":
    unittest.main()
