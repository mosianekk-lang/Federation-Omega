from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from authority_refresh import AuthorityObservation, ProviderAuthorityFreshnessLedger


class ProviderAuthorityFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = json.loads(Path("provider_authority_observations.json").read_text(encoding="utf-8"))
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = ProviderAuthorityFreshnessLedger(self.temp.name, self.bundle["policies"])
        self.now = self.bundle["captured_at"]

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def observation(data):
        row = dict(data)
        row["scope"] = tuple(row["scope"])
        return AuthorityObservation(**row)

    def test_provider_native_observations_are_admitted_and_projected(self) -> None:
        for row in self.bundle["observations"]:
            decision = self.ledger.admit(self.observation(row), now=self.now)
            self.assertEqual(decision["status"], "ADMITTED")
        projection = self.ledger.project(self.bundle["base_authority"], now=self.now)
        self.assertEqual(projection["states"]["github_actions"], "FRESH_VERIFIED")
        self.assertEqual(projection["states"]["google_drive_document_release"], "FRESH_VERIFIED_READBACK")
        self.assertEqual(
            projection["evidence"]["google_drive_document_release"]["evidence"]["file_id"],
            "1dSKrl418Wjns8pbk3GzY-w4c6rnKmwvIokmWVtKvjGI",
        )
        self.assertTrue(projection["ledger_integrity"])

    def test_non_provider_native_and_wrong_scope_are_rejected(self) -> None:
        row = copy.deepcopy(self.bundle["observations"][0])
        row["observation_id"] = "bad-provider"
        row["provider_native"] = False
        row["scope"] = ["source_read"]
        decision = self.ledger.admit(self.observation(row), now=self.now)
        self.assertEqual(decision["status"], "REJECTED")
        self.assertIn("NON_PROVIDER_NATIVE_OBSERVATION", decision["reasons"])
        self.assertTrue(any(reason.startswith("MISSING_REQUIRED_SCOPE:") for reason in decision["reasons"]))

    def test_stale_observation_is_rejected_and_existing_authority_expires(self) -> None:
        row = copy.deepcopy(self.bundle["observations"][0])
        row["observation_id"] = "stale-gh"
        row["observed_at"] = "2026-07-01T00:00:00Z"
        row["captured_at"] = "2026-08-03T20:01:49Z"
        decision = self.ledger.admit(self.observation(row), now=self.now)
        self.assertEqual(decision["status"], "REJECTED")
        self.assertIn("AUTHORITY_OBSERVATION_STALE", decision["reasons"])

        good = self.observation(self.bundle["observations"][0])
        self.ledger.admit(good, now=self.now)
        future = self.ledger.project(self.bundle["base_authority"], now="2026-08-05T20:01:49Z")
        self.assertEqual(future["states"]["github_actions"], "STALE_REVALIDATION_REQUIRED")

    def test_blocked_domains_are_not_promoted(self) -> None:
        for row in self.bundle["observations"]:
            self.ledger.admit(self.observation(row), now=self.now)
        projection = self.ledger.project(self.bundle["base_authority"], now=self.now)
        self.assertEqual(projection["states"]["cloud_run"], "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY")
        self.assertEqual(projection["states"]["payment_provider"], "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY")
        self.assertEqual(projection["states"]["customer_market"], "MARKET_PROOF_REQUIRED")
        self.assertEqual(projection["external_gate_effect"], "UNCHANGED")
        self.assertEqual(projection["owner_authority_effect"], "UNCHANGED")

    def test_restart_readback_and_id_conflict(self) -> None:
        row = self.bundle["observations"][1]
        original = self.observation(row)
        first = self.ledger.admit(original, now=self.now)
        again = self.ledger.admit(original, now=self.now)
        self.assertEqual(first, again)

        restarted = ProviderAuthorityFreshnessLedger(self.temp.name, self.bundle["policies"])
        projection = restarted.project(self.bundle["base_authority"], now=self.now)
        self.assertTrue(projection["ledger_integrity"])
        self.assertIn("google_drive_document_release", projection["evidence"])

        changed = copy.deepcopy(row)
        changed["content_sha256"] = "0" * 64
        conflict = restarted.admit(self.observation(changed), now=self.now)
        self.assertEqual(conflict["status"], "REJECTED")
        self.assertIn("OBSERVATION_ID_CONFLICT", conflict["reasons"])


if __name__ == "__main__":
    unittest.main()
