from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Sol62BibleEmbodimentRuntimeContractTests(unittest.TestCase):
    def test_bible_manifest_and_fabric_are_runtime_bound(self):
        manifest = (ROOT / "services" / "sol62_client_runtime" / "bible_estate_manifest.json").read_text(encoding="utf-8")
        fabric = (ROOT / "services" / "sol62_client_runtime" / "bible_embodiment.py").read_text(encoding="utf-8")
        app = (ROOT / "services" / "sol62_client_runtime" / "app.py").read_text(encoding="utf-8")
        self.assertIn('"entry_count": 39', manifest)
        self.assertIn("BibleEmbodimentFabric", app)
        self.assertIn("SOL62_BIBLE_EMBODIMENT_FABRIC_V1", fabric)
        self.assertIn("DOMAIN_AUTHORITY_PRESERVED", fabric)
        self.assertIn("NO_AUTHORITY_TRANSFER", fabric)

    def test_wake_orders_bible_embodiment_before_strategy(self):
        app = (ROOT / "services" / "sol62_client_runtime" / "app.py").read_text(encoding="utf-8")
        bible_idx = app.index("SOL62_BIBLE_EMBODIMENT_WAKE_PREPASS")
        strategy_idx = app.index("SOL62_ALPHA_OMEGA_FORMATION_WAKE_PREPASS")
        execute_idx = app.index("wake_until_terminal", strategy_idx)
        self.assertLess(bible_idx, strategy_idx)
        self.assertLess(strategy_idx, execute_idx)
        self.assertIn('strategy_result["bible_capsule_sha256"]', app)
        self.assertIn("strategy_recompiled_for_bible_change", app)

    def test_runtime_never_equates_inventory_with_full_read(self):
        fabric = (ROOT / "services" / "sol62_client_runtime" / "bible_embodiment.py").read_text(encoding="utf-8")
        self.assertIn("all_registered_bibles_read", fabric)
        self.assertIn("MANIFEST_REGISTERED_NE_SOURCE_READ", fabric)
        self.assertIn("full_corpus_available", fabric)

    def test_raw_bible_text_cannot_mint_authority_or_maturity(self):
        fabric = (ROOT / "services" / "sol62_client_runtime" / "bible_embodiment.py").read_text(encoding="utf-8")
        app = (ROOT / "services" / "sol62_client_runtime" / "app.py").read_text(encoding="utf-8")
        self.assertIn('"raw_text_is_authority": False', fabric)
        self.assertIn('"maturity_inheritance": False', fabric)
        self.assertIn('"authority_expansion": False', app)


if __name__ == "__main__":
    unittest.main()
