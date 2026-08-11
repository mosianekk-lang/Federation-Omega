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
    "provider_cutover_v3", ROOT / "phoenix" / "provider_cutover_v3.py"
)
assert SPEC and SPEC.loader
V3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = V3
SPEC.loader.exec_module(V3)


class UserAPI:
    def __init__(self):
        self.calls = []

    def request(self, method, path, payload=None, expected=(200, 201, 204)):
        self.calls.append((method, path, payload))
        if path == "/user":
            return 200, {"login": "mosianekk-lang"}
        if path == "/repos/mosianekk-lang/Federation-Omega":
            return 200, {"permissions": {"admin": True}}
        if path.endswith("/actions/permissions"):
            return 200, {"enabled": True}
        if "rulesets" in path:
            return 200, []
        raise AssertionError((method, path, payload))

    def optional(self, path):
        return None


class InstallationAPI:
    def __init__(self, include_source=True):
        self.include_source = include_source
        self.calls = []

    def request(self, method, path, payload=None, expected=(200, 201, 204)):
        self.calls.append((method, path, payload))
        if path == "/user":
            raise V3.CutoverError("GitHub API GET /user failed with 403")
        if path == "/installation/repositories?per_page=100":
            repos = (
                [{"full_name": "mosianekk-lang/Federation-Omega"}]
                if self.include_source
                else []
            )
            return 200, {"repositories": repos}
        if path == "/repos/mosianekk-lang/Federation-Omega":
            return 200, {
                "permissions": {"admin": True},
                "is_template": False,
            }
        if path.endswith("/actions/permissions"):
            return 200, {"enabled": True}
        if "rulesets" in path:
            return 200, []
        raise AssertionError((method, path, payload))


class TemplateGenerationAPI:
    def __init__(self, original_template=False):
        self.template = original_template
        self.repos = {
            "Federation-Omega": {
                "full_name": "mosianekk-lang/Federation-Omega",
                "permissions": {"admin": True},
                "is_template": original_template,
                "private": False,
            }
        }
        self.calls = []

    def optional(self, path):
        name = path.rsplit("/", 1)[-1]
        return self.repos.get(name)

    def request(self, method, path, payload=None, expected=(200, 201, 204)):
        self.calls.append((method, path, payload))
        if path == "/repos/mosianekk-lang/Federation-Omega":
            if method == "GET":
                return 200, dict(self.repos["Federation-Omega"])
            if method == "PATCH":
                self.template = bool(payload["is_template"])
                self.repos["Federation-Omega"]["is_template"] = self.template
                return 200, dict(self.repos["Federation-Omega"])
        if path == "/repos/mosianekk-lang/Federation-Omega/generate":
            assert self.template is True
            name = payload["name"]
            repo = {
                "full_name": f"mosianekk-lang/{name}",
                "private": bool(payload["private"]),
            }
            self.repos[name] = repo
            return 201, dict(repo)
        raise AssertionError((method, path, payload))


class UserCreationAPI:
    def __init__(self):
        self.calls = []

    def optional(self, path):
        return None

    def request(self, method, path, payload=None, expected=(200, 201, 204)):
        self.calls.append((method, path, payload))
        if method == "POST" and path == "/user/repos":
            return 201, {"name": payload["name"], "private": payload["private"]}
        raise AssertionError((method, path, payload))


