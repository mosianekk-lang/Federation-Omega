from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from evidenceops.capability_heartbeat.foundation.adapters import (
    read_formation_state,
    read_local_bible,
    read_local_repo,
)
from evidenceops.capability_heartbeat.foundation.adapters.common import make_observation
from evidenceops.capability_heartbeat.foundation.contracts import Authority, BlockerCode, CapabilityStatus, EventType, digest
from evidenceops.capability_heartbeat.foundation.errors import ContractError, PrivacyError
from evidenceops.capability_heartbeat.foundation.ledger import GENESIS_HASH, ImmutableEventLedger, LedgerEvent
from evidenceops.capability_heartbeat.foundation.master_bible import MasterBiblePolicy
from evidenceops.capability_heartbeat.foundation.respawn import RespawnManifest, verify_respawn

from evidenceops.capability_heartbeat.foundation_tests.helpers import (
    EXPIRES,
    MATTER,
    NOW,
    OBSERVED,
    OWNER,
    hash_of,
    ledger,
    registry_with_chain,
    stop_control,
)

RESPAWN_EXPIRES = "2026-08-02T12:04:00Z"


class LedgerTests(unittest.TestCase):
    def test_control_generation_rollback_is_rejected_by_append_verify_and_readback(self):
        first = ImmutableEventLedger().append(
            event_type=EventType.NODE_REGISTERED,
            entity_code="NODE-ROOT",
            occurred_at=OBSERVED,
            control_generation=1,
            payload={"node_code": "NODE-ROOT", "state_code": "REGISTERED"},
        )
        with self.assertRaisesRegex(ContractError, "CONTROL_GENERATION_ROLLBACK"):
            first.append(
                event_type=EventType.NODE_REGISTERED,
                entity_code="NODE-CHILD-1",
                occurred_at="2026-08-02T12:00:01Z",
                control_generation=0,
                payload={"node_code": "NODE-CHILD-1", "state_code": "REGISTERED"},
            )
        provisional = LedgerEvent(
            sequence=2,
            event_type=EventType.NODE_REGISTERED,
            entity_code="NODE-CHILD-1",
            occurred_at="2026-08-02T12:00:01Z",
            control_generation=0,
            payload_hash=hash_of("ROLLBACK-PAYLOAD"),
            previous_hash=first.tail_hash,
            event_hash=GENESIS_HASH,
        )
        forged = replace(provisional, event_hash=digest(provisional.hash_body()))
        rollback_ledger = ImmutableEventLedger(first.events + (forged,))
        self.assertFalse(rollback_ledger.verify())
        self.assertFalse(
            rollback_ledger.semantic_readback(
                expected_count=2,
                expected_tail=forged.event_hash,
                expected_generation=0,
            ).valid
        )

    def test_strict_json_decoder_rejects_duplicate_keys(self):
        line = ledger().to_jsonl().strip()
        duplicate = line[:-1] + ',"sequence":1}'
        with self.assertRaisesRegex(ContractError, "INVALID_LEDGER_LINE"):
            ImmutableEventLedger.from_jsonl(duplicate)
    def test_append_returns_new_immutable_ledger(self):
        original = ImmutableEventLedger()
        updated = ledger()
        self.assertEqual(original.events, ())
        self.assertEqual(len(updated.events), 1)
        self.assertTrue(updated.verify())

    def test_jsonl_round_trip_and_semantic_readback(self):
        value = ledger().append(
            event_type=EventType.RECEIPT_RECORDED,
            entity_code="NODE-ROOT",
            occurred_at="2026-08-02T12:00:05Z",
            control_generation=0,
            payload={"receipt_hash": hash_of("RECEIPT-RECORDED"), "node_code": "NODE-ROOT"},
        )
        restored = ImmutableEventLedger.from_jsonl(value.to_jsonl())
        readback = restored.semantic_readback(
            expected_count=2,
            expected_tail=value.tail_hash,
            expected_generation=0,
        )
        self.assertTrue(readback.valid)
        self.assertEqual(restored, value)

    def test_tampered_jsonl_rejected(self):
        text = ledger().to_jsonl().replace("NODE-ROOT", "NODE-FAKE")
        with self.assertRaisesRegex(ContractError, "CHAIN_INVALID"):
            ImmutableEventLedger.from_jsonl(text)

    def test_sensitive_ledger_payload_rejected(self):
        with self.assertRaises(PrivacyError):
            ImmutableEventLedger().append(
                event_type=EventType.NODE_REGISTERED,
                entity_code="NODE-ROOT",
                occurred_at=OBSERVED,
                control_generation=0,
                payload={"chat_body": "raw"},
            )

    def test_generic_ledger_field_cannot_hide_legal_or_personal_prose(self):
        for payload in (
            {"note": "PERSON FULL NAME"},
            {"node_code": "PERSON FULL NAME", "state_code": "REGISTERED"},
            {"node_code": "NODE-ROOT", "state_code": "API-KEY=VALUE"},
        ):
            with self.subTest(payload=payload), self.assertRaises(PrivacyError):
                ImmutableEventLedger().append(
                    event_type=EventType.NODE_REGISTERED,
                    entity_code="NODE-ROOT",
                    occurred_at=OBSERVED,
                    control_generation=0,
                    payload=payload,
                )


