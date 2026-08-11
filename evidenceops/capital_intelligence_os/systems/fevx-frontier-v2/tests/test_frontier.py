from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from frontier_v2 import Argonaut, Chimera, Janus, Lucid, Mnemosyne, Morphos, Noesis, Polis, Polylogue, Symbiosis
from frontier_v2.core import digest, semantic
from frontier_v2.evolution import evolve
from frontier_v2.runtime import run_frontier, semantic_hash
from frontier_v2.store import dump_database, restore_database, verify_chain

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = json.loads((ROOT / "context.json").read_text())


class FrontierSystemTests(unittest.TestCase):
    def test_noesis_finds_blind_spots(self):
        out = Noesis().run(CONTEXT)
        self.assertGreaterEqual(len(out["decision_sensitive_gaps"]), 3)
        self.assertTrue(all(not x["external_effect"] for x in out["experiments"]))

    def test_lucid_calibrates_route(self):
        out = Lucid().run(CONTEXT)
        self.assertIn(out["route"], {"ACT_WITH_READBACK", "ACT_WITH_INDEPENDENT_VERIFIER"})
        self.assertEqual(out["authority_ceiling"], "A1_INTERNAL")

    def test_mnemosyne_creates_antibody(self):
        out = Mnemosyne().run(CONTEXT)
        self.assertEqual(len(out["cognitive_antibodies"]), 1)
        self.assertFalse(out["constitutional_memory_modified"])

    def test_morphos_preserves_identity(self):
        out = Morphos().run(CONTEXT)
        self.assertEqual(out["maturity"], "HOMEOSTATIC")
        self.assertTrue(out["identity_preserved"])
        self.assertFalse(out["authority_expanded"])

    def test_polis_is_simulation_only(self):
        out = Polis().run(CONTEXT)
        self.assertGreater(out["institutional_success_probability"], 0.5)
        self.assertTrue(out["simulation_only"])

    def test_chimera_counterfactual(self):
        out = Chimera().run(CONTEXT)
        self.assertGreater(out["counterfactual"]["predicted_after"], out["counterfactual"]["baseline"])
        self.assertEqual(out["causality_state"], "MODELLED_NOT_REAL_WORLD_PROVEN")

    def test_argonaut_preserves_options(self):
        out = Argonaut().run(CONTEXT)
        self.assertEqual(out["portfolio"][0]["id"], "github_shadow")
        self.assertFalse(out["premature_lock_in"])

    def test_polylogue_diversity(self):
        out = Polylogue().run(CONTEXT)
        self.assertGreaterEqual(out["independent_viewpoints"], 3)
        self.assertTrue(out["diversity_sufficient"])

    def test_janus_excludes_hindsight(self):
        out = Janus().run(CONTEXT)
        self.assertEqual(out["regret"], 0.0)
        self.assertTrue(out["hindsight_information_excluded"])

    def test_symbiosis_human_leads_values(self):
        out = Symbiosis().run(CONTEXT)
        self.assertEqual(out["allocation_mode"], "HUMAN_LEADS_AI_REFINES")
        self.assertEqual(out["dependency_goal"], "REDUCE_NOT_INCREASE")

    def test_ordered_frontier_pipeline(self):
        first = run_frontier(dict(CONTEXT))
        second = run_frontier(dict(CONTEXT))
        self.assertEqual(len(first), 10)
        self.assertEqual(semantic_hash(first), semantic_hash(second))
        self.assertEqual(digest(semantic(first)), digest(semantic(second)))


class PersistenceTests(unittest.TestCase):
    def test_evolution_promotes_then_plateaus(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "frontier.db"
            first = evolve(db)
            second = evolve(db)
            self.assertEqual(first["final_version"], "2.0.6")
            self.assertEqual(first["final_score"], 1.0)
            self.assertEqual(second["promotion_count"], 0)
            self.assertEqual(second["final_score"], 1.0)
            self.assertEqual(verify_chain(db)["status"], "PASSED")

    def test_restore_dump_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "a.db"
            second = Path(directory) / "b.db"
            evolve(first)
            sql = dump_database(first)
            restore_database(second, sql)
            self.assertEqual(dump_database(second), sql)


if __name__ == "__main__":
    unittest.main()