class ProviderCutoverV3Tests(unittest.TestCase):
    def test_auto_prefers_user_scoped_authority(self):
        result = V3.detect_authority(
            UserAPI(), "mosianekk-lang", "Federation-Omega", "auto"
        )
        self.assertEqual("USER_SCOPED", result["authority_model"])
        self.assertEqual("/user/repos", result["repository_creation_endpoint"])

    def test_auto_falls_back_to_installation_template_authority(self):
        result = V3.detect_authority(
            InstallationAPI(),
            "mosianekk-lang",
            "Federation-Omega",
            "auto",
        )
        self.assertEqual("INSTALLATION_TEMPLATE", result["authority_model"])
        self.assertTrue(result["installation_all_repositories_required"])
        self.assertTrue(
            result["repository_creation_endpoint"].endswith("/generate")
        )

    def test_installation_preflight_rejects_missing_template_source(self):
        with self.assertRaisesRegex(
            V3.CutoverError, "cannot access template source"
        ):
            V3.installation_authority_preflight(
                InstallationAPI(include_source=False),
                "mosianekk-lang",
                "Federation-Omega",
            )

    def test_template_generation_restores_original_false_state(self):
        api = TemplateGenerationAPI(original_template=False)
        original_sleep = V3.time.sleep
        V3.time.sleep = lambda *_: None
        try:
            result = V3.generate_missing_template_repositories(
                api,
                "mosianekk-lang",
                "Federation-Omega",
                [
                    ("Federation-Omega-Core", False, "Core"),
                    ("Federation-Omega-Ops", True, "Ops"),
                ],
            )
        finally:
            V3.time.sleep = original_sleep
        self.assertEqual(
            "CREATED_TEMPLATE_ENDPOINT",
            result["Federation-Omega-Core"][0],
        )
        self.assertEqual(
            "CREATED_TEMPLATE_ENDPOINT",
            result["Federation-Omega-Ops"][0],
        )
        self.assertFalse(api.template)
        patches = [
            payload["is_template"]
            for method, path, payload in api.calls
            if method == "PATCH"
        ]
        self.assertEqual([True, False], patches)

    def test_template_generation_preserves_original_true_state(self):
        api = TemplateGenerationAPI(original_template=True)
        original_sleep = V3.time.sleep
        V3.time.sleep = lambda *_: None
        try:
            V3.generate_missing_template_repositories(
                api,
                "mosianekk-lang",
                "Federation-Omega",
                [("Federation-Omega-Core", False, "Core")],
            )
        finally:
            V3.time.sleep = original_sleep
        self.assertTrue(api.template)
        patches = [call for call in api.calls if call[0] == "PATCH"]
        self.assertEqual([], patches)

    def test_user_route_uses_authenticated_user_endpoint(self):
        api = UserCreationAPI()
        operation, created = V3.ensure_user_repository(
            api,
            "mosianekk-lang",
            "Federation-Omega-Core",
            False,
            "Core",
        )
        self.assertEqual("CREATED_USER_ENDPOINT", operation)
        self.assertFalse(created["private"])
        self.assertEqual("/user/repos", api.calls[0][1])

    def test_default_ruleset_does_not_lock_sole_owner(self):
        payload = V3.ruleset_payload("Core Main", False)
        pull_request = next(
            rule for rule in payload["rules"] if rule["type"] == "pull_request"
        )
        parameters = pull_request["parameters"]
        self.assertEqual(0, parameters["required_approving_review_count"])
        self.assertFalse(parameters["require_code_owner_review"])
        self.assertFalse(parameters["require_last_push_approval"])

    def test_second_reviewer_mode_enables_review_gates(self):
        payload = V3.ruleset_payload("Core Main", True)
        pull_request = next(
            rule for rule in payload["rules"] if rule["type"] == "pull_request"
        )
        parameters = pull_request["parameters"]
        self.assertEqual(1, parameters["required_approving_review_count"])
        self.assertTrue(parameters["require_code_owner_review"])
        self.assertTrue(parameters["require_last_push_approval"])

    def test_safe_extract_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "bad.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                info = tarfile.TarInfo("../escape.txt")
                data = b"no"
                info.size = len(data)
                bundle.addfile(info, io.BytesIO(data))
            with self.assertRaisesRegex(V3.CutoverError, "Unsafe archive path"):
                V3.safe_extract(archive, root / "out")

    def test_template_payload_supports_custom_private_target(self):
        payload = V3.template_payload(
            "mosianekk-lang",
            "Federation-Omega-Ops",
            True,
            "Ops",
        )
        self.assertEqual("mosianekk-lang", payload["owner"])
        self.assertEqual("Federation-Omega-Ops", payload["name"])
        self.assertTrue(payload["private"])
        self.assertFalse(payload["include_all_branches"])


if __name__ == "__main__":
    unittest.main()