class RespawnTests(unittest.TestCase):
    def test_respawn_requires_every_registry_record_fresh_at_now(self):
        policy, registry, nodes = registry_with_chain(2)
        event_ledger = ledger()
        expired_child = replace(nodes[1], expires_at="2026-08-02T12:00:05Z")
        expired_registry = type(registry)((nodes[0], expired_child))
        manifest = RespawnManifest(
            manifest_code="RESPAWN-FRESH",
            master_node_id=policy.root_node_id,
            parent_transaction_id=event_ledger.events[-1].event_hash,
            policy_hash=policy.policy_hash,
            registry_hash=expired_registry.registry_hash,
            ledger_tail_hash=event_ledger.tail_hash,
            ledger_event_count=1,
            root_node_generation=0,
            control_generation=0,
            authority_ceiling=Authority.A0,
            registration_receipts=tuple(
                item.registration_receipt for item in expired_registry.records
            ),
            generated_at=OBSERVED,
            expires_at=RESPAWN_EXPIRES,
        )
        self.assertFalse(
            verify_respawn(
                manifest=manifest,
                policy=policy,
                registry=expired_registry,
                ledger=event_ledger,
                stop_control=stop_control(),
                now=NOW,
            ).valid
        )

    def test_master_bible_policy_hash_is_deterministically_recomputed(self):
        policy, _, _ = registry_with_chain(1)
        with self.assertRaisesRegex(ContractError, "POLICY_HASH_MISMATCH"):
            replace(policy, policy_hash=hash_of("CALLER-SUPPLIED-POLICY"))
    def test_master_bible_respawn_semantic_readback(self):
        policy, registry, _ = registry_with_chain(2)
        event_ledger = ledger()
        manifest = RespawnManifest(
            manifest_code="RESPAWN-001",
            master_node_id=policy.root_node_id,
            parent_transaction_id=event_ledger.events[-1].event_hash,
            policy_hash=policy.policy_hash,
            registry_hash=registry.registry_hash,
            ledger_tail_hash=event_ledger.tail_hash,
            ledger_event_count=1,
            root_node_generation=0,
            control_generation=0,
            authority_ceiling=Authority.A0,
            registration_receipts=tuple(item.registration_receipt for item in registry.records),
            generated_at=OBSERVED,
            expires_at=RESPAWN_EXPIRES,
        )
        result = verify_respawn(
            manifest=manifest,
            policy=policy,
            registry=registry,
            ledger=event_ledger,
            stop_control=stop_control(),
            now=NOW,
        )
        self.assertTrue(result.valid)

    def test_respawn_cannot_claim_live_attachment(self):
        policy, registry, _ = registry_with_chain(1)
        with self.assertRaisesRegex(ContractError, "UNPROVEN_LIVE_CAPABILITY_CLAIM"):
            RespawnManifest(
                manifest_code="RESPAWN-002",
                master_node_id=policy.root_node_id,
                parent_transaction_id=ledger().events[-1].event_hash,
                policy_hash=policy.policy_hash,
                registry_hash=registry.registry_hash,
                ledger_tail_hash=ledger().tail_hash,
                ledger_event_count=1,
                root_node_generation=0,
                control_generation=0,
                authority_ceiling=Authority.A0,
                registration_receipts=tuple(item.registration_receipt for item in registry.records),
                generated_at=OBSERVED,
                expires_at=RESPAWN_EXPIRES,
                live_master_bible_attachment=True,
            )

    def test_respawn_detects_registry_mismatch(self):
        policy, registry, _ = registry_with_chain(1)
        event_ledger = ledger()
        manifest = RespawnManifest(
            manifest_code="RESPAWN-003",
            master_node_id=policy.root_node_id,
            parent_transaction_id=event_ledger.events[-1].event_hash,
            policy_hash=policy.policy_hash,
            registry_hash=hash_of("WRONG-REGISTRY"),
            ledger_tail_hash=event_ledger.tail_hash,
            ledger_event_count=1,
            root_node_generation=0,
            control_generation=0,
            authority_ceiling=Authority.A0,
            registration_receipts=tuple(item.registration_receipt for item in registry.records),
            generated_at=OBSERVED,
            expires_at=RESPAWN_EXPIRES,
        )
        result = verify_respawn(
            manifest=manifest, policy=policy, registry=registry, ledger=event_ledger,
            stop_control=stop_control(), now=NOW
        )
        self.assertFalse(result.valid)

    def test_respawn_rejects_missing_parent_transaction(self):
        policy, registry, _ = registry_with_chain(1)
        event_ledger = ledger()
        manifest = RespawnManifest(
            manifest_code="RESPAWN-004",
            master_node_id=policy.root_node_id,
            parent_transaction_id=hash_of("MISSING-TRANSACTION"),
            policy_hash=policy.policy_hash,
            registry_hash=registry.registry_hash,
            ledger_tail_hash=event_ledger.tail_hash,
            ledger_event_count=1,
            root_node_generation=0,
            control_generation=0,
            authority_ceiling=Authority.A0,
            registration_receipts=tuple(item.registration_receipt for item in registry.records),
            generated_at=OBSERVED,
            expires_at=RESPAWN_EXPIRES,
        )
        result = verify_respawn(
            manifest=manifest, policy=policy, registry=registry, ledger=event_ledger,
            stop_control=stop_control(), now=NOW
        )
        self.assertFalse(result.valid)

    def test_respawn_rejects_future_manifest(self):
        policy, registry, _ = registry_with_chain(1)
        event_ledger = ledger()
        manifest = RespawnManifest(
            manifest_code="RESPAWN-005",
            master_node_id=policy.root_node_id,
            parent_transaction_id=event_ledger.events[-1].event_hash,
            policy_hash=policy.policy_hash,
            registry_hash=registry.registry_hash,
            ledger_tail_hash=event_ledger.tail_hash,
            ledger_event_count=1,
            root_node_generation=0,
            control_generation=0,
            authority_ceiling=Authority.A0,
            registration_receipts=tuple(item.registration_receipt for item in registry.records),
            generated_at="2026-08-02T12:01:00Z",
            expires_at="2026-08-02T12:04:00Z",
        )
        with self.assertRaisesRegex(ContractError, "FUTURE_DATED"):
            verify_respawn(
                manifest=manifest, policy=policy, registry=registry, ledger=event_ledger,
                stop_control=stop_control(), now=NOW
            )

    def test_respawn_cross_binds_ledger_entity_and_control_generation(self):
        policy, registry, _ = registry_with_chain(1)
        wrong_entity_ledger = ImmutableEventLedger().append(
            event_type=EventType.NODE_REGISTERED,
            entity_code="NODE-OTHER",
            occurred_at=OBSERVED,
            control_generation=0,
            payload={"node_code": "NODE-OTHER", "state_code": "REGISTERED"},
        )
        manifest = RespawnManifest(
            manifest_code="RESPAWN-006",
            master_node_id=policy.root_node_id,
            parent_transaction_id=wrong_entity_ledger.events[-1].event_hash,
            policy_hash=policy.policy_hash,
            registry_hash=registry.registry_hash,
            ledger_tail_hash=wrong_entity_ledger.tail_hash,
            ledger_event_count=1,
            root_node_generation=0,
            control_generation=0,
            authority_ceiling=Authority.A0,
            registration_receipts=tuple(item.registration_receipt for item in registry.records),
            generated_at=OBSERVED,
            expires_at=RESPAWN_EXPIRES,
        )
        result = verify_respawn(
            manifest=manifest, policy=policy, registry=registry, ledger=wrong_entity_ledger,
            stop_control=stop_control(), now=NOW
        )
        self.assertFalse(result.valid)

    def test_respawn_cross_binds_policy_registry_root_and_generation(self):
        policy, registry, _ = registry_with_chain(1)
        event_ledger = ledger()
        other_policy = MasterBiblePolicy.create(
            root_node_id="NODE-OTHER",
            owner_code=OWNER,
            matter_code=MATTER,
            classification="INTERNAL_META",
            control_generation=0,
        )
        manifest = RespawnManifest(
            manifest_code="RESPAWN-007",
            master_node_id=other_policy.root_node_id,
            parent_transaction_id=event_ledger.events[-1].event_hash,
            policy_hash=other_policy.policy_hash,
            registry_hash=registry.registry_hash,
            ledger_tail_hash=event_ledger.tail_hash,
            ledger_event_count=1,
            root_node_generation=1,
            control_generation=0,
            authority_ceiling=Authority.A0,
            registration_receipts=tuple(item.registration_receipt for item in registry.records),
            generated_at=OBSERVED,
            expires_at=RESPAWN_EXPIRES,
        )
        result = verify_respawn(
            manifest=manifest, policy=other_policy, registry=registry, ledger=event_ledger,
            stop_control=stop_control(), now=NOW
        )
        self.assertFalse(result.valid)

    def test_respawn_cross_binds_complete_policy_root_scope(self):
        policy, registry, nodes = registry_with_chain(1)
        event_ledger = ledger()
        root = nodes[0]
        root_variations = (
            replace(root, owner_code="OWNER-D4E5F6A7"),
            replace(root, matter_code="MATTER-E4F5A6B7"),
            replace(root, classification="RESTRICTED_META"),
            replace(root, authority_ceiling="A1"),
            replace(root, generation=1),
            replace(
                root,
                control_generation=1,
                signer_identity=replace(root.signer_identity, rotation_generation=1),
            ),
        )
        for changed_root in root_variations:
            changed_registry = type(registry)((changed_root,))
            manifest = RespawnManifest(
                manifest_code="RESPAWN-SCOPE",
                master_node_id=policy.root_node_id,
                parent_transaction_id=event_ledger.events[-1].event_hash,
                policy_hash=policy.policy_hash,
                registry_hash=changed_registry.registry_hash,
                ledger_tail_hash=event_ledger.tail_hash,
                ledger_event_count=1,
                root_node_generation=changed_root.generation,
                control_generation=0,
                authority_ceiling=Authority.A0,
                registration_receipts=(changed_root.registration_receipt,),
                generated_at=OBSERVED,
                expires_at=RESPAWN_EXPIRES,
            )
            with self.subTest(changed_root=changed_root):
                self.assertFalse(
                    verify_respawn(
                        manifest=manifest,
                        policy=policy,
                        registry=changed_registry,
                        ledger=event_ledger,
                        stop_control=stop_control(),
                        now=NOW,
                    ).valid
                )

    def test_respawn_rejects_stale_manifest(self):
        policy, registry, _ = registry_with_chain(1)
        event_ledger = ImmutableEventLedger().append(
            event_type=EventType.NODE_REGISTERED,
            entity_code="NODE-ROOT",
            occurred_at="2026-08-02T11:50:00Z",
            control_generation=0,
            payload={"node_code": "NODE-ROOT", "state_code": "REGISTERED"},
        )
        manifest = RespawnManifest(
            manifest_code="RESPAWN-008",
            master_node_id=policy.root_node_id,
            parent_transaction_id=event_ledger.events[-1].event_hash,
            policy_hash=policy.policy_hash,
            registry_hash=registry.registry_hash,
            ledger_tail_hash=event_ledger.tail_hash,
            ledger_event_count=1,
            root_node_generation=0,
            control_generation=0,
            authority_ceiling=Authority.A0,
            registration_receipts=tuple(item.registration_receipt for item in registry.records),
            generated_at="2026-08-02T11:50:00Z",
            expires_at="2026-08-02T11:54:00Z",
        )
        with self.assertRaisesRegex(ContractError, "STALE"):
            verify_respawn(
                manifest=manifest, policy=policy, registry=registry, ledger=event_ledger,
                stop_control=stop_control(), now=NOW
            )


