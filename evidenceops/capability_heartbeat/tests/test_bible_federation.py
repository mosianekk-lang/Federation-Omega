from __future__ import annotations

import unittest
from dataclasses import replace

from evidenceops.capability_heartbeat.bible_federation import BibleFederation
from evidenceops.capability_heartbeat.foundation.contracts import Authority, EventType
from evidenceops.capability_heartbeat.foundation.errors import ContractError
from evidenceops.capability_heartbeat.foundation.ledger import ImmutableEventLedger
from evidenceops.capability_heartbeat.foundation.respawn import RespawnManifest
from evidenceops.capability_heartbeat.tests.integration_helpers import (
    EXPIRES,
    NOW,
    OBSERVED,
    authority,
    envelope,
)


class BibleFederationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.authority = authority()
        self.federation = BibleFederation(self.authority)

    def test_registered_child_scaffold_inherits_scope_and_a0(self):
        child = self.federation.child_scaffold("NODE-EVIDENCEOPS")
        self.assertEqual(child["parent_node_id"], "NODE-ROOT")
        self.assertEqual(child["owner_code"], self.authority.policy.owner_code)
        self.assertEqual(child["matter_code"], self.authority.policy.matter_code)
        self.assertEqual(child["classification"], self.authority.policy.classification.value)
        self.assertEqual(child["authority_ceiling"], "A0")
        self.assertEqual(child["max_hops"], 3)
        self.assertFalse(child["effectful_execution_inherited"])
        self.assertFalse(any(child["live_awareness_flags"].values()))

    def test_unregistered_child_has_no_scaffold_or_inherited_capability(self):
        with self.assertRaisesRegex(ContractError, "NODE_NOT_REGISTERED"):
            self.federation.child_scaffold("NODE-ROGUE")

    def test_complete_signed_lineage_produces_fresh_destination_receipt(self):
        _, result, signed = envelope(self.authority)
        receipt = self.federation.accept(
            lineage=(signed,),
            destination_node_id="NODE-EVIDENCEOPS",
            observed_at=NOW,
        )
        self.assertEqual(receipt.envelope_id, signed.envelope_id)
        self.assertEqual(receipt.owner_code, self.authority.policy.owner_code)
        self.assertEqual(receipt.matter_code, self.authority.policy.matter_code)
        self.assertEqual(result.recommendations[0].role.value, "PREFERRED")

    def test_reconciliation_is_registry_readback_not_live_chat_claim(self):
        report = self.federation.reconcile(observed_at=NOW)
        self.assertEqual(report["registered_node_count"], 2)
        self.assertEqual(report["active_chat_count"], 0)
        self.assertFalse(report["scheduler_authority"])
        self.assertFalse(any(report["live_awareness_flags"].values()))

    def test_false_live_attachment_policy_is_rejected(self):
        with self.assertRaises(ContractError):
            replace(self.authority.policy, live_attachment=True)

    def test_respawn_semantic_readback_cross_binds_policy_registry_and_ledger(self):
        ledger = ImmutableEventLedger().append(
            event_type=EventType.NODE_REGISTERED,
            entity_code="NODE-ROOT",
            occurred_at=OBSERVED,
            control_generation=0,
            payload={"node_code": "NODE-ROOT", "state_code": "REGISTERED"},
        )
        manifest = RespawnManifest(
            manifest_code="RESPAWN-SYNTHETIC",
            master_node_id="NODE-ROOT",
            parent_transaction_id=ledger.tail_hash,
            policy_hash=self.authority.policy.policy_hash,
            registry_hash=self.authority.registry.registry_hash,
            ledger_tail_hash=ledger.tail_hash,
            ledger_event_count=1,
            root_node_generation=0,
            control_generation=0,
            authority_ceiling=Authority.A0,
            registration_receipts=tuple(
                sorted(item.registration_receipt for item in self.authority.registry.records)
            ),
            generated_at=NOW,
            expires_at="2026-08-02T12:04:00Z",
        )
        readback = self.federation.verify_respawn(
            manifest=manifest, ledger=ledger, observed_at=NOW
        )
        self.assertTrue(readback.valid)
        with self.assertRaises(ContractError):
            replace(manifest, system_wide_awareness=True)


if __name__ == "__main__":
    unittest.main()
