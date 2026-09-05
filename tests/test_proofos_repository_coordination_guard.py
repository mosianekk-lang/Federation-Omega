from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path

from proofos_omega.repository_coordination import (
    CLAIM_SCHEMA,
    DEFAULT_LEASE_REF,
    LEASE_SCHEMA,
    evaluate_coordination,
    evaluate_hosted_pull_request,
    extract_coordination_claim,
    load_policy,
    parse_lease_message,
)

ROOT = Path(__file__).resolve().parents[1]
AIRLOCK_WORKFLOW = ROOT / ".github" / "workflows" / "github-airlock.yml"
BASE = "1" * 40
LEASE_SHA = "2" * 40
NOW = datetime(2026, 9, 2, 20, 50, tzinfo=timezone.utc)


def lease(*, source_head: str = BASE, expires_at: str = "2026-09-02T23:19:04+02:00") -> dict:
    return {
        "schema": LEASE_SCHEMA,
        "state": "ACTIVE",
        "fencing_token": 7,
        "writer_node": "NODE-A",
        "system": "FDOF/Federation Omega Airlock",
        "workstream": "coordination-test",
        "transaction_id": "TXN-1",
        "idempotency_key": "TC-1",
        "source_head": source_head,
        "scope": ["repository:*"],
        "acquired_at": "2026-09-02T22:49:04+02:00",
        "expires_at": expires_at,
        "turn_capture_id": "TC-1",
        "effect": "NONE",
        "authority": "A1_INTERNAL",
    }


def lease_message(payload: dict) -> str:
    return LEASE_SCHEMA + "\n" + json.dumps(payload, sort_keys=True, separators=(",", ":"))


def claim(**overrides) -> dict:
    body = {
        "schema": CLAIM_SCHEMA,
        "writer_node": "NODE-A",
        "system": "FDOF/Federation Omega Airlock",
        "workstream": "coordination-test",
        "transaction_id": "TXN-1",
        "idempotency_key": "TC-1",
        "source_head": BASE,
        "turn_capture_id": "TC-1",
        "lock_ref": DEFAULT_LEASE_REF,
        "lease_commit_sha": LEASE_SHA,
        "fencing_token": 7,
    }
    body.update(overrides)
    return body