class ReadOnlyAdapterTests(unittest.TestCase):
    def test_local_git_reference_rejects_traversal_empty_dot_and_symlink_segments(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            git = root / ".git"
            (git / "refs" / "heads").mkdir(parents=True)
            (root / "outside").write_text("a" * 40 + "\n", encoding="ascii")
            for reference in (
                "refs/heads/../../../outside",
                "refs//heads/main",
                "refs/./heads/main",
                "refs/heads/../main",
            ):
                (git / "HEAD").write_text(f"ref: {reference}\n", encoding="ascii")
                with self.subTest(reference=reference), self.assertRaisesRegex(
                    ContractError, "INVALID_GIT_REFERENCE"
                ):
                    read_local_repo(
                        root,
                        node_id="NODE-ROOT",
                        owner_code=OWNER,
                        matter_code=MATTER,
                        observed_at=OBSERVED,
                    )
            outside_refs = root / "outside-refs"
            outside_refs.mkdir()
            (outside_refs / "main").write_text("a" * 40 + "\n", encoding="ascii")
            (git / "refs" / "heads").rmdir()
            (git / "refs" / "heads").symlink_to(outside_refs, target_is_directory=True)
            (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="ascii")
            with self.assertRaisesRegex(ContractError, "SYMLINK_PROHIBITED"):
                read_local_repo(
                    root,
                    node_id="NODE-ROOT",
                    owner_code=OWNER,
                    matter_code=MATTER,
                    observed_at=OBSERVED,
                )

    def test_adapter_json_boundaries_reject_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "state.json").write_text(
                '{"mission":{"id":"MISSION-D4E5F6A7","id":"MISSION-D4E5F6A7","version":1,"state":"READY","control_generation":0}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ContractError, "JSON_INVALID"):
                read_formation_state(
                    root,
                    state_filename="state.json",
                    node_id="NODE-ROOT",
                    owner_code=OWNER,
                    matter_code=MATTER,
                    observed_at=OBSERVED,
                )
            (root / "LOCAL_BIBLE.md").write_text(
                "Latest transaction: `TXN-0010`\n", encoding="utf-8"
            )
            (root / "transaction-0010.json").write_text(
                '{"transaction_id":"TXN-0010","transaction_id":"TXN-0010"}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ContractError, "JSON_INVALID"):
                read_local_bible(
                    root,
                    node_id="NODE-ROOT",
                    owner_code=OWNER,
                    matter_code=MATTER,
                    observed_at=OBSERVED,
                )
    def test_observation_rejects_unknown_source_fields_and_raw_prose(self):
        common = {
            "node_id": "NODE-ROOT",
            "owner_code": OWNER,
            "matter_code": MATTER,
            "capability_code": "LOCAL-BIBLE-READBACK",
            "status": CapabilityStatus.AVAILABLE,
            "confidence_bp": 9000,
            "freshness_seconds": 0,
            "evidence_count": 1,
            "blocker_code": BlockerCode.NONE,
            "observed_at": OBSERVED,
        }
        with self.assertRaisesRegex(ContractError, "UNSUPPORTED_OBSERVATION_SOURCE"):
            make_observation(
                source_code="ARBITRARY-SOURCE",
                semantic_value={"latest_transaction": "TXN-CODE"},
                **common,
            )
        for semantic_value in (
            {
                "latest_transaction": "TXN-CODE",
                "transaction_sequence": 1,
                "semantic_alignment": True,
                "extra": "CODE",
            },
            {
                "latest_transaction": "raw legal or personal prose",
                "transaction_sequence": 1,
                "semantic_alignment": True,
            },
        ):
            with self.subTest(semantic_value=semantic_value), self.assertRaises(PrivacyError):
                make_observation(
                    source_code="LOCAL_BIBLE",
                    semantic_value=semantic_value,
                    **common,
                )

    def test_local_repo_readback(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            git = root / ".git"
            (git / "refs" / "heads").mkdir(parents=True)
            (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="ascii")
            (git / "refs" / "heads" / "main").write_text("a" * 40 + "\n", encoding="ascii")
            result = read_local_repo(
                root, node_id="NODE-ROOT", owner_code=OWNER, matter_code=MATTER, observed_at=OBSERVED
            )
            self.assertEqual(result.capability_code, "LOCAL_REPO_STATE")

    def test_local_bible_semantic_readback_and_drift(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "LOCAL_BIBLE.md").write_text(
                "Latest transaction: `TXN-HEARTBEAT-0010`\n", encoding="utf-8"
            )
            path = root / "transaction-0010.json"
            path.write_text(json.dumps({"transaction_id": "TXN-HEARTBEAT-0010"}), encoding="utf-8")
            result = read_local_bible(
                root, node_id="NODE-ROOT", owner_code=OWNER, matter_code=MATTER, observed_at=OBSERVED
            )
            self.assertEqual(result.capability_code, "LOCAL_BIBLE_READBACK")
            path.write_text(json.dumps({"transaction_id": "TXN-OTHER-0010"}), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "SEMANTIC_DRIFT"):
                read_local_bible(
                    root, node_id="NODE-ROOT", owner_code=OWNER, matter_code=MATTER, observed_at=OBSERVED
                )

    def test_formation_state_readback(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "state.json").write_text(
                json.dumps(
                    {
                        "mission": {
                            "id": "MISSION-C1D2E3F4",
                            "version": 1,
                            "state": "READY",
                            "control_generation": 0,
                        }
                    }
                ),
                encoding="utf-8",
            )
            result = read_formation_state(
                root,
                state_filename="state.json",
                node_id="NODE-ROOT",
                owner_code=OWNER,
                matter_code=MATTER,
                observed_at=OBSERVED,
            )
            self.assertEqual(result.capability_code, "FORMATION_STATE_READBACK")

    def test_formation_state_rejects_credential_labels(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "state.json").write_text(
                json.dumps({"mission": {"id": "MISSION-D4E5F6A7", "version": 1, "state": "READY", "control_generation": 0}, "api_key": "REDACTED"}),
                encoding="utf-8",
            )
            with self.assertRaises(PrivacyError):
                read_formation_state(
                    root, state_filename="state.json", node_id="NODE-ROOT",
                    owner_code=OWNER, matter_code=MATTER, observed_at=OBSERVED
                )

    def test_adapters_reject_callable_roots(self):
        with self.assertRaisesRegex(ContractError, "NOT_CALLABLE"):
            read_local_repo(
                lambda: None,
                node_id="NODE-ROOT",
                owner_code=OWNER,
                matter_code=MATTER,
                observed_at=OBSERVED,
            )


if __name__ == "__main__":
    unittest.main()
