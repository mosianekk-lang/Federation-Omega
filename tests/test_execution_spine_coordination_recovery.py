from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest

from proofos_omega.repository_coordination import LEASE_SCHEMA, evaluate_coordination, load_policy


BASE = "3b47e77062242f224ab1d3eab993d53fd3f95147"
LEASE_SHA = "0" * 40


def lease_message(*, expires_at: str, include_turn_capture: bool) -> str:
    lease = {
        "schema": LEASE_SCHEMA,
        "state": "ACTIVE",
        "fencing_token": 27,
        "writer_node": "NODE-X",
        "system": "CFBE/FEDERATION",
        "workstream": "workstream-x",
        "transaction_id": "TXN-X",
        "idempotency_key": "IDEMP-X",
        "source_head": BASE,
        "acquired_at": "2026-09-04T17:47:00+02:00",
        "expires_at": expires_at,
        "scope": ["source_update"],
        "effect": "NONE",
        "authority": "A1_INTERNAL_SOURCE_CI",
        "provider_runtime_effect": False,
    }
    if include_turn_capture:
        lease["turn_capture_id"] = "CAP-X"
    return LEASE_SCHEMA + "\n" + json.dumps(lease, separators=(",", ":"), sort_keys=True)


class CoordinationRecoveryTests(unittest.TestCase):
    def test_expired_descriptor_no_longer_blocks_even_if_non_authoritative_field_missing(self):
        result = evaluate_coordination(
            base_sha=BASE,
            pr_body="",
            lease_message=lease_message(
                expires_at="2026-09-04T18:17:00+02:00",
                include_turn_capture=False,
            ),
            lease_commit_sha=LEASE_SHA,
            lease_tree_matches_source=True,
            now=datetime(2026, 9, 4, 16, 37, tzinfo=timezone.utc),
            policy=load_policy(),
        )
        self.assertEqual("PASS", result["status"])
        self.assertEqual("LEASE_EXPIRED", result["state"])
        self.assertEqual([], result["findings"])

    def test_same_incomplete_descriptor_still_fails_while_active(self):
        result = evaluate_coordination(
            base_sha=BASE,
            pr_body="",
            lease_message=lease_message(
                expires_at="2026-09-04T19:17:00+02:00",
                include_turn_capture=False,
            ),
            lease_commit_sha=LEASE_SHA,
            lease_tree_matches_source=True,
            now=datetime(2026, 9, 4, 16, 37, tzinfo=timezone.utc),
            policy=load_policy(),
        )
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("INVALID_LEASE", result["state"])
        self.assertIn(
            {"rule": "LEASE_DESCRIPTOR_FIELD_MISSING", "detail": "turn_capture_id"},
            result["findings"],
        )

    def test_released_descriptor_is_terminal_before_active_field_court(self):
        raw = lease_message(
            expires_at="2026-09-04T19:17:00+02:00",
            include_turn_capture=False,
        )
        first, body = raw.split("\n", 1)
        lease = json.loads(body)
        lease["state"] = "RELEASED"
        result = evaluate_coordination(
            base_sha=BASE,
            pr_body="",
            lease_message=first + "\n" + json.dumps(lease),
            lease_commit_sha=LEASE_SHA,
            lease_tree_matches_source=True,
            now=datetime(2026, 9, 4, 16, 37, tzinfo=timezone.utc),
            policy=load_policy(),
        )
        self.assertEqual("PASS", result["status"])
        self.assertEqual("LEASE_RELEASED", result["state"])


if __name__ == "__main__":
    unittest.main()
