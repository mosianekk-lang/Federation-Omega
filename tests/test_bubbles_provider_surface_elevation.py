from __future__ import annotations

import json
import unittest

from bubbles.platform_specialist_corps_extensions import build_provider_extended_corps
from bubbles.provider_surface_probe import (
    ARCHON_SCRIPT_DEPLOYMENT_ID,
    ARCHON_SCRIPT_URL,
    CommandResult,
    ProbeHooks,
    run_probe,
)


class ProviderSurfaceElevationTests(unittest.TestCase):
    def test_provider_extensions_add_four_unique_first_class_specialists(self) -> None:
        corps = build_provider_extended_corps()
        required = {
            "Federation Omega Operator",
            "ARCHON Admin Plane V5",
            "ARCHON Apps Script Translator",
            "AFEME v4",
        }
        self.assertTrue(required.issubset(corps.roles))
        self.assertGreaterEqual(len(corps.roles), 23)
        role_ids = [role.role_id for role in corps.roles.values()]
        self.assertEqual(len(role_ids), len(set(role_ids)))

    def test_apps_script_extension_forbids_service_account_api_shortcut(self) -> None:
        corps = build_provider_extended_corps()
        role = corps.roles["ARCHON Apps Script Translator"]
        joined = " ".join(role.forbidden_assumptions)
        self.assertIn("service account", joined)
        self.assertIn("Apps Script API", joined)

    def test_attachment_deployment_id_is_bound_to_exec_url(self) -> None:
        self.assertTrue(ARCHON_SCRIPT_DEPLOYMENT_ID.startswith("AKfy"))
        self.assertEqual(
            f"https://script.google.com/macros/s/{ARCHON_SCRIPT_DEPLOYMENT_ID}/exec",
            ARCHON_SCRIPT_URL,
        )

    def test_full_read_only_probe_can_promote_all_four_surfaces_without_leaking_tokens(self) -> None:
        def fake_http(url, *, body=None, headers=None, follow_redirects=False, timeout=20):
            headers = dict(headers or {})
            if "federation-omega-operator" in url and url.endswith("/health"):
                return {"http_status": 200, "body": {"ok": True, "status": "OPERATOR_READY"}}
            if "federation-omega-operator" in url and body is None:
                return {
                    "http_status": 200,
                    "body": {"ok": True, "allowedActions": ["STATUS", "READ_CLOUD_RUN_SERVICE"]},
                }
            if "federation-omega-operator" in url and body is not None:
                self.assertEqual("fo-secret-value", headers.get("x-fo-admin-token"))
                return {"http_status": 200, "body": {"ok": True, "action": body["action"]}}
            if "archon-admin-plane" in url and url.endswith("openapi.yaml"):
                return {"http_status": 200, "body": {"text": "openapi: 3.0.0"}}
            if "archon-admin-plane" in url and body is None:
                return {"http_status": 200, "body": {"ok": True, "service": "archon-admin-plane"}}
            if "archon-admin-plane" in url and body is not None:
                self.assertEqual("Bearer archon-secret-value", headers.get("Authorization"))
                return {"http_status": 200, "body": {"ok": True, "command": "capability_audit"}}
            if "script.google.com/macros" in url:
                return {"http_status": 302, "body": {"text": ""}, "location": "https://accounts.google.com/"}
            if "afeme-sovereign" in url and headers.get("Authorization"):
                self.assertEqual("Bearer id-token-value", headers["Authorization"])
                return {"http_status": 200, "body": {"ok": True, "service": "afeme-v4"}}
            if "afeme-sovereign" in url:
                return {"http_status": 403, "body": {"error": "unauthorized"}}
            raise AssertionError(url)

        def fake_command(args):
            joined = " ".join(args)
            if "auth list" in joined:
                return CommandResult(0, "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com\n", "")
            if "secrets versions access" in joined and "fo-operator-admin-token" in joined:
                return CommandResult(0, "fo-secret-value\n", "")
            if "secrets versions access" in joined and "archon-admin-plane-token" in joined:
                return CommandResult(0, "archon-secret-value\n", "")
            if "print-identity-token" in joined:
                return CommandResult(0, "id-token-value\n", "")
            return CommandResult(1, "", "unsupported")

        receipt = run_probe(ProbeHooks(http=fake_http, command=fake_command))
        surfaces = receipt["surfaces"]
        self.assertEqual("AUTHENTICATED_READBACK_VERIFIED", surfaces["federation_omega_operator"]["classification"])
        self.assertEqual("AUTHENTICATED_CAPABILITY_AUDIT_REACHABLE", surfaces["archon_admin_plane_v5"]["classification"])
        self.assertEqual("AUTH_OR_REDIRECT_REACHABLE", surfaces["archon_apps_script_translator"]["classification"])
        self.assertEqual("IDENTITY_TOKEN_READ_VERIFIED", surfaces["afeme_v4"]["classification"])
        self.assertFalse(receipt["mutation_attempted"])
        self.assertFalse(receipt["secret_values_recorded"])
        rendered = json.dumps(receipt, sort_keys=True)
        self.assertNotIn("fo-secret-value", rendered)
        self.assertNotIn("archon-secret-value", rendered)
        self.assertNotIn("id-token-value", rendered)

    def test_missing_provider_credentials_fail_closed_without_mutation(self) -> None:
        def fake_http(url, **kwargs):
            if "federation-omega-operator" in url and url.endswith("/health"):
                return {"http_status": 200, "body": {"ok": True}}
            if "federation-omega-operator" in url:
                return {"http_status": 200, "body": {"ok": True, "allowedActions": ["STATUS", "READ_CLOUD_RUN_SERVICE"]}}
            if "script.google.com" in url:
                return {"http_status": 403, "body": {"error": "auth"}}
            return {"http_status": 403, "body": {"error": "auth"}}

        def fake_command(args):
            return CommandResult(1, "", "no provider identity")

        receipt = run_probe(ProbeHooks(http=fake_http, command=fake_command))
        operator = receipt["surfaces"]["federation_omega_operator"]
        self.assertEqual("BLOCKED_TRUSTED_TOKEN_BINDING", operator["classification"])
        self.assertFalse(operator["trusted_token_available"])
        self.assertFalse(receipt["mutation_attempted"])


if __name__ == "__main__":
    unittest.main()
