from __future__ import annotations

import unittest

from provider_authority import AppsScriptAuthorityEvidence, CloudRunInvocationEvidence, ProviderAuthorityGate


class ProviderAuthorityGateTests(unittest.TestCase):
    def test_cloud_run_requires_complete_live_evidence(self) -> None:
        blocked = ProviderAuthorityGate.certify_cloud_run(CloudRunInvocationEvidence(
            service="federation-omega-operator", revision="", request_id="req-1",
            authenticated_principal="", response_status=0, response_body_hash="",
            readback_match=False, rollback_supported=False,
        ))
        self.assertEqual(blocked["status"], "CLOUD_RUN_CERTIFICATION_BLOCKED")
        certified = ProviderAuthorityGate.certify_cloud_run(CloudRunInvocationEvidence(
            service="federation-omega-operator", revision="rev-1", request_id="req-2",
            authenticated_principal="owner@example.com", response_status=200,
            response_body_hash="a" * 64, readback_match=True, rollback_supported=True,
        ))
        self.assertEqual(certified["status"], "CLOUD_RUN_LIVE_CERTIFIED")

    def test_apps_script_requires_human_oauth_and_execution_receipts(self) -> None:
        no_oauth = ProviderAuthorityGate.certify_apps_script(AppsScriptAuthorityEvidence(
            script_id="script-1", oauth_subject=None, oauth_scopes=(),
            standard_cloud_project_bound=True, apps_script_api_enabled=True,
        ))
        self.assertEqual(no_oauth["status"], "OWNER_CONSENT_REQUIRED")
        ready = ProviderAuthorityGate.certify_apps_script(AppsScriptAuthorityEvidence(
            script_id="script-1", oauth_subject="owner@example.com",
            oauth_scopes=tuple(ProviderAuthorityGate.REQUIRED_APPS_SCRIPT_SCOPES),
            standard_cloud_project_bound=True, apps_script_api_enabled=True,
        ))
        self.assertEqual(ready["status"], "AUTHORITY_READY_EXECUTION_UNPROVEN")
        live = ProviderAuthorityGate.certify_apps_script(AppsScriptAuthorityEvidence(
            script_id="script-1", oauth_subject="owner@example.com",
            oauth_scopes=tuple(ProviderAuthorityGate.REQUIRED_APPS_SCRIPT_SCOPES),
            standard_cloud_project_bound=True, apps_script_api_enabled=True,
            source_read_receipt="read-1", source_write_receipt="write-1", trigger_receipt="trigger-1",
        ))
        self.assertEqual(live["status"], "APPS_SCRIPT_LIVE_CERTIFIED")


if __name__ == "__main__":
    unittest.main()
