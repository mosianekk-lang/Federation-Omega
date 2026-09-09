from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile" / "fuse-mobile"


class FuseMobileIapTransportV1Tests(unittest.TestCase):
    def text(self, relative: str) -> str:
        return (ROOT / relative).read_text()

    def test_google_signin_dependency_and_native_config_are_exact_public_only(self) -> None:
        package = json.loads((MOBILE / "package.json").read_text())
        self.assertEqual(package["dependencies"]["@react-native-google-signin/google-signin"], "16.1.5")
        app = json.loads((MOBILE / "app.json").read_text())
        self.assertIn("@react-native-google-signin/google-signin", app["expo"]["plugins"])
        env = (MOBILE / ".env.example").read_text()
        self.assertIn("EXPO_PUBLIC_FUSE_IAP_RESOURCE_CLIENT_ID", env)
        self.assertIn("installed Android/iOS OAuth client", env)
        self.assertIn("programmatic access", env)
        self.assertIn("EXPO_PUBLIC_FEDERATION_GATEWAY_URL", env)
        self.assertNotIn("PRIVATE_KEY", env)
        self.assertNotIn("CLIENT_SECRET", env)
        self.assertNotIn("REFRESH_TOKEN", env)

    def test_mobile_transport_keeps_iap_and_fuse_authority_in_separate_headers(self) -> None:
        federation = (MOBILE / "src" / "federation.ts").read_text()
        self.assertIn("Authorization: `Bearer ${iapIdentityToken.trim()}`", federation)
        self.assertIn("headers['X-Fuse-Authorization'] = `Bearer ${fuseCredential.trim()}`", federation)
        self.assertIn("enrollOwner", federation)
        self.assertIn("createFuseSession", federation)
        self.assertNotIn("Authorization: `Bearer ${accessToken}`", federation)

    def test_google_identity_token_is_ephemeral_and_resource_audience_is_explicit(self) -> None:
        iap = (MOBILE / "src" / "iap.ts").read_text()
        session = (MOBILE / "src" / "session.ts").read_text()
        self.assertIn("EXPO_PUBLIC_FUSE_IAP_RESOURCE_CLIENT_ID", iap)
        self.assertIn("IAP_RESOURCE_CLIENT_ID", iap)
        self.assertIn("separate provider-side identity", iap)
        self.assertIn("programmatic access", iap)
        self.assertIn("GoogleSignin.getTokens()", iap)
        self.assertIn("tokens.idToken", iap)
        self.assertNotIn("SecureStore", iap)
        self.assertIn("fuse.mobile.device_token", session)
        self.assertIn("fuse.mobile.access_token", session)
        self.assertNotIn("google", session.lower())
        self.assertNotIn("iap", session.lower())

    def test_owner_connection_enrolls_restores_and_retries_session_at_most_once(self) -> None:
        owner = (MOBILE / "src" / "ownerConnection.ts").read_text()
        self.assertIn("connectOwner", owner)
        self.assertIn("enrollOwner(iapIdentityToken)", owner)
        self.assertIn("loadDeviceCredential", owner)
        self.assertIn("createFuseSession", owner)
        self.assertIn("REFRESHABLE_SESSION_REASONS", owner)
        self.assertEqual(owner.count("return sendFuseMessage("), 1)
        self.assertEqual(owner.count("await sendFuseMessage("), 1)
        self.assertNotIn("while (", owner)
        self.assertNotIn("for (;;", owner)

    def test_ui_exposes_real_owner_connection_instead_of_dead_end(self) -> None:
        ui = (MOBILE / "app" / "index.tsx").read_text()
        self.assertIn("Connect owner", ui)
        self.assertIn("connectOwner", ui)
        self.assertIn("restoreOwnerSession", ui)
        self.assertIn("sendOwnerFuseMessage", ui)
        self.assertNotIn("A verified Federation Gateway session is required", ui)

    def test_backend_verifies_signed_iap_assertion_exact_audience_and_owner_hash(self) -> None:
        bindings = self.text("services/fuse_mobile_gateway/bindings.py")
        app = self.text("services/fuse_mobile_gateway/app.py")
        self.assertIn("IAP_CERTS_URL = \"https://www.gstatic.com/iap/verify/public_key\"", bindings)
        self.assertIn("/projects/{CANONICAL_PROJECT_NUMBER}/locations/{CANONICAL_REGION}/services/{CANONICAL_SERVICE}", bindings)
        self.assertIn("google_id_token.verify_token", bindings)
        self.assertIn("IAP_ISSUER = \"https://cloud.google.com/iap\"", bindings)
        self.assertIn("FUSE_MOBILE_OWNER_EMAIL_SHA256", bindings)
        self.assertIn("hmac.compare_digest(_sha256(email), self.owner_email_sha256)", bindings)
        self.assertIn("X-Goog-IAP-JWT-Assertion", app)
        self.assertIn("enroll_iap_owner", app)
        self.assertNotIn("X-Goog-Authenticated-User-Email", app)
        self.assertNotIn("X-Goog-Authenticated-User-Email", bindings)

    def test_iap_identity_cannot_create_fuse_effect_authority(self) -> None:
        runtime = self.text("services/fuse_mobile_gateway/runtime.py")
        self.assertIn("owner_identity_verifier", runtime)
        self.assertIn("enroll_iap_owner", runtime)
        self.assertIn("device_manager.enroll_verified", runtime)
        self.assertIn("GOOGLE_IAP_IDENTITY_PLUS_FUSE_SESSION", runtime)
        self.assertIn("OWNER_EFFECT_APPROVAL_REQUIRED", runtime)


if __name__ == "__main__":
    unittest.main()
