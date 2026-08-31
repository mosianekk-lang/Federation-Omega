import unittest

from benchmarking.cfbe_omega.bco_provider_identity_gap_compiler_v1 import (
    RouteState,
    compile_provider_identity_gap_graph,
)


CANONICAL = (
    "mosianekk-lang/Federation-Omega/.github/workflows/"
    "sovara-litellm-v2-3-provider-admission.yml@refs/heads/main"
)
BUBBLES = (
    "mosianekk-lang/Federation-Omega/.github/workflows/"
    "bubbles-command-bus.yml@refs/heads/main"
)
BCO = (
    "mosianekk-lang/Federation-Omega/.github/workflows/"
    "bco-provider-readback-continuity.yml@refs/heads/main"
)


class BCOProviderIdentityGapCompilerTests(unittest.TestCase):
    def _historical_wif(self):
        return {
            "active_account": "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
            "mutation_performed": False,
            "project": "sov-hybrid-suite",
            "project_number_observed": "257649435135",
            "provider_condition_sha256": "d743e2226750120ec20fef85613d07f696064a003b673470356979358fbb1e39",
            "provider_mapping_sha256": "58907481e403c27d72b944c27abc10a544259f3be5eab6aaf2c00e46b173577f",
            "provider_name": "projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/providers/github",
            "provider_state": "ACTIVE",
            "receipt": "FEDOMEGA-WIF-CLOUD-VERIFIED",
            "receipt_sha256": "470eb3f9e8388a553790882bbdd5a7aa86544b4de0aedc4d3b76974d53aa4ba0",
            "secret_payload_accessed": False,
            "state": "VERIFIED",
        }

    def _wif_provider(self):
        return {
            "attributeCondition": (
                "assertion.repository_id=='1292795464' && "
                "assertion.repository_owner_id=='261966700' && "
                "assertion.ref=='refs/heads/main' && "
                "assertion.job_workflow_ref=='mosianekk-lang/Federation-Omega/.github/workflows/"
                "sovara-litellm-v2-3-provider-admission.yml@refs/heads/main' && "
                "(assertion.event_name=='workflow_dispatch' || assertion.event_name=='push')"
            ),
            "attributeMapping": {
                "attribute.event_name": "assertion.event_name",
                "attribute.ref": "assertion.ref",
                "attribute.repository_id": "assertion.repository_id",
                "attribute.repository_owner_id": "assertion.repository_owner_id",
                "attribute.workflow_ref": "assertion.job_workflow_ref",
                "google.subject": "assertion.sub",
            },
            "name": "projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/providers/github",
            "state": "ACTIVE",
        }

    def _historical_adc(self, *, verified=False):
        if verified:
            return {
                "receipt": "FEDOMEGA-GEMINI-ADC-VERIFIED",
                "state": "VERIFIED",
                "mutation_performed": False,
                "missing_controls": [],
            }
        return {
            "deployer_service_account": "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
            "missing_controls": [
                "gemini_runtime_service_account",
                "aiplatform_user_binding",
                "service_usage_consumer_binding",
                "deployer_service_account_user_binding",
                "deployer_cloud_run_developer_binding",
            ],
            "mutation_performed": False,
            "receipt": "FEDOMEGA-GEMINI-ADC-VERIFICATION-FAILED",
            "runtime_service_account": "sv-gemini-runtime@sov-hybrid-suite.iam.gserviceaccount.com",
            "state": "NOT_VERIFIED",
        }

    def _current_provider(self, *, wif=False, scope="SOURCE_VALIDATION_ONLY"):
        return {
            "schema": "SOVARA-LITELLM-V2.3-GITHUB-WORKFLOW-RECEIPT-8",
            "execution_scope": scope,
            "g0_identity_adc_verified": False,
            "wif_verified": wif,
            "adc_verified": False,
            "source_sha": "f14379ccb672d26f00b131eb1a423667bf299722",
        }

    def _pfrd(self, *, direct_token=False, machine=False, secret_access=False):
        return {
            "schema": "SOVARA-OPERATOR-AUTH-RECOVERY-V3",
            "source_sha": "f14379ccb672d26f00b131eb1a423667bf299722",
            "credential_alias_presence": {
                "FO_ADMIN_TOKEN": direct_token,
                "GEMINI_API_KEY": False,
                "GCP_SA_KEY": False,
                "GCP_SERVICE_ACCOUNT_KEY": False,
                "GOOGLE_CREDENTIALS": False,
                "GOOGLE_SERVICE_ACCOUNT_KEY": False,
                "GCP_CREDENTIALS": False,
                "GOOGLE_GHA_CREDS_JSON": False,
                "GOOGLE_CLOUD_CREDENTIALS": False,
                "GCP_WIF_PAIR_CONFIGURED_NOT_USED": False,
                "GENERIC_WIF_PAIR_CONFIGURED_NOT_USED": False,
            },
            "google_machine_auth": {
                "authenticated": machine,
                "source_alias": "TEST_ROUTE" if machine else None,
            },
            "secret_manager": {
                "operator_token": {"accessible": True} if secret_access else None,
                "gemini_key": None,
            },
            "operator": {
                "token_present": direct_token or secret_access,
                "token_source": "github_actions_secret" if direct_token else ("google_secret_manager" if secret_access else "none"),
                "classification": (
                    "AUTHENTICATED_OPERATOR_READS_PROVEN_BIND_ABSENT"
                    if (direct_token or secret_access)
                    else "OPERATOR_TOKEN_UNAVAILABLE"
                ),
            },
            "overall_classification": (
                "SOVARA_OPERATOR_READ_MESH_PROVEN"
                if (direct_token or secret_access)
                else "SOVARA_PROVIDER_AUTHORITY_NOT_REESTABLISHED"
            ),
            "mutation_attempted": False,
            "secret_values_recorded": False,
        }

    def _compile(self, **overrides):
        values = dict(
            historical_wif_receipt=self._historical_wif(),
            historical_wif_provider_readback=self._wif_provider(),
            historical_adc_receipt=self._historical_adc(),
            current_provider_workflow_receipt=self._current_provider(),
            current_pfrd_receipt=self._pfrd(),
            requesting_workflow_refs=(CANONICAL, BUBBLES, BCO),
            current_bco_readback_receipt={"observed_level": "PUBLIC_REACHABILITY"},
            proof_refs={
                "historical_wif": "artifact:9682552700:WIF_G0_VERIFIED.json",
                "wif_provider": "artifact:9682552700:WIF_PROVIDER_READBACK.json",
                "historical_adc": "artifact:9682552700:GEMINI_ADC_VERIFIED.json",
                "current_provider": "artifact:9776749178:WORKFLOW_RECEIPT.json",
                "pfrd": "artifact:9776750925:OPERATOR_AUTH_RECOVERY_RECEIPT.json",
                "bco_readback": "artifact:9776771200:continuity.json",
            },
        )
        values.update(overrides)
        return compile_provider_identity_gap_graph(**values)

    def test_exact_evidence_compiles_distinct_identity_and_readback_gaps(self):
        report = self._compile()
        self.assertEqual("HOLD_PROVIDER_IDENTITY_GAPS", report.state)
        self.assertTrue(report.historical_wif_verified)
        self.assertEqual("CURRENT_HEAD_NOT_REFRESHED", report.current_wif_freshness)
        self.assertFalse(report.direct_operator_token_present)
        self.assertFalse(report.google_machine_authenticated)
        self.assertFalse(report.runtime_adc_verified)
        self.assertFalse(report.action_specific_authenticated_read_proven)

        gap_ids = {item.gap_id for item in report.gaps}
        self.assertIn("DIRECT_OPERATOR_TOKEN_UNAVAILABLE", gap_ids)
        self.assertIn("STATIC_GOOGLE_MACHINE_CREDENTIAL_UNAVAILABLE", gap_ids)
        self.assertIn("CANONICAL_WIF_FRESHNESS_UNPROVEN", gap_ids)
        self.assertIn("REQUESTING_WORKFLOW_NOT_MATCHING_WIF_ATTRIBUTE_CONDITION", gap_ids)
        self.assertIn("SECRET_MANAGER_TOKEN_RECOVERY_UNPROVEN", gap_ids)
        self.assertIn("RUNTIME_GOOGLE_ADC_UNVERIFIED", gap_ids)
        self.assertIn("ACTION_SPECIFIC_AUTHENTICATED_READ_UNPROVEN", gap_ids)

        adc = next(item for item in report.gaps if item.gap_id == "RUNTIME_GOOGLE_ADC_UNVERIFIED")
        self.assertEqual(5, len(adc.missing_controls))
        self.assertTrue(adc.authority_required_to_change)

    def test_workflow_identity_is_scoped_not_globally_inherited(self):
        report = self._compile()
        eligibility = dict(report.requesting_workflow_eligibility)
        self.assertTrue(eligibility[CANONICAL])
        self.assertFalse(eligibility[BUBBLES])
        self.assertFalse(eligibility[BCO])

        route = next(item for item in report.routes if item.route_id == "CANONICAL_WIF")
        self.assertEqual(RouteState.HISTORICALLY_PROVEN_FRESHNESS_OPEN, route.state)
        self.assertEqual((CANONICAL,), route.eligible_workflows)
        self.assertEqual((BCO, BUBBLES), route.ineligible_workflows)
        self.assertIn("REQUESTING_WORKFLOW_NOT_MATCHING_WIF_ATTRIBUTE_CONDITION", route.blockers)

    def test_fresh_canonical_wif_does_not_make_ineligible_workflow_eligible(self):
        report = self._compile(
            current_provider_workflow_receipt=self._current_provider(
                wif=True,
                scope="G0_READ_ONLY_VERIFY",
            )
        )
        self.assertEqual("CURRENT_HEAD_VERIFIED", report.current_wif_freshness)
        route = next(item for item in report.routes if item.route_id == "CANONICAL_WIF")
        self.assertEqual(RouteState.PROVEN, route.state)
        self.assertIn("REQUESTING_WORKFLOW_NOT_MATCHING_WIF_ATTRIBUTE_CONDITION", route.blockers)
        self.assertFalse(dict(report.requesting_workflow_eligibility)[BCO])

    def test_action_specific_readback_is_independent_of_adc_and_wif_freshness(self):
        report = self._compile(
            current_bco_readback_receipt={"observed_level": "ACTION_SPECIFIC_AUTHENTICATED_READ"}
        )
        self.assertTrue(report.action_specific_authenticated_read_proven)
        read_route = next(item for item in report.routes if item.route_id == "ACTION_SPECIFIC_AUTHENTICATED_READBACK")
        self.assertEqual(RouteState.PROVEN, read_route.state)
        gap_ids = {item.gap_id for item in report.gaps}
        self.assertNotIn("ACTION_SPECIFIC_AUTHENTICATED_READ_UNPROVEN", gap_ids)
        self.assertIn("RUNTIME_GOOGLE_ADC_UNVERIFIED", gap_ids)
        self.assertIn("CANONICAL_WIF_FRESHNESS_UNPROVEN", gap_ids)

    def test_secret_manager_route_requires_machine_identity_before_token_recovery(self):
        blocked = self._compile()
        route = next(item for item in blocked.routes if item.route_id == "SECRET_MANAGER_OPERATOR_TOKEN_RECOVERY")
        self.assertEqual(RouteState.BLOCKED, route.state)
        self.assertIn("GOOGLE_MACHINE_AUTH_NOT_PROVEN", route.blockers)

        available = self._compile(current_pfrd_receipt=self._pfrd(machine=True, secret_access=True))
        route = next(item for item in available.routes if item.route_id == "SECRET_MANAGER_OPERATOR_TOKEN_RECOVERY")
        self.assertEqual(RouteState.AVAILABLE_UNPROVEN, route.state)
        self.assertIn("ACTION_SPECIFIC_AUTHENTICATED_READ_UNPROVEN", route.blockers)

    def test_receipt_mutation_or_secret_access_boundaries_fail_closed(self):
        bad_wif = self._historical_wif()
        bad_wif["mutation_performed"] = True
        with self.assertRaisesRegex(ValueError, "MUTATION_BOUNDARY:historical_wif"):
            self._compile(historical_wif_receipt=bad_wif)

        bad_pfrd = self._pfrd()
        bad_pfrd["secret_values_recorded"] = True
        with self.assertRaisesRegex(ValueError, "SECRET_BOUNDARY:pfrd"):
            self._compile(current_pfrd_receipt=bad_pfrd)


if __name__ == "__main__":
    unittest.main()
