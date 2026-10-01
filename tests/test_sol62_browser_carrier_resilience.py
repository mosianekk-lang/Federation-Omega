from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from services.sol62_client_runtime.browser_carrier_resilience import (
    BrowserCarrierSupervisor,
    CarrierRegistration,
    FailureDisposition,
    classify_carrier_failure,
)
from sol_61_runtime.sol_62 import GatewayPolicy, MissionSpec, Sol62Runtime, WorkloadIdentityPolicy
from sol_61_runtime.sol_62_complete_client_runtime import (
    ConstraintDisposition,
    Sol62CompleteClientRuntime,
    classify_provider_constraint,
)


class BrowserCarrierResilienceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 2_000_000_000
        self.runtime = Sol62Runtime(
            self.tmp.name,
            gateway_policy=GatewayPolicy("sol-gateway", "sol-6.2"),
            identity_policy=WorkloadIdentityPolicy(
                allowed_issuers={"issuer"},
                audience="aud",
                subject_prefix="sub:",
                max_ttl_seconds=600,
            ),
        )
        self.client = Sol62CompleteClientRuntime(self.runtime)
        self.supervisor = BrowserCarrierSupervisor(self.client, heartbeat_ttl_seconds=45)
        self.runtime.register_mission(
            MissionSpec(
                "m1",
                "continue despite browser/chat carrier failure",
                {"state": "OPEN"},
                {"state": "DONE"},
            )
        )
        self.client.bind_mission("m1", owner_subject="owner")

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def register(
        self,
        carrier_id: str,
        *,
        priority: int = 50,
        at: int | None = None,
        client_kind: str = "CHATGPT_BROWSER",
        failure_domain: str = "CHATGPT_BROWSER",
    ):
        return self.supervisor.register(
            CarrierRegistration(
                carrier_id=carrier_id,
                owner_subject="owner",
                session_id="session-" + carrier_id,
                client_kind=client_kind,
                priority=priority,
                conversation_ref_hash="hash-" + carrier_id,
                failure_domain=failure_domain,
            ),
            now_epoch=self.now if at is None else at,
        )

    def test_screenshot_failure_is_route_local_not_mission_terminal(self):
        failure = classify_carrier_failure("CHATGPT_CONVERSATION_LOAD_FAILED")
        self.assertEqual(failure.disposition, FailureDisposition.ROUTE_LOCAL)
        self.assertFalse(failure.mission_terminal)
        self.assertFalse(failure.goal_mutation_allowed)
        self.assertFalse(failure.bypass_allowed)
        self.assertFalse(failure.retry_same_carrier)

    def test_failed_conversation_elects_healthier_replacement_and_hydrates_same_mission(self):
        self.register("dead", priority=100)
        self.register("replacement", priority=90)
        self.supervisor.attach_mission(
            "m1",
            owner_subject="owner",
            carrier_id="dead",
            now_epoch=self.now,
        )
        result = self.supervisor.failover(
            "m1",
            owner_subject="owner",
            failed_carrier_id="dead",
            failure_code="CHATGPT_CONVERSATION_LOAD_FAILED",
            now_epoch=self.now + 1,
        )
        self.assertEqual(result["state"], "HYDRATE_REPLACEMENT")
        self.assertEqual(result["replacement_carrier_id"], "replacement")
        self.assertFalse(result["mission_terminal"])
        self.assertFalse(result["effect_replay_allowed"])
        self.assertTrue(result["effect_readback_before_retry"])
        self.assertEqual(result["hydration"]["mission_id"], "m1")
        self.assertEqual(result["hydration"]["carrier_id"], "replacement")
        self.assertTrue(result["hydration"]["conversation_identity_is_nonauthoritative"])
        self.assertFalse(result["hydration"]["provider_credentials_in_packet"])

    def test_stale_carrier_is_not_elected(self):
        self.register("stale", priority=100, at=self.now - 100)
        self.register("fresh", priority=10, at=self.now)
        elected = self.supervisor.elect(owner_subject="owner", now_epoch=self.now)
        self.assertEqual(elected["carrier_id"], "fresh")
    def test_cross_domain_carrier_beats_same_domain_higher_priority(self):
        self.register("dead", priority=100, failure_domain="CHATGPT_BROWSER")
        self.register("same-domain", priority=99, failure_domain="CHATGPT_BROWSER")
        self.register(
            "fuse-web",
            priority=10,
            client_kind="FUSE_WEB",
            failure_domain="FUSE_OWNED_WEB",
        )
        self.supervisor.attach_mission(
            "m1",
            owner_subject="owner",
            carrier_id="dead",
            now_epoch=self.now,
        )
        result = self.supervisor.failover(
            "m1",
            owner_subject="owner",
            failed_carrier_id="dead",
            failure_code="CHATGPT_CONVERSATION_LOAD_FAILED",
            now_epoch=self.now + 1,
        )
        self.assertEqual(result["replacement_carrier_id"], "fuse-web")

    def test_same_domain_fallback_remains_available_when_no_independent_carrier_exists(self):
        self.register("dead", priority=100, failure_domain="CHATGPT_BROWSER")
        self.register("same-domain", priority=50, failure_domain="CHATGPT_BROWSER")
        selected = self.supervisor.elect(
            owner_subject="owner",
            now_epoch=self.now,
            exclude_carrier_id="dead",
            avoid_failure_domain="CHATGPT_BROWSER",
        )
        self.assertEqual(selected["carrier_id"], "same-domain")

    def test_federation_status_reports_failure_domain_redundancy(self):
        self.register("edge", failure_domain="CHATGPT_BROWSER")
        self.register(
            "windows",
            client_kind="WINDOWS_COMPANION",
            failure_domain="WINDOWS_NATIVE",
        )
        status = self.supervisor.federation_status(
            owner_subject="owner",
            now_epoch=self.now,
        )
        self.assertEqual(status["live_failure_domains"], 2)
        self.assertTrue(status["cross_domain_failover_ready"])
        self.assertFalse(status["mission_authority_in_carrier"])
        self.assertFalse(status["provider_authority_in_carrier"])

    def test_carrier_epoch_increases_on_rebind_to_reject_stale_tab(self):
        first = self.register("tab-a")
        second = self.register("tab-a")
        self.assertGreater(
            second["value"]["carrier_epoch"],
            first["value"]["carrier_epoch"],
        )

    def test_possible_effect_forces_readback_before_replacement_execution(self):
        self.register("dead", priority=100)
        self.register("replacement", priority=90)
        self.supervisor.attach_mission(
            "m1",
            owner_subject="owner",
            carrier_id="dead",
            now_epoch=self.now,
        )
        with patch.object(
            self.client,
            "_inflight_for_mission",
            return_value=[{"effect_id": "e1", "state": "DISPATCHED"}],
        ):
            result = self.supervisor.failover(
                "m1",
                owner_subject="owner",
                failed_carrier_id="dead",
                failure_code="CHATGPT_CONVERSATION_LOAD_FAILED",
                now_epoch=self.now + 1,
            )
        self.assertEqual(result["state"], "WAITING_EFFECT_READBACK")
        self.assertFalse(result["effect_replay_allowed"])
        self.assertTrue(result["inflight_effects"])
    def test_core_runtime_classifier_matches_browser_supervisor(self):
        result = classify_provider_constraint(
            "CHATGPT_CONVERSATION_LOAD_FAILED",
            "Could not load this ChatGPT conversation",
        )
        self.assertEqual(result.disposition, ConstraintDisposition.ROUTE_LOCAL)
        self.assertFalse(result.mission_terminal)
        self.assertTrue(result.retry_requires_changed_route)
        self.assertFalse(result.goal_mutation_allowed)
    def test_duplicate_failover_event_is_idempotent(self):
        self.register("dead", priority=100)
        self.register("replacement", priority=90)
        self.supervisor.attach_mission(
            "m1",
            owner_subject="owner",
            carrier_id="dead",
            now_epoch=self.now,
        )
        first = self.supervisor.failover(
            "m1",
            owner_subject="owner",
            failed_carrier_id="dead",
            failure_code="CHATGPT_CONVERSATION_LOAD_FAILED",
            event_id="evt-1",
            now_epoch=self.now + 1,
        )
        second = self.supervisor.failover(
            "m1",
            owner_subject="owner",
            failed_carrier_id="dead",
            failure_code="CHATGPT_CONVERSATION_LOAD_FAILED",
            event_id="evt-1",
            now_epoch=self.now + 2,
        )
        self.assertEqual(first["replacement_carrier_id"], second["replacement_carrier_id"])
        self.assertEqual(
            first["attachment"]["value"]["mission_carrier_epoch"],
            second["attachment"]["value"]["mission_carrier_epoch"],
        )
        receipts = self.client._rows("sol62.browser.event_receipt")
        self.assertTrue(any(row["value"]["event_id"] == "evt-1" for row in receipts))

    def test_hard_boundary_never_becomes_bypass_authority(self):
        failure = classify_carrier_failure("SAFETY_BOUNDARY")
        self.assertEqual(failure.disposition, FailureDisposition.HARD_BOUNDARY)
        self.assertFalse(failure.bypass_allowed)
        self.assertFalse(failure.goal_mutation_allowed)


    def test_stream_cache_expired_is_route_local_not_mission_terminal(self):
        failure = classify_carrier_failure("STREAM_CACHE_EXPIRED")
        self.assertEqual(failure.disposition, FailureDisposition.ROUTE_LOCAL)
        self.assertFalse(failure.mission_terminal)
        self.assertFalse(failure.retry_same_carrier)

    def test_no_replacement_browser_requests_durable_sol_continuation(self):
        self.register("c1", at=self.now)
        self.supervisor.attach_mission(
            "m1",
            owner_subject="owner",
            carrier_id="c1",
            now_epoch=self.now,
        )
        result = self.supervisor.failover(
            "m1",
            owner_subject="owner",
            failed_carrier_id="c1",
            failure_code="STREAM_CACHE_EXPIRED",
            event_id="stream-cache-1",
            now_epoch=self.now,
        )
        self.assertEqual(result["state"], "DURABLE_CONTINUATION_READY")
        self.assertTrue(result["durable_continuation_required"])
        self.assertEqual(result["continuation_mode"], "SOL62_GENESIS_WAKE")
        self.assertFalse(result["owner_retry_required"])
        self.assertFalse(result["ui_retry_required"])
        self.assertTrue(result["resume_packet"]["replay_guard_verified"])



if __name__ == "__main__":
    unittest.main()
