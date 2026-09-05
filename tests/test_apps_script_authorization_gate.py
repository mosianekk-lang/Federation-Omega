from __future__ import annotations

import json
import unittest

from ops.apps_script_authorization_gate import (
    AppsScriptSecurityError,
    audit_apps_script_source,
    validate_apps_script_source,
)


class AppsScriptAuthorizationGateCompatibilityTests(unittest.TestCase):
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


class AppsScriptFleetBundleTests(unittest.TestCase):
    def fleet(self) -> str:
        return json.dumps(
            {
                "contract": "FO_GAS_FLEET_RESTORABLE_BACKUP",
                "sourceSha256": "a" * 64,
                "files": [
                    {
                        "name": "appsscript",
                        "type": "JSON",
                        "source": json.dumps(
                            {
                                "oauthScopes": [
                                    "https://www.googleapis.com/auth/cloud-platform",
                                    "https://www.googleapis.com/auth/script.projects",
                                    "https://www.googleapis.com/auth/script.deployments",
                                ],
                                "webapp": {
                                    "executeAs": "USER_DEPLOYING",
                                    "access": "ANYONE",
                                },
                            }
                        ),
                    },
                    {
                        "name": "Code",
                        "type": "SERVER_JS",
                        "source": r'''
const CONFIG = Object.freeze({
  CLOUD_PROJECT_NUMBER: "516699068552",
  APPROVAL_KEY: "APPROVED"
});
function doGet(e) {
  const key = getParam_(e, "key");
  return jsonOutput_(getBridgeStatus());
}
function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  enqueueCommand({approvalKey: body.approvalKey || CONFIG.APPROVAL_KEY});
  if (body.runNow !== false) { return runNowBridge(); }
}
function enqueueCommand(command) {
  const normalized = {approvalKey: command.approvalKey};
  sheet.appendRow([normalized.approvalKey]);
}
function callRuntimeExecute_(payload) {
  const outbound = payload || {};
  outbound.approvalKey = outbound.approvalKey || CONFIG.APPROVAL_KEY;
  const successful = httpStatus >= 200 && httpStatus < 300 && body.status !== "FAILED";
  return successful;
}
function getBridgeStatus() {
  return {projectNumber: 1, spreadsheetUrl: "x", runtimeUrl: "y", capabilities: []};
}
function ARCHON_enableRequiredApis() { return enableService_("516699068552"); }
function ARCHON_codeApply(command) { return command; }
function ARCHON_codeRollback(command) { return command; }
const proof = {commandRowFound: true, resultJsonPresent: true, completedAtPresent: true};
''',
                    },
                    {
                        "name": "Gateway",
                        "type": "SERVER_JS",
                        "source": r'''
/** OMEGA_GATEWAY_TOKEN must be a unique private 32+ character token. */
function doGet() { return {}; }
function doPost(event) { return {}; }
''',
                    },
                    {
                        "name": "SignedManager",
                        "type": "SERVER_JS",
                        "source": r'''
function ARCHON_codeApply(context) {
  verifySignedRequest(context);
  CacheService.getScriptCache().put(context.nonce, "USED", 600);
}
function ARCHON_codeRollback(context) {
  computeHmacSha256Signature(context);
  CacheService.getScriptCache().put(context.nonce, "USED", 600);
}
''',
                    },
                    {
                        "name": "Omega",
                        "type": "SERVER_JS",
                        "source": r'''
function omegaMcpCall_() {
  const url = properties.getProperty(OMEGA_CONTROL.URL_PROPERTY);
  return UrlFetchApp.fetch(url, {headers: {Authorization: 'Bearer ' + token}});
}
''',
                    },
                ],
            }
        )

    def report(self) -> dict:
        return audit_apps_script_source(self.fleet())

    def codes(self) -> set[str]:
        return {item["code"] for item in self.report()["findings"]}

    def test_bundle_wrapper_is_parsed_and_fails_closed(self) -> None:
        report = self.report()
        self.assertEqual(report["source_kind"], "FLEET_BACKUP_JSON")
        self.assertEqual(report["status"], "SECURITY_HOLD")
        self.assertFalse(report["provider_authority_proven"])
        self.assertFalse(report["provider_mutation_authorized"])

    def test_public_privileged_ingress_and_immediate_execution_are_detected(self) -> None:
        self.assertTrue(
            {
                "PUBLIC_PRIVILEGED_WEBAPP",
                "PUBLIC_UNSIGNED_POST",
                "PUBLIC_POST_IMMEDIATE_EXECUTION",
                "PUBLIC_STATUS_METADATA_EXPOSURE",
            }.issubset(self.codes())
        )

    def test_static_default_and_persisted_approval_are_detected(self) -> None:
        self.assertTrue(
            {
                "STATIC_APPROVAL_SECRET",
                "DEFAULT_APPROVAL_BYPASS",
                "APPROVAL_CREDENTIAL_PERSISTED",
                "SECRET_IN_QUERY_PARAMETER",
            }.issubset(self.codes())
        )

    def test_global_collisions_and_weak_mutator_shadowing_are_detected(self) -> None:
        report = self.report()
        duplicate_findings = [
            item for item in report["findings"]
            if item["code"] == "DUPLICATE_GLOBAL_HANDLER"
        ]
        self.assertGreaterEqual(len(duplicate_findings), 4)
        self.assertIn("MIXED_AUTH_MUTATOR_SHADOWING", self.codes())

    def test_lineage_transport_and_semantic_proof_defects_are_detected(self) -> None:
        self.assertTrue(
            {
                "LEGACY_PROJECT_MUTATION_DEFAULT",
                "GENERIC_TRANSPORT_SUCCESS_PROMOTION",
                "SELF_READBACK_ONLY",
            }.issubset(self.codes())
        )
        self.assertIn("516699068552", self.report()["observed_project_numbers"])

    def test_bearer_destination_replay_and_token_policy_are_detected(self) -> None:
        self.assertTrue(
            {
                "CONFIGURABLE_BEARER_DESTINATION",
                "EPHEMERAL_NONCE_REPLAY_STORE",
                "TOKEN_STRENGTH_NOT_ENFORCED",
            }.issubset(self.codes())
        )

    def test_receipt_hash_is_deterministic_and_bound(self) -> None:
        left = self.report()
        right = self.report()
        self.assertEqual(left["receipt_sha256"], right["receipt_sha256"])
        claimed = left.pop("receipt_sha256")
        from ops.apps_script_authorization_gate import canonical_sha256
        self.assertEqual(claimed, canonical_sha256(left))

    def test_declared_hash_nonmatch_is_unverified_not_corruption_claim(self) -> None:
        integrity = self.report()["integrity"]
        self.assertEqual(
            integrity["declared_hash_verification_state"],
            "ALGORITHM_UNSPECIFIED_UNVERIFIED",
        )
        self.assertIn("does not prove corruption", integrity["note"])

    def test_minimal_signed_public_gateway_is_not_false_blocked(self) -> None:
        source = json.dumps(
            {
                "files": [
                    {
                        "name": "appsscript",
                        "type": "JSON",
                        "source": json.dumps(
                            {
                                "oauthScopes": [
                                    "https://www.googleapis.com/auth/script.external_request"
                                ],
                                "webapp": {
                                    "executeAs": "USER_DEPLOYING",
                                    "access": "ANYONE",
                                },
                            }
                        ),
                    },
                    {
                        "name": "Gateway",
                        "type": "SERVER_JS",
                        "source": r'''
function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  verifySignedEnvelope(body.signature, body.timestamp, body.nonce);
  computeHmacSha256Signature(body.signature);
  return minimalReadOnlyStatus();
}
''',
                    },
                ]
            }
        )
        report = audit_apps_script_source(source)
        blocking = [
            item for item in report["findings"]
            if item["severity"] in {"CRITICAL", "HIGH"}
        ]
        self.assertEqual(blocking, [])
        self.assertEqual(report["status"], "SOURCE_REVIEW_PASS")

    def test_private_hardened_bundle_passes(self) -> None:
        source = json.dumps(
            {
                "files": [
                    {
                        "name": "appsscript",
                        "type": "JSON",
                        "source": json.dumps(
                            {
                                "oauthScopes": [
                                    "https://www.googleapis.com/auth/script.projects"
                                ],
                                "webapp": {
                                    "executeAs": "USER_DEPLOYING",
                                    "access": "MYSELF",
                                },
                            }
                        ),
                    },
                    {
                        "name": "AdminRouter",
                        "type": "SERVER_JS",
                        "source": r'''
function SOVARA_ADMIN_dispatch(request) {
  verifySignedEnvelope(request.signature, request.timestamp, request.nonce);
  computeHmacSha256Signature(request.signature);
  claimNonce(request.nonce);
  return readOnlyStatus(request);
}
''',
                    },
                ]
            }
        )
        report = audit_apps_script_source(source)
        self.assertEqual(report["status"], "SOURCE_REVIEW_PASS")
        self.assertEqual(report["findings"], [])


