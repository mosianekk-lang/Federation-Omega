from __future__ import annotations

import json
from pathlib import Path
import unittest

from benchmarking.cfbe_omega.toka_public_capability_harvest_v1 import (
    FUSE_TARGETS,
    RESTRICTED_DIRECT_REPLICATION,
    PUBLIC_SIGNALS,
    compile_cfbe_dna,
    evaluate_source_text,
    hypercube_pattern_specs,
    load_capabilities,
    validate_corpus,
)
from superior_logic.hypercube_bottleneck_resolver import MARKET_PATTERNS

ROOT = Path(__file__).resolve().parents[1]


class TokaPublicCapabilityHarvestTests(unittest.TestCase):
    def test_all_public_signals_are_present_and_unique(self):
        receipt = validate_corpus()
        self.assertEqual(41, receipt["capability_count"])
        self.assertEqual(41, len(PUBLIC_SIGNALS))
        self.assertEqual(41, len({row[0] for row in PUBLIC_SIGNALS}))
        self.assertEqual(41, len({row[2] for row in PUBLIC_SIGNALS}))

    def test_all_twelve_mission_use_cases_are_captured(self):
        names = {item.public_name for item in load_capabilities() if item.category == "MISSION_USE_CASE"}
        self.assertEqual({
            "Battlefield Reconnaissance", "Targeting & Tracking", "Counter Narcotics",
            "Suspect Surveillance", "Video & Vehicle Forensics", "SWAT Support",
            "Network Intelligence", "Systems Access & Collection", "Data Exfiltration",
            "Covert Entry", "Site Security", "Close Access Operations",
        }, names)

    def test_sensitive_public_concepts_are_transformed_not_directly_replicated(self):
        by_name = {item.public_name: item for item in load_capabilities()}
        for name in RESTRICTED_DIRECT_REPLICATION:
            item = by_name[name]
            self.assertTrue(item.restricted_direct_replication)
            self.assertNotEqual(name.lower(), item.safe_fuse_mechanism.lower())
        forbidden = ("exfiltrate data", "steal credentials", "weapon targeting", "malware payload", "bypass access control")
        self.assertTrue(all(
            not any(term in item.safe_fuse_mechanism.lower() for term in forbidden)
            for item in load_capabilities()
        ))

    def test_global_inheritance_targets_are_present_without_effect_authority(self):
        receipt = validate_corpus()
        self.assertFalse(receipt["external_effect_authorized"])
        self.assertGreaterEqual(len(FUSE_TARGETS), 10)
        self.assertTrue(all(item.fuse_targets == FUSE_TARGETS for item in load_capabilities()))

    def test_every_signal_compiles_to_cfbe_capability_dna(self):
        genes = compile_cfbe_dna()
        self.assertEqual(41, len(genes))
        self.assertEqual(41, len({gene.capability_id for gene in genes}))
        self.assertTrue(all(gene.license_class == "PUBLIC_FUNCTIONAL_DESCRIPTION_CLEAN_ROOM" for gene in genes))

    def test_seven_clean_room_hypercube_patterns_are_globally_loaded(self):
        specs = hypercube_pattern_specs()
        self.assertEqual(7, len(specs))
        self.assertTrue(all(spec["clean_room_only"] for spec in specs))
        ids = {item.pattern_id for item in MARKET_PATTERNS}
        self.assertTrue({spec["pattern_id"] for spec in specs}.issubset(ids))

    def test_synthetic_full_source_parity_reaches_terminal_state(self):
        corpus = " ".join(phrase for row in PUBLIC_SIGNALS for phrase in row[3])
        synthetic = {
            "mission": corpus,
            "home": corpus,
            "about": corpus,
            "platform_2026": corpus,
            "company_2026": corpus,
        }
        report = evaluate_source_text(synthetic)
        self.assertEqual(41, report["covered_count"])
        self.assertTrue(report["terminal"])
        self.assertEqual("COMPLETE_VERIFIED_PUBLIC_PARITY", report["state"])

    def test_missing_public_signal_remains_nonterminal(self):
        report = evaluate_source_text({"mission": "battlefield reconnaissance"})
        self.assertFalse(report["terminal"])
        self.assertTrue(report["missing_capability_ids"])
        self.assertEqual("NONTERMINAL_REHARVEST_REQUIRED", report["state"])

    def test_heartbeat_route_is_registered(self):
        data = json.loads((ROOT / "evidenceops" / "capability_heartbeat" / "sources.json").read_text(encoding="utf-8"))
        source = next(item for item in data["sources"] if item["source_id"] == "toka-public-capability-harvest")
        self.assertEqual("A0", source["capabilities"][0]["authority_class"])
        self.assertFalse(source["capabilities"][0]["external_effect"])

    def test_existing_scheduler_owns_repeat_loop(self):
        data = json.loads((ROOT / "scheduler" / "tasks.json").read_text(encoding="utf-8"))
        task = next(item for item in data["tasks"] if item["task_id"] == "EXT-015")
        self.assertEqual("hourly", task["cadence"])
        self.assertEqual("READY", task["state"])


if __name__ == "__main__":
    unittest.main()
