import unittest

from security.apps_script_fleet_guard import Severity, analyze_backup


def fixture():
    return {
        "files": [
            {"name": "appsscript", "source": '{"oauthScopes":["https://www.googleapis.com/auth/cloud-platform","https://www.googleapis.com/auth/script.projects"],"webapp":{"executeAs":"USER_DEPLOYING","access":"ANYONE"}}'},
            {"name": "Code", "source": '''
const CONFIG={CLOUD_PROJECT_NUMBER:"516699068552",APPROVAL_KEY:"APPROVED"};
function doGet(e){const key=getParam_(e,"key");}
function doPost(e){enqueue({approvalKey:body.approvalKey||CONFIG.APPROVAL_KEY});}
function enqueue(){sheet.appendRow([normalized.approvalKey]);}
function callRuntime(){const ok=httpStatus>=200&&httpStatus<300&&body.status!=="FAILED";}
function ARCHON_enableRequiredApis(){return enableService_();}
function ARCHON_codeApply(x){return x;}
function ARCHON_codeRollback(x){return x;}
const proof={commandRowFound:true,resultJsonPresent:true,completedAtPresent:true};
'''},
            {"name": "Gateway", "source": '''
function doGet(){} function doPost(){}
function auth(){const x=PropertiesService.getScriptProperties().getProperty('OMEGA_GATEWAY_TOKEN');}
'''},
            {"name": "SignedManager", "source": '''
function ARCHON_codeApply(x){verifySignedRequest(x);}
function ARCHON_codeRollback(x){computeHmacSha256Signature(x);}
'''},
            {"name": "Omega", "source": '''
function call(){const u=p.getProperty(OMEGA_CONTROL.URL_PROPERTY);return f(u,{headers:{Authorization: 'Bearer '+token}});}
'''},
        ]
    }


def result():
    return analyze_backup(
        fixture(),
        canonical_target_project="257649435135",
        legacy_projects={"516699068552", "516690968552", "979287460558"},
    )


def codes():
    return {item.code for item in result().findings}


class AppsScriptFleetGuardTests(unittest.TestCase):
    def test_fails_closed_and_never_grants_provider_authority(self):
        value = result()
        self.assertEqual(value.status, "SECURITY_HOLD")
        self.assertFalse(value.provider_authority_proven)
        self.assertFalse(value.provider_mutation_authorized)

    def test_detects_public_privileged_ingress_and_approval_bypass(self):
        self.assertTrue(
            {"PUBLIC_PRIVILEGED_WEBAPP", "STATIC_APPROVAL_SECRET", "DEFAULT_APPROVAL_BYPASS"}
            <= codes()
        )

    def test_detects_secret_query_and_persistence(self):
        self.assertTrue(
            {"SECRET_IN_QUERY_PARAMETER", "APPROVAL_CREDENTIAL_PERSISTED"}
            <= codes()
        )

    def test_detects_global_collisions_and_mixed_auth_mutators(self):
        value = result()
        self.assertGreaterEqual(
            sum(item.code == "DUPLICATE_GLOBAL_HANDLER" for item in value.findings),
            4,
        )
        self.assertIn("MIXED_AUTH_MUTATOR_SHADOWING", codes())

    def test_detects_transport_self_certification(self):
        self.assertTrue(
            {"GENERIC_TRANSPORT_SUCCESS_PROMOTION", "SELF_READBACK_ONLY"}
            <= codes()
        )

    def test_detects_legacy_mutation_default_and_bearer_destination(self):
        self.assertTrue(
            {"LEGACY_PROJECT_MUTATION_DEFAULT", "CONFIGURABLE_BEARER_DESTINATION"}
            <= codes()
        )

    def test_detects_token_policy_not_enforced(self):
        self.assertIn("TOKEN_STRENGTH_NOT_ENFORCED", codes())

    def test_clean_minimal_private_router_passes(self):
        clean = {"files": [
            {"name": "appsscript", "source": '{"oauthScopes":["https://www.googleapis.com/auth/spreadsheets"],"webapp":{"executeAs":"USER_DEPLOYING","access":"MYSELF"}}'},
            {"name": "SecureRouter", "source": "function doPost(e){verifySignedRequest(e);}"},
        ]}
        value = analyze_backup(
            clean,
            canonical_target_project="257649435135",
            legacy_projects={"516699068552"},
        )
        self.assertEqual(value.status, "SOURCE_REVIEW_PASS")
        self.assertEqual(value.findings, ())

    def test_critical_findings_remain_critical(self):
        self.assertTrue(
            any(item.severity == Severity.CRITICAL for item in result().findings)
        )


if __name__ == "__main__":
    unittest.main()
