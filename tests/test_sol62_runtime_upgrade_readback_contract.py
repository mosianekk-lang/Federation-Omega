from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Sol62RuntimeUpgradeReadbackContractTests(unittest.TestCase):
    def test_runtime_exposes_upgrade_genome_without_maturity_inflation(self):
        app = (ROOT / "services" / "sol62_client_runtime" / "app.py").read_text(encoding="utf-8")
        genome = (ROOT / "services" / "sol62_client_runtime" / "runtime_upgrade_genome.py").read_text(encoding="utf-8")
        self.assertIn('"/v1/runtime-upgrades"', app)
        self.assertIn("runtime_upgrade_genome", app)
        self.assertIn("HG-SOL62-101", genome)
        self.assertIn("HG-SOL62-200", genome)
        self.assertIn("GENOME_REGISTERED_NE_IMPLEMENTED", genome)
        self.assertIn("SOURCE_ADMITTED_NE_LIVE_RUNTIME", genome)


if __name__ == "__main__":
    unittest.main()