class RepositoryCoordinationV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_policy()

    def assess(self, *, pr_body: str, lease_payload: dict | None = None, tree_matches: bool = True):
        payload = lease_payload or lease()
        return evaluate_coordination(
            base_sha=BASE,
            pr_body=pr_body,
            lease_message=lease_message(payload),
            lease_commit_sha=LEASE_SHA,
            lease_tree_matches_source=tree_matches,
            now=NOW,
            policy=self.policy,
        )

    def rules(self, assessment):
        return {item["rule"] for item in assessment["findings"]}

    def test_governance_contract_is_bounded(self):
        self.assertEqual(DEFAULT_LEASE_REF, self.policy["lease_ref"])
        self.assertTrue(self.policy["write_ahead_capture_required"])
        self.assertFalse(self.policy["provider_branch_protection_equivalent"])
        self.assertFalse(self.policy["provider_ruleset_equivalent"])
        self.assertFalse(self.policy["provider_authority_created"])
        self.assertFalse(self.policy["external_effect_authorized"])

    def test_machine_readable_lease_descriptor_parses(self):
        parsed = parse_lease_message(lease_message(lease()))
        self.assertEqual("ACTIVE", parsed["state"])
        self.assertEqual(7, parsed["fencing_token"])
        self.assertEqual(BASE, parsed["source_head"])

    def test_matching_active_lease_claim_passes(self):
        assessment = self.assess(pr_body=json.dumps(claim()))
        self.assertEqual("PASS", assessment["status"])
        self.assertEqual("ACTIVE_LEASE_CLAIM_VERIFIED", assessment["state"])
        self.assertFalse(assessment["provider_effect_authorized"])

    def test_unclaimed_active_lease_fails_closed(self):
        assessment = self.assess(pr_body="ordinary PR body")
        self.assertEqual("FAIL", assessment["status"])
        self.assertIn("ACTIVE_REPOSITORY_LEASE_UNCLAIMED", self.rules(assessment))

    def test_wrong_writer_or_transaction_fails_closed(self):
        assessment = self.assess(
            pr_body=json.dumps(claim(writer_node="NODE-B", transaction_id="TXN-OTHER"))
        )
        self.assertEqual("FAIL", assessment["status"])
        self.assertIn("PR_COORDINATION_LEASE_MISMATCH", self.rules(assessment))

    def test_wrong_fence_commit_fails_closed(self):
        assessment = self.assess(pr_body=json.dumps(claim(lease_commit_sha="3" * 40)))
        self.assertEqual("FAIL", assessment["status"])
        self.assertIn("PR_COORDINATION_FENCE_COMMIT_MISMATCH", self.rules(assessment))

    def test_active_lease_source_drift_fails_closed(self):
        assessment = self.assess(
            pr_body=json.dumps(claim()),
            lease_payload=lease(source_head="4" * 40),
        )
        self.assertEqual("FAIL", assessment["status"])
        self.assertIn("ACTIVE_LEASE_SOURCE_EPOCH_MISMATCH", self.rules(assessment))

    def test_lock_tree_must_match_declared_source_tree(self):
        assessment = self.assess(pr_body=json.dumps(claim()), tree_matches=False)
        self.assertEqual("FAIL", assessment["status"])
        self.assertIn("ACTIVE_LEASE_TREE_MISMATCH", self.rules(assessment))

    def test_expired_lease_does_not_block_future_work(self):
        assessment = self.assess(
            pr_body="ordinary PR body",
            lease_payload=lease(expires_at="2026-09-02T22:49:30+02:00"),
        )
        self.assertEqual("PASS", assessment["status"])
        self.assertEqual("LEASE_EXPIRED", assessment["state"])

    def test_sparse_released_legacy_lease_does_not_permanently_deadlock_repo(self):
        released = {
            "schema": LEASE_SCHEMA,
            "state": "RELEASED",
            "fencing_token": 48,
            "source_head": BASE,
            "effect": "NONE",
        }
        assessment = self.assess(pr_body="ordinary PR body", lease_payload=released)
        self.assertEqual("PASS", assessment["status"])
        self.assertEqual("LEASE_RELEASED", assessment["state"])
        self.assertEqual([], assessment["findings"])

    def test_sparse_active_legacy_lease_remains_fail_closed(self):
        active = {
            "schema": LEASE_SCHEMA,
            "state": "ACTIVE",
            "fencing_token": 49,
            "source_head": BASE,
            "effect": "NONE",
            "expires_at": "2026-09-02T23:19:04+02:00",
        }
        assessment = self.assess(pr_body="ordinary PR body", lease_payload=active)
        self.assertEqual("FAIL", assessment["status"])
        self.assertEqual("INVALID_LEASE", assessment["state"])
        self.assertIn("LEASE_DESCRIPTOR_FIELD_MISSING", self.rules(assessment))

    def test_released_lease_with_invalid_effect_still_fails_closed(self):
        released = {
            "schema": LEASE_SCHEMA,
            "state": "RELEASED",
            "fencing_token": 48,
            "source_head": BASE,
            "effect": "PROVIDER_MUTATION",
        }
        assessment = self.assess(pr_body="ordinary PR body", lease_payload=released)
        self.assertEqual("FAIL", assessment["status"])
        self.assertEqual("INVALID_RELEASED_LEASE", assessment["state"])
        self.assertIn("LEASE_EFFECT_SCOPE_INVALID", self.rules(assessment))

    def test_bubbles_payload_can_carry_coordination_claim(self):
        body = json.dumps({
            "schema": "BUBBLES-CONTROL-COMMAND-V1",
            "payload": {"message": "x", "coordination": claim()},
        })
        extracted = extract_coordination_claim(body)
        self.assertEqual("TXN-1", extracted["transaction_id"])
        assessment = self.assess(pr_body=body)
        self.assertEqual("PASS", assessment["status"])

    def test_markdown_comment_can_carry_coordination_claim(self):
        body = "Summary\n\n<!-- FEDERATION_COORDINATION_V1\n" + json.dumps(claim()) + "\n-->"
        assessment = self.assess(pr_body=body)
        self.assertEqual("PASS", assessment["status"])

    @unittest.skipUnless(
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_EVENT_NAME") == "pull_request",
        "hosted repository coordination court runs only on GitHub pull_request",
    )
    def test_hosted_pull_request_honours_active_repository_lease(self):
        if not AIRLOCK_WORKFLOW.exists():
            self.skipTest("workflow-free export excludes repository coordination enforcement surface")
        assessment = evaluate_hosted_pull_request(ROOT)
        self.assertEqual(
            "PASS",
            assessment["status"],
            json.dumps(assessment, indent=2, sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
