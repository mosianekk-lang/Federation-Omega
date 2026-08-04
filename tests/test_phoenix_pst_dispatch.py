from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phoenix_build_exports_v2_test", ROOT / "phoenix" / "build_exports_v2.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhoenixPstDispatchTests(unittest.TestCase):
    def test_skips_outside_authorised_phoenix_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=True):
            result = MODULE.maybe_dispatch_pst_remote_verifier(Path(tmp))
        self.assertEqual(result["status"], "SKIPPED_UNAUTHORISED_CONTEXT")

    def test_skips_when_request_is_absent(self) -> None:
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_WORKFLOW": "Phoenix Emergency Execution Freeze",
        }
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, env, clear=True):
            result = MODULE.maybe_dispatch_pst_remote_verifier(Path(tmp))
        self.assertEqual(result["status"], "SKIPPED_NO_REQUEST")

    def test_rejects_malformed_request_before_provider_call(self) -> None:
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_WORKFLOW": "Phoenix Emergency Execution Freeze",
            "GITHUB_REPOSITORY": "mosianekk-lang/Federation-Omega",
            "GH_TOKEN": "not-used-because-validation-fails",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = root / MODULE.PST_REQUEST_PATH
            request.parent.mkdir(parents=True, exist_ok=True)
            request.write_text(
                json.dumps(
                    {
                        "schema": "WRONG",
                        "status": "REQUESTED",
                        "request_nonce": "test",
                        "workflow_path": MODULE.PST_WORKFLOW_PATH,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                MODULE, "_gh_api"
            ) as provider:
                with self.assertRaisesRegex(RuntimeError, "PST_VERIFY_REQUEST_INVALID"):
                    MODULE.maybe_dispatch_pst_remote_verifier(root)
                provider.assert_not_called()

    def test_skips_when_verified_completion_already_exists(self) -> None:
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_WORKFLOW": "Phoenix Emergency Execution Freeze",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = root / MODULE.PST_REQUEST_PATH
            request.parent.mkdir(parents=True, exist_ok=True)
            request.write_text(
                json.dumps(
                    {
                        "schema": "FEDOMEGA-PST-PHOENIX-VERIFY-REQUEST-1",
                        "status": "REQUESTED",
                        "request_nonce": "test-complete",
                        "workflow_path": MODULE.PST_WORKFLOW_PATH,
                    }
                ),
                encoding="utf-8",
            )
            completion = root / MODULE.PST_COMPLETION_PATH
            completion.parent.mkdir(parents=True, exist_ok=True)
            completion.write_text(
                json.dumps({"status": "COMPLETE_VERIFIED"}), encoding="utf-8"
            )
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                MODULE, "_gh_api"
            ) as provider:
                result = MODULE.maybe_dispatch_pst_remote_verifier(root)
                provider.assert_not_called()
        self.assertEqual(result["status"], "SKIPPED_ALREADY_COMPLETE_VERIFIED")


if __name__ == "__main__":
    unittest.main()
