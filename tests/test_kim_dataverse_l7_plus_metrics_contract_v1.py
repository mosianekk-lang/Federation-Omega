from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_metrics_contract_v1.json"


class KimDataverseLevel7PlusMetricsContractTests(unittest.TestCase):
    def test_metrics_contract_rejects_synthetic_owner_value_and_requires_provider_readback(self) -> None:
        data = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertFalse(data["synthetic_can_satisfy_operational_metrics"])
        self.assertFalse(data["shadow_can_satisfy_owner_value"])
        self.assertTrue(data["provider_claim_requires_provider_native_readback"])


if __name__ == "__main__":
    unittest.main()
