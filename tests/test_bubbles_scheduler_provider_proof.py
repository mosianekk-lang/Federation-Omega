from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "governance" / "bubbles_scheduler_provider_proof_v1.json"


class BubblesSchedulerProviderProofTests(unittest.TestCase):
    def test_scheduler_proof_is_bounded_and_provider_observed(self) -> None:
        payload = json.loads(PROOF.read_text(encoding="utf-8"))
        self.assertEqual("BUBBLES-SCHEDULER-PROVIDER-PROOF-V1", payload["schema"])
        self.assertEqual("github_actions", payload["provider"])
        self.assertEqual("schedule", payload["observed_schedule_run"]["event"])
        self.assertEqual("success", payload["observed_schedule_run"]["conclusion"])
        self.assertFalse(payload["provider_effect_authority_created"])
        self.assertFalse(payload["future_payload_self_certified"])
        self.assertFalse(payload["owner_value_inferred"])


if __name__ == "__main__":
    unittest.main()
