import unittest

from bubbles.command_bus import build_receipt
from bubbles.provider_worker import ProviderWorkerError, build_provider_receipt, validate_handoff


class BubblesProviderWorkerTests(unittest.TestCase):
    def event(self):
        return {
            "workflow_run": {
                "id": 12345,
                "name": "Bubbles Command Bus",
                "conclusion": "success",
                "event": "pull_request",
                "head_sha": "a" * 40,
                "actor": {"login": "mosianekk-lang"},
                "head_repository": {"full_name": "mosianekk-lang/Federation-Omega"},
            }
        }

    def handoff(self):
        return {
            "schema": "BUBBLES-COMMAND-RECEIPT-V1",
            "actor": "mosianekk-lang",
            "event_name": "pull_request",
            "state": "PROVIDER_PENDING",
            "command_sha256": "b" * 64,
            "request": {
                "adapter_id": "google_cloud_wif_plan",
                "action": "plan_wif",
                "effect": "READ",
                "target_alias": "GOOGLE_CLOUD_EXECUTION_PLANE",
            },
        }

    def plan(self):
        return {
            "receipt": "FEDOMEGA-WIF-PLAN",
            "state": "READY_FOR_VERIFICATION",
            "project": "sov-hybrid-suite",
            "project_number_observed": "257649435135",
            "region": "africa-south1",
            "service": "architron9",
            "workload_identity_provider": "projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/providers/github",
            "deployer_service_account": "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
            "active_account": "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
            "mutation_performed": False,
            "missing_controls": [],
            "missing_apis": [],
            "provider_state": "ACTIVE",
            "pool_state": "ACTIVE",
            "service_exists": True,
            "artifact_repository_exists": True,
        }

    def test_command_bus_emits_provider_pending_for_read_only_cloud_plan(self):
        raw = '{"schema":"BUBBLES-CONTROL-COMMAND-V1","adapter_id":"google_cloud_wif_plan","action":"plan_wif","effect":"READ","target_alias":"GOOGLE_CLOUD_EXECUTION_PLANE","payload":{}}'
        receipt = build_receipt(raw, actor="mosianekk-lang", event_name="pull_request", source_ref="PR")
        self.assertEqual("PROVIDER_PENDING", receipt["state"])
        self.assertFalse(receipt["execution"]["mutation_requested"])

    def test_write_effect_cannot_use_read_only_cloud_plan_adapter(self):
        raw = '{"schema":"BUBBLES-CONTROL-COMMAND-V1","adapter_id":"google_cloud_wif_plan","action":"plan_wif","effect":"LOW_RISK_WRITE","target_alias":"GOOGLE_CLOUD_EXECUTION_PLANE","payload":{}}'
        receipt = build_receipt(raw, actor="mosianekk-lang", event_name="pull_request", source_ref="PR")
        self.assertEqual("CONSTRAINT", receipt["state"])

    def test_valid_handoff_is_bound_to_owner_repo_and_exact_operation(self):
        result = validate_handoff(self.event(), self.handoff())
        self.assertEqual("VALIDATED", result["state"])
        self.assertEqual("GOOGLE_CLOUD_WIF_PLAN_READ_ONLY", result["provider_operation"])

    def test_foreign_actor_is_rejected_before_provider_work(self):
        event = self.event()
        event["workflow_run"]["actor"]["login"] = "other-user"
        with self.assertRaises(ProviderWorkerError):
            validate_handoff(event, self.handoff())

    def test_noncanonical_head_repository_is_rejected(self):
        event = self.event()
        event["workflow_run"]["head_repository"]["full_name"] = "fork/example"
        with self.assertRaises(ProviderWorkerError):
            validate_handoff(event, self.handoff())

    def test_provider_auth_failure_returns_constraint_without_mutation(self):
        validation = validate_handoff(self.event(), self.handoff())
        receipt = build_provider_receipt(
            validation=validation,
            auth_outcome="failure",
            setup_outcome="skipped",
            plan_outcome="skipped",
            plan_payload=None,
            provider_run_id="999",
            provider_ref="refs/heads/main",
        )
        self.assertEqual("CONSTRAINT", receipt["state"])
        self.assertFalse(receipt["mutation_performed"])
        self.assertFalse(receipt["provider_identity_verified"])

    def test_success_requires_exact_google_readback_and_no_mutation(self):
        validation = validate_handoff(self.event(), self.handoff())
        receipt = build_provider_receipt(
            validation=validation,
            auth_outcome="success",
            setup_outcome="success",
            plan_outcome="success",
            plan_payload=self.plan(),
            provider_run_id="999",
            provider_ref="refs/heads/main",
        )
        self.assertEqual("SUCCESS", receipt["state"])
        self.assertTrue(receipt["provider_identity_verified"])
        self.assertTrue(receipt["provider_inventory_readback"])
        self.assertFalse(receipt["mutation_performed"])

    def test_mutation_flag_in_plan_is_fail_closed(self):
        validation = validate_handoff(self.event(), self.handoff())
        plan = self.plan()
        plan["mutation_performed"] = True
        with self.assertRaises(ProviderWorkerError):
            build_provider_receipt(
                validation=validation,
                auth_outcome="success",
                setup_outcome="success",
                plan_outcome="success",
                plan_payload=plan,
                provider_run_id="999",
                provider_ref="refs/heads/main",
            )


if __name__ == "__main__":
    unittest.main()
