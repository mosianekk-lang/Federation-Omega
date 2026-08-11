from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace

from live_provider_block import ProviderBlockEvidence, ProviderBlockLedger
from live_provider_expansion import digest

NOW = "2026-08-04T00:15:00Z"


def block(observed_at: str = "2026-08-04T00:10:00Z") -> ProviderBlockEvidence:
    metadata = {
        "workflow_run": 30857451510,
        "job_id": 91831656941,
        "failed_step": "Authenticate to Google Cloud through keyless OIDC",
        "preceding_exact_error": "invalid_target",
        "subsequent_cloud_steps_skipped": True,
    }
    return ProviderBlockEvidence(
        block_id="cloud-run-wif-block-001",
        provider="google_cloud_run",
        reason="PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED",
        provider_native=True,
        observed_at=observed_at,
        locator="github-actions://mosianekk-lang/Federation-Omega/runs/30857451510/jobs/91831656941",
        attempted_scope=("oidc_token_exchange", "cloud_run_readback"),
        mutation_performed=False,
        content_sha256=digest(metadata),
        metadata=metadata,
    )


class ProviderBlockLedgerTests(unittest.TestCase):
    def test_records_fresh_provider_native_block_and_replays(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ProviderBlockLedger(tmp)
            decision = ledger.record(block(), now=NOW)
            self.assertTrue(decision["admitted"])
            projected = ledger.latest("google_cloud_run", now=NOW)
            self.assertEqual("PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED", projected["projected_state"])
            self.assertTrue(projected["fresh"])
            replayed = ProviderBlockLedger(tmp)
            self.assertEqual(projected["block_id"], replayed.latest("google_cloud_run", now=NOW)["block_id"])
            self.assertTrue(replayed.verify_ledger())

    def test_idempotency_and_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ProviderBlockLedger(tmp)
            first = ledger.record(block(), now=NOW)
            lines = ledger.ledger_file.read_text().splitlines()
            second = ledger.record(block(), now=NOW)
            self.assertEqual(first, second)
            self.assertEqual(lines, ledger.ledger_file.read_text().splitlines())
            conflict = ledger.record(replace(block(), reason="PROVIDER_BLOCKED_WIF_INVALID_TARGET"), now=NOW)
            self.assertFalse(conflict["admitted"])
            self.assertIn("BLOCK_ID_CONFLICT", conflict["reasons"])

    def test_rejects_mutation_and_stale_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ProviderBlockLedger(tmp)
            stale_mutated = replace(block("2026-08-03T00:00:00Z"), mutation_performed=True)
            decision = ledger.record(stale_mutated, now=NOW)
            self.assertFalse(decision["admitted"])
            self.assertIn("MUTATION_OCCURRED_BEFORE_BLOCK", decision["reasons"])
            self.assertIn("BLOCK_EVIDENCE_STALE", decision["reasons"])

    def test_rejects_unknown_reason_and_tampered_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ProviderBlockLedger(tmp)
            invalid = replace(block(), reason="SOMETHING_FAILED", content_sha256="bad")
            decision = ledger.record(invalid, now=NOW)
            self.assertFalse(decision["admitted"])
            self.assertIn("UNRECOGNISED_BLOCK_REASON", decision["reasons"])
            self.assertIn("INVALID_CONTENT_SHA256", decision["reasons"])


if __name__ == "__main__":
    unittest.main()
