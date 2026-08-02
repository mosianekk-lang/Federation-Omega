from __future__ import annotations

import unittest
from dataclasses import replace

from evidenceops.capability_heartbeat.foundation.chat_handoff import ChatHandoff
from evidenceops.capability_heartbeat.foundation.contracts import (
    BlockerCode,
    HeartbeatEnvelope,
    NodeState,
    Recommendation,
    digest,
)
from evidenceops.capability_heartbeat.foundation.errors import ContractError, PrivacyError
from evidenceops.capability_heartbeat.foundation.privacy import minimize_metadata, reject_sensitive_tree, require_code

from evidenceops.capability_heartbeat.foundation_tests.helpers import EXPIRES, MATTER, MISSION, NOW, OBSERVED, OWNER, envelope, hash_of


class StrictContractTests(unittest.TestCase):
    def test_unknown_envelope_field_rejected(self):
        payload = envelope().signing_body() | {"signature": envelope().signature, "unknown": "CODE"}
        with self.assertRaisesRegex(ContractError, "UNKNOWN_FIELDS"):
            HeartbeatEnvelope.from_mapping(payload)

    def test_unknown_recommendation_enum_rejected(self):
        with self.assertRaisesRegex(ContractError, "UNKNOWN_ENUM"):
            Recommendation(role="EXECUTE", capability_code="CAPABILITY-A", score=9000)

    def test_non_a0_envelope_rejected(self):
        with self.assertRaisesRegex(ContractError, "AUTHORITY_MUST_BE_A0"):
            replace(envelope(), delegation_ceiling="A1")

    def test_invalid_ttl_rejected(self):
        with self.assertRaisesRegex(ContractError, "INVALID_ENVELOPE_TTL"):
            replace(envelope(), expires_at=OBSERVED)

    def test_hop_above_three_rejected(self):
        with self.assertRaisesRegex(ContractError, "HOP_LIMIT_EXCEEDED"):
            replace(envelope(), hop_count=4)

    def test_visited_loop_rejected(self):
        with self.assertRaisesRegex(ContractError, "VISITED_LOOP_DETECTED"):
            replace(envelope(), visited_node_ids=("NODE-ROOT", "NODE-ROOT"))

    def test_hop_count_must_equal_visited_path_length(self):
        with self.assertRaisesRegex(ContractError, "HOP_PATH_LENGTH_MISMATCH"):
            replace(envelope(), hop_count=1)


class PrivacyTests(unittest.TestCase):
    def test_field_bound_code_privacy_rejects_credentials_personal_and_legal_probes(self):
        credential_shapes = (
            "AKIA" + "A" * 16,
            "AIza" + "A" * 35,
            "ghp_" + "A" * 36,
            "github_pat_" + "A" * 20,
        )
        for value in credential_shapes:
            with self.subTest(value=value), self.assertRaisesRegex(PrivacyError, "CREDENTIAL_VALUE_SHAPE"):
                reject_sensitive_tree({"safe_value": value})
        probes = (
            ("owner_code", "ALICE-SMITH"),
            ("owner_code", "OWNER-ALICE-SMITH"),
            ("owner_code", "OWNER-AL1CE-SM1TH"),
            ("matter_code", "UNFAIR-DISMISSAL"),
            ("matter_code", "MATTER-UNFAIR-DISMISSAL"),
            ("matter_code", "MATTER-UNFAIR_DISMISSAL"),
        )
        for field, value in probes:
            with self.subTest(field=field, value=value), self.assertRaises(PrivacyError):
                require_code(value, field=field)

    def test_valid_code_namespace_compatibility_table(self):
        values = {
            "node_id": "NODE-ROOT",
            "parent_node_id": "NODE-CHILD-1",
            "origin_node_id": "NODE-ROOT",
            "signing_node_id": "NODE-ROOT",
            "accepting_node_id": "NODE-CHILD-1",
            "master_node_id": "NODE-ROOT",
            "root_node_id": "NODE-ROOT",
            "from_node_id": "NODE-ROOT",
            "to_node_id": "NODE-CHILD-1",
            "node_code": "NODE-ROOT",
            "entity_code": "NODE-ROOT",
            "visited_node_ids": "NODE-CHILD-1",
            "owner_code": "OWNER-A1B2C3D4",
            "matter_code": "MATTER-B1C2D3E4",
            "mission_code": "MISSION-C1D2E3F4",
            "mission.id": "MISSION-D4E5F6A7",
            "capability_code": "CAPABILITY-A",
            "source_code": "LOCAL_REPO",
            "state_code": "REGISTERED",
            "mission_state": "READY",
            "key_id": "KEY-NODE-CHILD-1",
            "latest_transaction": "TXN-0010",
            "schema_version": "HEARTBEAT-0.1",
            "adapter_version": "LOCAL-0.1",
            "signing_version": "HMAC-0.1",
            "version_code": "HANDOFF-0.1",
            "reference_code": "SYMBOLIC",
            "stop_reason_code": "NONE",
            "reason_code": "STOP-OWNER",
            "manifest_code": "RESPAWN-001",
        }
        for field, value in values.items():
            with self.subTest(field=field, value=value):
                self.assertEqual(require_code(value, field=field), value)
    def test_credential_labels_rejected(self):
        for key in ("api-key", "password", "private_key", "accessToken", "cookie", "authorization"):
            with self.subTest(key=key), self.assertRaisesRegex(PrivacyError, "CREDENTIAL_LABEL"):
                reject_sensitive_tree({key: "REDACTED"})

    def test_raw_content_keys_rejected(self):
        for key in ("prompt", "chat_body", "evidence", "legal_text", "file_id"):
            with self.subTest(key=key), self.assertRaisesRegex(PrivacyError, "RAW_CONTENT_KEY"):
                reject_sensitive_tree({key: "CODE"})

    def test_pii_shapes_rejected(self):
        values = (
            "person@example.org",
            "https://example.org/path",
            "+27 82 123 4567",
            "/home/person/case.txt",
            "1Abcdefghijklmnopqrstuvwxyz_opaque",
        )
        for value in values:
            with self.subTest(value=value), self.assertRaises(PrivacyError):
                reject_sensitive_tree({"safe_code": value})

    def test_callable_rejected(self):
        with self.assertRaisesRegex(PrivacyError, "CALLABLE_PROHIBITED"):
            reject_sensitive_tree({"adapter": lambda: None})

    def test_minimizer_rejects_unknown_instead_of_dropping(self):
        with self.assertRaisesRegex(PrivacyError, "UNKNOWN_METADATA_FIELDS"):
            minimize_metadata({"mission_code": MISSION, "extra": "CODE"}, allowed_keys=frozenset({"mission_code"}))

    def test_chat_handoff_accepts_only_minimal_metadata(self):
        payload = {
            "node_id": "NODE-CHAT",
            "mission_code": MISSION,
            "owner_code": OWNER,
            "matter_code": MATTER,
            "state": NodeState.BLOCKED.value,
            "capability_hashes": [hash_of("CAP-A")],
            "blocker_codes": [BlockerCode.ATTACHMENT_UNPROVEN.value],
            "observed_at": OBSERVED,
            "expires_at": EXPIRES,
            "version_code": "HANDOFF-0.1",
            "receipt_hash": digest({"receipt": "CHAT"}),
        }
        handoff = ChatHandoff.from_mapping(payload)
        self.assertTrue(handoff.handoff_hash.startswith("sha256:"))
        with self.assertRaises(PrivacyError):
            ChatHandoff.from_mapping(payload | {"message_body": "raw"})


if __name__ == "__main__":
    unittest.main()
