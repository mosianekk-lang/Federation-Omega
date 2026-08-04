from __future__ import annotations

import unittest

from ops.apps_script_authorization_gate import (
    AppsScriptSecurityError,
    validate_apps_script_source,
)


class AppsScriptAuthorizationGateTests(unittest.TestCase):
    def test_caller_authorization_substitution_is_rejected(self) -> None:
        source = """
        function doPost(e) {
          const body = JSON.parse(e.postData.contents);
          const supplied = body.approvalKey || CONFIG.APPROVAL_KEY;
          return runPrivileged(supplied);
        }
        """
        with self.assertRaisesRegex(
            AppsScriptSecurityError,
            "must not fall back",
        ):
            validate_apps_script_source(source)

    def test_hardcoded_authorization_material_is_rejected(self) -> None:
        source = """
        const CONFIG = Object.freeze({
          APPROVAL_KEY: "placeholder-value"
        });
        """
        with self.assertRaisesRegex(
            AppsScriptSecurityError,
            "must not be hardcoded",
        ):
            validate_apps_script_source(source)

    def test_public_privileged_post_handler_is_rejected(self) -> None:
        source = """
        const manifest = {"webapp": {"access": "ANYONE"}};
        function doPost(e) {
          return privilegedAction(e);
        }
        """
        with self.assertRaisesRegex(
            AppsScriptSecurityError,
            "must not use public ANYONE",
        ):
            validate_apps_script_source(source)

    def test_missing_authorization_fails_closed(self) -> None:
        source = """
        const manifest = {"webapp": {"access": "DOMAIN"}};
        function doPost(e) {
          const body = JSON.parse(e.postData.contents);
          const supplied = body.approvalKey;
          if (!supplied) throw new Error("AUTHORIZATION_REQUIRED");
          return runReadOnlyAction(supplied);
        }
        """
        self.assertEqual(validate_apps_script_source(source), source)


if __name__ == "__main__":
    unittest.main()
