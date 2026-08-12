from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bubbles.showcase import ShowcasePack


class ShowcasePortfolioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = ShowcasePack.load()

    def test_manifest_contains_exactly_six_flagships(self) -> None:
        manifest = self.pack.manifest()
        self.assertEqual(6, manifest["entry_count"])
        self.assertEqual(
            ["CIOS", "ECERTIFY", "CASEFORGE", "IPEP", "ARCHITRON", "K10"],
            [entry["project_id"] for entry in manifest["entries"]],
        )

    def test_architron_is_now_local_runtime_verified_not_provider_verified(self) -> None:
        entry = self.pack.entry("ARCHITRON")
        self.assertEqual("LOCAL_RUNTIME_VERIFIED", entry.evidence_state)
        self.assertFalse(entry.provider_verified)
        self.assertIn("local_semantic_event_queue_worker_target_readback", entry.verified_proofs)

    def test_k10_remains_execution_pending(self) -> None:
        entry = self.pack.entry("K10")
        self.assertEqual("IMPLEMENTED", entry.evidence_state)
        self.assertEqual("DESIGN_VALIDATED_EXECUTION_PENDING", entry.demo_state)
        self.assertFalse(entry.provider_verified)

    def test_provider_overclaim_is_blocked(self) -> None:
        decision = self.pack.validate_public_claim("CIOS", "DEPLOYED", "CIOS is deployed")
        self.assertFalse(decision["allowed"])
        self.assertFalse(decision["maturity_allowed"])
        self.assertFalse(decision["text_allowed"])

    def test_safe_current_claim_is_allowed(self) -> None:
        entry = self.pack.entry("IPEP")
        decision = self.pack.validate_public_claim("IPEP", "LOCAL_RUNTIME_VERIFIED", entry.strongest_safe_claim)
        self.assertTrue(decision["allowed"])

    def test_manifest_can_be_written_for_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.pack.write_manifest(Path(tmp) / "portfolio.json")
            self.assertTrue(path.is_file())
            text = path.read_text(encoding="utf-8")
            self.assertIn("Applied AI Systems Architect Demonstrable Portfolio", text)
            self.assertIn("INTERNAL_PROOF_PACK_READY_EXTERNAL_PROOFS_PENDING", text)


if __name__ == "__main__":
    unittest.main()
