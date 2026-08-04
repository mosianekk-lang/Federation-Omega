from __future__ import annotations

import importlib.util
import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "provider_cutover_v2", ROOT / "phoenix" / "provider_cutover_v2.py"
)
assert SPEC and SPEC.loader
CUTOVER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CUTOVER
SPEC.loader.exec_module(CUTOVER)


class FakeAPI:
    def __init__(self, responses=None, optional_responses=None, failure=None):
        self.responses = responses or {}
        self.optional_responses = optional_responses or {}
        self.failure = failure
        self.calls = []

    def request(self, method, path, payload=None, expected=(200, 201, 204)):
        self.calls.append((method, path, payload))
        if self.failure and path == self.failure:
            raise CUTOVER.CutoverError("simulated provider failure")
        key = (method, path)
        if key not in self.responses:
            raise AssertionError(f"Unexpected request: {key}")
        return 200, self.responses[key]

    def optional(self, path):
        self.calls.append(("OPTIONAL", path, None))
        return self.optional_responses.get(path)


class PhoenixProviderCutoverV2Tests(unittest.TestCase):
    def test_default_ruleset_is_safe_for_sole_owner(self):
        payload = CUTOVER.ruleset_payload("Core Main", False)
        pull_request = next(
            rule for rule in payload["rules"] if rule["type"] == "pull_request"
        )
        parameters = pull_request["parameters"]
        self.assertEqual(0, parameters["required_approving_review_count"])
        self.assertFalse(parameters["require_code_owner_review"])
        self.assertFalse(parameters["require_last_push_approval"])
        self.assertTrue(parameters["required_review_thread_resolution"])

    def test_second_reviewer_mode_enables_review_controls(self):
        payload = CUTOVER.ruleset_payload("Core Main", True)
        pull_request = next(
            rule for rule in payload["rules"] if rule["type"] == "pull_request"
        )
        parameters = pull_request["parameters"]
        self.assertEqual(1, parameters["required_approving_review_count"])
        self.assertTrue(parameters["require_code_owner_review"])
        self.assertTrue(parameters["require_last_push_approval"])
        self.assertTrue(parameters["dismiss_stale_reviews_on_push"])

    def test_safe_extract_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                info = tarfile.TarInfo("../escape.txt")
                data = b"escape"
                info.size = len(data)
                bundle.addfile(info, io.BytesIO(data))
            with self.assertRaises(CUTOVER.CutoverError):
                CUTOVER.safe_extract(archive, root / "out")

    def test_safe_extract_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "symlink.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                info = tarfile.TarInfo("link")
                info.type = tarfile.SYMTYPE
                info.linkname = "target"
                bundle.addfile(info)
            with self.assertRaises(CUTOVER.CutoverError):
                CUTOVER.safe_extract(archive, root / "out")

    def test_archive_digest_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archive.tar.gz"
            path.write_bytes(b"not-the-expected-archive")
            with self.assertRaises(CUTOVER.CutoverError):
                CUTOVER.validate_expected_digest(path, "0" * 64)

    def test_authority_preflight_accepts_matching_user_admin(self):
        owner = "mosianekk-lang"
        legacy = "Federation-Omega"
        api = FakeAPI(
            responses={
                ("GET", "/user"): {"login": owner},
                ("GET", f"/repos/{owner}/{legacy}"): {
                    "permissions": {"admin": True}
                },
                ("GET", f"/repos/{owner}/{legacy}/actions/permissions"): {
                    "enabled": True
                },
                (
                    "GET",
                    f"/repos/{owner}/{legacy}/rulesets?includes_parents=false",
                ): [],
            }
        )
        result = CUTOVER.authority_preflight(api, owner, legacy)
        self.assertTrue(result["user_identity_verified"])
        self.assertTrue(result["legacy_repository_admin"])
        self.assertFalse(result["credential_value_recorded"])

    def test_authority_preflight_rejects_installation_only_credential(self):
        api = FakeAPI(failure="/user")
        with self.assertRaisesRegex(
            CUTOVER.CutoverError, "user-scoped"
        ):
            CUTOVER.authority_preflight(api, "mosianekk-lang", "Federation-Omega")

    def test_authority_preflight_rejects_wrong_user(self):
        api = FakeAPI(responses={("GET", "/user"): {"login": "someone-else"}})
        with self.assertRaisesRegex(CUTOVER.CutoverError, "does not match"):
            CUTOVER.authority_preflight(api, "mosianekk-lang", "Federation-Omega")

    def test_verify_repository_requires_exact_provider_state(self):
        owner = "mosianekk-lang"
        repo = "Federation-Omega-Core"
        ruleset_id = 123
        expected_head = "a" * 40
        api = FakeAPI(
            responses={
                ("GET", f"/repos/{owner}/{repo}"): {
                    "full_name": f"{owner}/{repo}",
                    "private": True,
                    "default_branch": "main",
                },
                ("GET", f"/repos/{owner}/{repo}/actions/permissions"): {
                    "enabled": False
                },
                (
                    "GET",
                    f"/repos/{owner}/{repo}/actions/permissions/workflow",
                ): {
                    "default_workflow_permissions": "read",
                    "can_approve_pull_request_reviews": False,
                },
                ("GET", f"/repos/{owner}/{repo}/git/ref/heads/main"): {
                    "object": {"sha": expected_head}
                },
                ("GET", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}"): {
                    "enforcement": "active",
                    "target": "branch",
                },
            },
            optional_responses={
                f"/repos/{owner}/{repo}/contents/.github/workflows?ref=main": None
            },
        )
        result = CUTOVER.verify_repository(
            api,
            owner,
            repo,
            expected_private=True,
            expected_head=expected_head,
            ruleset_id=ruleset_id,
        )
        self.assertTrue(result["verified"])
        self.assertTrue(all(result["checks"].values()))

    def test_verify_repository_fails_on_head_mismatch(self):
        owner = "mosianekk-lang"
        repo = "Federation-Omega-Core"
        ruleset_id = 123
        api = FakeAPI(
            responses={
                ("GET", f"/repos/{owner}/{repo}"): {
                    "full_name": f"{owner}/{repo}",
                    "private": True,
                    "default_branch": "main",
                },
                ("GET", f"/repos/{owner}/{repo}/actions/permissions"): {
                    "enabled": False
                },
                (
                    "GET",
                    f"/repos/{owner}/{repo}/actions/permissions/workflow",
                ): {
                    "default_workflow_permissions": "read",
                    "can_approve_pull_request_reviews": False,
                },
                ("GET", f"/repos/{owner}/{repo}/git/ref/heads/main"): {
                    "object": {"sha": "b" * 40}
                },
                ("GET", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}"): {
                    "enforcement": "active",
                    "target": "branch",
                },
            },
            optional_responses={
                f"/repos/{owner}/{repo}/contents/.github/workflows?ref=main": None
            },
        )
        result = CUTOVER.verify_repository(
            api,
            owner,
            repo,
            expected_private=True,
            expected_head="a" * 40,
            ruleset_id=ruleset_id,
        )
        self.assertFalse(result["verified"])
        self.assertFalse(result["checks"]["main_head_matches_export"])


if __name__ == "__main__":
    unittest.main()
