from __future__ import annotations

import tempfile
import unittest

from services.sol62_client_runtime.browser_carrier_resilience import (
    BrowserCarrierSupervisor,
    CarrierRegistration,
)
from services.sol62_client_runtime.browser_control_plane import (
    AUTHORITY_ACTOR,
    AUTHORITY_SOURCE_VERSION,
    BrowserControlIntent,
    BrowserControlPlane,
    BrowserEffectClass,
    safe_chatgpt_url,
)
from sol_61_runtime.sol_62 import (
    GatewayPolicy,
    Sol62Runtime,
    WorkloadIdentityPolicy,
)
from sol_61_runtime.sol_62_complete_client_runtime import Sol62CompleteClientRuntime
from sol_61_runtime.sol_62_frontier_primitives import (
    AuthorityError,
    AuthorityLease,
    ConstraintError,
)


class Sol62BrowserControlPlaneTests(unittest.TestCase):
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
        self.supervisor = BrowserCarrierSupervisor(self.client, heartbeat_ttl_seconds=60)
        self.control = BrowserControlPlane(
            self.client,
            lease_seconds=20,
            command_ttl_seconds=300,
        )
        self.capabilities = (
            "TAB_QUERY",
            "TAB_CREATE",
            "TAB_ACTIVATE",
            "TAB_CLOSE",
            "TAB_RELOAD",
            "HISTORY_BACK_FORWARD",
            "SAFE_CHATGPT_NAVIGATION",
            "SEMANTIC_DOM_SNAPSHOT",
            "SEMANTIC_FOCUS_SCROLL",
            "SEMANTIC_CLICK_GATED",
            "SEMANTIC_FILL_GATED",
            "DURABLE_LOCAL_OUTBOX",
        )
        self.supervisor.register(
            CarrierRegistration(
                carrier_id="carrier-1",
                owner_subject="owner",
                session_id="session-1",
                client_kind="CHATGPT_BROWSER_COMPANION",
                capabilities=self.capabilities,
                failure_domain="CHATGPT_BROWSER",
            ),
            now_epoch=self.now,
        )

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def test_chatgpt_origin_is_hard_bounded(self):
        self.assertEqual(safe_chatgpt_url("https://chatgpt.com/"), "https://chatgpt.com/")
        with self.assertRaises(ConstraintError):
            safe_chatgpt_url("https://example.com/")
        with self.assertRaises(ConstraintError):
            safe_chatgpt_url("http://chatgpt.com/")

    def test_capability_twin_is_nonauthoritative(self):
        twin = self.control.capability_twin(
            "carrier-1",
            owner_subject="owner",
            now_epoch=self.now,
        )
        self.assertTrue(twin["callable"])
        self.assertIn("TAB_CREATE", twin["capabilities"])
        self.assertFalse(twin["mission_authority"])
        self.assertFalse(twin["provider_authority"])
        self.assertFalse(twin["website_effect_authority"])

    def test_read_only_command_leases_and_verifies_with_readback(self):
        queued = self.control.enqueue(
            owner_subject="owner",
            carrier_id="carrier-1",
            intent=BrowserControlIntent(
                operation="LIST_TABS",
                effect_class=BrowserEffectClass.READ_ONLY,
                expected_readback={"count": 2},
                command_id="cmd-read",
            ),
            now_epoch=self.now,
        )
        self.assertEqual(queued["value"]["state"], "QUEUED")
        leased = self.control.next_command(
            "carrier-1",
            owner_subject="owner",
            now_epoch=self.now + 1,
        )
        self.assertEqual(leased["command_id"], "cmd-read")
        self.assertEqual(leased["state"], "LEASED")
        ack = self.control.acknowledge(
            "cmd-read",
            owner_subject="owner",
            carrier_id="carrier-1",
            status="VERIFIED",
            readback={"count": 2, "tabs": []},
            now_epoch=self.now + 2,
        )
        self.assertTrue(ack["browser_action_verified"])

    def test_local_browser_mutation_requires_observed_action(self):
        self.control.enqueue(
            owner_subject="owner",
            carrier_id="carrier-1",
            intent=BrowserControlIntent(
                operation="OPEN_NEW_CHAT",
                args={"url": "https://chatgpt.com/"},
                effect_class=BrowserEffectClass.LOCAL_BROWSER_STATE,
                command_id="cmd-local",
            ),
            now_epoch=self.now,
        )
        self.control.next_command(
            "carrier-1",
            owner_subject="owner",
            now_epoch=self.now + 1,
        )
        ack = self.control.acknowledge(
            "cmd-local",
            owner_subject="owner",
            carrier_id="carrier-1",
            status="VERIFIED",
            readback={"url": "https://chatgpt.com/"},
            now_epoch=self.now + 2,
        )
        self.assertFalse(ack["browser_action_verified"])
        self.assertEqual(
            ack["command"]["error_code"],
            "BROWSER_ACTION_NOT_OBSERVED",
        )

    def test_website_state_requires_action_bound_authority(self):
        with self.assertRaises(ConstraintError):
            self.control.enqueue(
                owner_subject="owner",
                carrier_id="carrier-1",
                intent=BrowserControlIntent(
                    operation="CLICK_ELEMENT",
                    args={"target": {"stable_id": "sem-submit"}},
                    effect_class=BrowserEffectClass.WEBSITE_STATE,
                    command_id="cmd-no-auth",
                ),
                now_epoch=self.now,
            )

    def test_website_state_consumes_exact_authority_before_effect(self):
        self.control.enqueue(
            owner_subject="owner",
            carrier_id="carrier-1",
            intent=BrowserControlIntent(
                operation="CLICK_ELEMENT",
                args={"target": {"stable_id": "sem-submit"}},
                effect_class=BrowserEffectClass.WEBSITE_STATE,
                authority_ref="lease-click",
                command_id="cmd-click",
            ),
            now_epoch=self.now,
        )
        leased = self.control.next_command(
            "carrier-1",
            owner_subject="owner",
            now_epoch=self.now + 1,
        )
        self.assertFalse(leased["authority_bound"])
        requirements = leased["authority_requirements"]

        self.runtime.control.create_authority_lease(
            AuthorityLease(
                lease_id="lease-click",
                action=requirements["action"],
                target=requirements["target"],
                actor=AUTHORITY_ACTOR,
                source_version=AUTHORITY_SOURCE_VERSION,
                issued_at_epoch=self.now,
                expires_at_epoch=self.now + 60,
                nonce="n1",
                max_uses=1,
            )
        )
        authorized = self.control.authorize_command(
            "cmd-click",
            owner_subject="owner",
            carrier_id="carrier-1",
            now_epoch=self.now + 2,
        )
        self.assertTrue(authorized["value"]["authority_bound"])
        self.assertEqual(authorized["value"]["authority_receipt"]["uses"], 1)

        ack = self.control.acknowledge(
            "cmd-click",
            owner_subject="owner",
            carrier_id="carrier-1",
            status="VERIFIED",
            readback={
                "action_observed": True,
                "semantic": {"verified": True},
            },
            now_epoch=self.now + 3,
        )
        self.assertTrue(ack["browser_action_verified"])

        with self.assertRaises(AuthorityError):
            self.control.authorize_command(
                "cmd-click",
                owner_subject="owner",
                carrier_id="carrier-1",
                now_epoch=self.now + 4,
            )

    def test_wrong_authority_contract_cannot_authorize_browser_effect(self):
        self.control.enqueue(
            owner_subject="owner",
            carrier_id="carrier-1",
            intent=BrowserControlIntent(
                operation="FILL_ELEMENT",
                args={
                    "target": {"stable_id": "sem-prompt"},
                    "value": "hello",
                },
                effect_class=BrowserEffectClass.WEBSITE_STATE,
                authority_ref="lease-wrong",
                command_id="cmd-fill",
            ),
            now_epoch=self.now,
        )
        self.control.next_command(
            "carrier-1",
            owner_subject="owner",
            now_epoch=self.now + 1,
        )
        self.runtime.control.create_authority_lease(
            AuthorityLease(
                lease_id="lease-wrong",
                action="CLICK_ELEMENT",
                target="chatgpt.com:CLICK_ELEMENT:sem-other",
                actor=AUTHORITY_ACTOR,
                source_version=AUTHORITY_SOURCE_VERSION,
                issued_at_epoch=self.now,
                expires_at_epoch=self.now + 60,
                nonce="n2",
                max_uses=1,
            )
        )
        with self.assertRaises(AuthorityError):
            self.control.authorize_command(
                "cmd-fill",
                owner_subject="owner",
                carrier_id="carrier-1",
                now_epoch=self.now + 2,
            )

    def test_idempotent_command_identity_rejects_semantic_collision(self):
        first = BrowserControlIntent(
            operation="CREATE_TAB",
            args={"url": "https://chatgpt.com/"},
            effect_class=BrowserEffectClass.LOCAL_BROWSER_STATE,
            command_id="cmd-idem",
        )
        self.control.enqueue(
            owner_subject="owner",
            carrier_id="carrier-1",
            intent=first,
            now_epoch=self.now,
        )
        self.control.enqueue(
            owner_subject="owner",
            carrier_id="carrier-1",
            intent=first,
            now_epoch=self.now + 1,
        )
        with self.assertRaises(ConstraintError):
            self.control.enqueue(
                owner_subject="owner",
                carrier_id="carrier-1",
                intent=BrowserControlIntent(
                    operation="NAVIGATE_CHATGPT",
                    args={"url": "https://chatgpt.com/?different=1"},
                    effect_class=BrowserEffectClass.LOCAL_BROWSER_STATE,
                    command_id="cmd-idem",
                ),
                now_epoch=self.now + 2,
            )

    def test_carrier_election_uses_capability_not_name(self):
        elected = self.control.elect_carrier(
            owner_subject="owner",
            operation="SEMANTIC_SNAPSHOT",
            now_epoch=self.now,
        )
        self.assertIsNotNone(elected)
        self.assertEqual(elected.carrier_id, "carrier-1")


if __name__ == "__main__":
    unittest.main()
