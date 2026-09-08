from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile" / "fuse-mobile"


class FuseMobileClientContractV1Tests(unittest.TestCase):
    def test_required_build_contract_files_exist(self) -> None:
        for relative in ("app.json", "tsconfig.json", "eas.json", "package.json"):
            self.assertTrue((MOBILE / relative).is_file(), relative)

    def test_app_identity_is_consistent_and_no_secret_is_embedded(self) -> None:
        app = json.loads((MOBILE / "app.json").read_text())
        expo = app["expo"]
        self.assertEqual(expo["android"]["package"], expo["ios"]["bundleIdentifier"])
        raw = json.dumps(app).lower()
        for forbidden in ("api_key", "openrouter_api_key", "sk-", "bearer "):
            self.assertNotIn(forbidden, raw)

    def test_gateway_client_requires_external_config_and_bearer_session(self) -> None:
        client = (MOBILE / "src" / "federation.ts").read_text()
        self.assertIn("EXPO_PUBLIC_FEDERATION_GATEWAY_URL", client)
        self.assertIn("FEDERATION_GATEWAY_UNCONFIGURED", client)
        self.assertIn("FEDERATION_GATEWAY_INSECURE_URL", client)
        self.assertIn("Authorization: `Bearer ${accessToken}`", client)
        self.assertIn("/v1/capabilities", client)
        self.assertIn("/v1/chat", client)
        self.assertIn("/v1/federation/health", client)

    def test_session_uses_native_secure_store(self) -> None:
        session = (MOBILE / "src" / "session.ts").read_text()
        self.assertIn("expo-secure-store", session)
        self.assertIn("AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY", session)
        self.assertIn("clearSession", session)
        self.assertNotIn("AsyncStorage", session)

    def test_fuse_bar_is_bound_to_client_and_fails_closed_without_session(self) -> None:
        ui_path = MOBILE / "app" / "index.tsx"
        if not ui_path.is_file():
            self.skipTest("FUSE Mobile UI is outside this reduced exported-core verification surface")
        ui = ui_path.read_text()
        self.assertIn("sendFuseMessage", ui)
        self.assertIn("loadSession", ui)
        self.assertIn("onPress={handleSend}", ui)
        self.assertIn("Gateway session required", ui)
        self.assertIn("FEDERATION_GATEWAY", (MOBILE / "src" / "federation.ts").read_text())

    def test_build_profiles_separate_preview_and_production(self) -> None:
        eas = json.loads((MOBILE / "eas.json").read_text())
        self.assertEqual(eas["build"]["preview"]["android"]["buildType"], "apk")
        self.assertIn("production", eas["build"])
        self.assertNotEqual(eas["build"]["preview"], eas["build"]["production"])


if __name__ == "__main__":
    unittest.main()
