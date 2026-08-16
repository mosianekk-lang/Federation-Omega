import tempfile
import unittest
from pathlib import Path

from governance.external_action_firewall import (
    ExternalActionFirewall,
    FileLeaseStore,
    FirewallDecision,
)


class ExternalActionFirewallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = FileLeaseStore(Path(self.tmp.name) / "leases.json")
        self.now = 1_700_000_000
        self.firewall = ExternalActionFirewall(
            secret=b"unit-test-secret",
            store=self.store,
            ttl_seconds=600,
            clock=lambda: self.now,
        )
        self.target = {
            "adapter": "gmail",
            "draft_id": "draft-123",
            "recipient": "nlp@ccma.org.za",
            "subject": "Status request",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_update_status_is_hard_read_only(self):
        receipt = self.firewall.prepare(
            user_turn_id="t1",
            user_text="Update all status",
            action="send_draft",
            target=self.target,
        )
        self.assertEqual(receipt.decision, FirewallDecision.DENY.value)
        self.assertIn("Read-only", receipt.reason)

    def test_mixed_audit_and_send_fails_closed(self):
        receipt = self.firewall.prepare(
            user_turn_id="t1",
            user_text="Audit the case and send the draft",
            action="send_draft",
            target=self.target,
        )
        self.assertEqual(receipt.decision, FirewallDecision.DENY.value)

    def test_explicit_send_only_prepares_lease(self):
        receipt = self.firewall.prepare(
            user_turn_id="t1",
            user_text="Send the CCMA draft",
            action="send_draft",
            target=self.target,
        )
        self.assertEqual(receipt.decision, FirewallDecision.PREPARED.value)
        self.assertIsNotNone(receipt.lease_token)

    def test_two_phase_exact_commit_allows_once(self):
        prepared = self.firewall.prepare(
            user_turn_id="t1",
            user_text="Send the CCMA draft",
            action="send_draft",
            target=self.target,
        )
        committed = self.firewall.commit(
            user_turn_id="t2",
            user_text=f"EXECUTE {prepared.lease_token}",
            lease_token=prepared.lease_token,
            action="send_draft",
            target=self.target,
        )
        self.assertEqual(committed.decision, FirewallDecision.ALLOW_ONCE.value)

        replay = self.firewall.commit(
            user_turn_id="t3",
            user_text=f"EXECUTE {prepared.lease_token}",
            lease_token=prepared.lease_token,
            action="send_draft",
            target=self.target,
        )
        self.assertEqual(replay.decision, FirewallDecision.DENY.value)
        self.assertIn("consumed", replay.reason)

    def test_same_turn_execution_is_blocked(self):
        prepared = self.firewall.prepare(
            user_turn_id="t1",
            user_text="Send the CCMA draft",
            action="send_draft",
            target=self.target,
        )
        committed = self.firewall.commit(
            user_turn_id="t1",
            user_text=f"EXECUTE {prepared.lease_token}",
            lease_token=prepared.lease_token,
            action="send_draft",
            target=self.target,
        )
        self.assertEqual(committed.decision, FirewallDecision.DENY.value)
        self.assertIn("Same-turn", committed.reason)

    def test_target_change_is_blocked(self):
        prepared = self.firewall.prepare(
            user_turn_id="t1",
            user_text="Send the CCMA draft",
            action="send_draft",
            target=self.target,
        )
        changed = dict(self.target)
        changed["recipient"] = "someone-else@example.org"
        committed = self.firewall.commit(
            user_turn_id="t2",
            user_text=f"EXECUTE {prepared.lease_token}",
            lease_token=prepared.lease_token,
            action="send_draft",
            target=changed,
        )
        self.assertEqual(committed.decision, FirewallDecision.DENY.value)
        self.assertIn("differs", committed.reason)

    def test_stale_prior_approval_without_lease_cannot_execute(self):
        committed = self.firewall.commit(
            user_turn_id="t9",
            user_text="EXECUTE made-up-token",
            lease_token="made-up-token",
            action="send_draft",
            target=self.target,
        )
        self.assertEqual(committed.decision, FirewallDecision.DENY.value)

    def test_existing_sent_counterpart_blocks_duplicate_send(self):
        receipt = self.firewall.prepare(
            user_turn_id="t1",
            user_text="Send the CCMA draft",
            action="send_draft",
            target=self.target,
            provider_state={"sent_counterpart_exists": True},
        )
        self.assertEqual(receipt.decision, FirewallDecision.DENY.value)
        self.assertIn("duplicate", receipt.reason.lower())

    def test_resend_requires_explicit_resend_and_new_turn(self):
        prepared = self.firewall.prepare(
            user_turn_id="t1",
            user_text="RESEND the CCMA draft",
            action="send_draft",
            target=self.target,
            provider_state={"sent_counterpart_exists": True},
        )
        self.assertEqual(prepared.decision, FirewallDecision.PREPARED.value)
        committed = self.firewall.commit(
            user_turn_id="t2",
            user_text=f"EXECUTE {prepared.lease_token}",
            lease_token=prepared.lease_token,
            action="send_draft",
            target=self.target,
            provider_state={"sent_counterpart_exists": True},
        )
        self.assertEqual(committed.decision, FirewallDecision.ALLOW_ONCE.value)

    def test_expired_lease_is_blocked(self):
        prepared = self.firewall.prepare(
            user_turn_id="t1",
            user_text="Send the CCMA draft",
            action="send_draft",
            target=self.target,
        )
        self.now += 601
        committed = self.firewall.commit(
            user_turn_id="t2",
            user_text=f"EXECUTE {prepared.lease_token}",
            lease_token=prepared.lease_token,
            action="send_draft",
            target=self.target,
        )
        self.assertEqual(committed.decision, FirewallDecision.DENY.value)
        self.assertIn("expired", committed.reason.lower())


if __name__ == "__main__":
    unittest.main()