class AppsScriptAuthorizationGateV21Tests(unittest.TestCase):
    def audit(self, *sources: str) -> dict:
        files = [
            {"name": f"File{index}", "type": "SERVER_JS", "source": source}
            for index, source in enumerate(sources, start=1)
        ]
        return audit_apps_script_source(json.dumps({"files": files}))

    def test_same_project_properties_are_not_independent_authority_anchor(self) -> None:
        report = self.audit(r"""
const PROVIDER_RECEIPT_ANCHOR_PROPERTY = 'ANCHOR';
function assertProviderMutationPermit(request) {
  const value = PropertiesService.getScriptProperties()
    .getProperty(PROVIDER_RECEIPT_ANCHOR_PROPERTY);
  return value === request.receiptSha256;
}
function claimEffectPermit(p) {}
// transactionId requestSha256 expectedBeforeHash expectedAfterHash oneUse
""")
        self.assertIn(
            "SAME_PROJECT_AUTHORITY_ANCHOR",
            {item["code"] for item in report["findings"]},
        )

    def test_incomplete_effect_permit_binding_fails_closed(self) -> None:
        report = self.audit(r"""
function assertProviderMutationPermit(request) { return request.action; }
function claimEffectPermit(p) {}
""")
        self.assertIn(
            "INCOMPLETE_EFFECT_PERMIT_BINDING",
            {item["code"] for item in report["findings"]},
        )

    def test_unclaimed_effect_permit_is_replay_unguarded(self) -> None:
        report = self.audit(r"""
function assertProviderMutationPermit(request) {
  return {transactionId: request.transactionId, requestSha256: request.requestSha256,
    expectedBeforeHash: request.expectedBeforeHash, expectedAfterHash: request.expectedAfterHash,
    oneUse: true};
}
""")
        self.assertIn(
            "EFFECT_PERMIT_REPLAY_UNGUARDED",
            {item["code"] for item in report["findings"]},
        )

    def test_semantic_readback_name_does_not_trigger_self_row_false_positive(self) -> None:
        report = self.audit(
            "function verify(){ return {providerSemanticReadbackVerified:true}; }"
        )
        self.assertNotIn(
            "SELF_READBACK_ONLY",
            {item["code"] for item in report["findings"]},
        )


if __name__ == "__main__":
    unittest.main()
