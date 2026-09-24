from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.sol62_client_runtime.bible_embodiment import (
    BibleEmbodimentFabric,
    BibleEstateManifest,
)
from sol_61_runtime.sol_62 import GatewayPolicy, MissionSpec, Sol62Runtime, WorkloadIdentityPolicy
from sol_61_runtime.sol_62_complete_client_runtime import Sol62CompleteClientRuntime


ROOT = Path(__file__).resolve().parents[1]


class Sol62BibleEmbodimentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = Sol62Runtime(
            self.tmp.name,
            gateway_policy=GatewayPolicy("g", "sol-6.2"),
            identity_policy=WorkloadIdentityPolicy(
                allowed_issuers={"issuer"},
                audience="aud",
                subject_prefix="sub:",
                max_ttl_seconds=600,
            ),
        )
        self.client = Sol62CompleteClientRuntime(self.runtime)
        self.fabric = BibleEmbodimentFabric(self.client)

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def test_manifest_contains_full_registered_estate_and_strategic_sources(self):
        manifest = BibleEstateManifest()
        self.assertEqual(len(manifest.entries), 39)
        systems = {str(item["system"]) for item in manifest.entries}
        self.assertIn("FUSE Ω∞", systems)
        self.assertIn("Federation Omega", systems)
        self.assertIn("Strategic FUSE", systems)
        self.assertIn("Strategic FUSE Commercial", systems)
        self.assertIn("Human-First Ω", systems)
        self.assertIn("FORMATION-OMEGA Unified Powerhouse", systems)

    def test_manifest_registration_is_not_false_full_read(self):
        receipt = self.fabric.register_manifest(observed_epoch=100)
        self.assertEqual(receipt["entry_count"], 39)
        coverage = self.fabric.snapshot_coverage()
        self.assertTrue(coverage["full_inventory_registered"])
        self.assertFalse(coverage["all_registered_bibles_read"])
        self.assertEqual(coverage["snapshot_entries"], 0)

    def test_full_snapshot_is_hashed_chunked_and_has_no_authority_transfer(self):
        self.fabric.register_manifest(observed_epoch=100)
        entry = self.fabric.manifest.by_id("STRATEGIC-FUSE-INTELLIGENCE-AMPLIFIER-V2-I3")
        text = "Strategic FUSE source " + ("x" * 25000)
        stored = self.fabric.ingest_snapshot(
            bible_id=entry["bible_id"],
            source_ref=entry["primary_ref"],
            title=entry["primary_title"],
            text=text,
            revision="rev-1",
            observed_epoch=101,
        )
        value = stored["value"]
        self.assertEqual(value["char_count"], len(text))
        self.assertGreater(value["chunk_count"], 1)
        self.assertFalse(value["raw_text_is_authority"])
        self.assertFalse(value["maturity_inheritance"])
        chunks = self.client._rows("sol62.bible.chunk")
        self.assertEqual(len(chunks), value["chunk_count"])

    def test_unregistered_source_reference_fails_closed(self):
        self.fabric.register_manifest()
        with self.assertRaises(Exception):
            self.fabric.ingest_snapshot(
                bible_id="STRATEGIC-FUSE-INTELLIGENCE-AMPLIFIER-V2-I3",
                source_ref="unknown-source",
                title="x",
                text="nonempty",
            )

    def test_capsule_keeps_parent_organs_and_marks_unread_sources(self):
        self.fabric.register_manifest(observed_epoch=100)
        self.runtime.register_mission(
            MissionSpec(
                "m1",
                "strategic commercial runtime resilience and evidence integrity",
                {"state": "OPEN"},
                {"state": "DONE"},
            )
        )
        self.client.bind_mission("m1", owner_subject="owner")
        capsule = self.fabric.compile_capsule(
            mission_id="m1",
            objective="strategic commercial runtime resilience and evidence integrity",
            requested_systems=("Strategic FUSE", "EvidenceOps"),
            max_bibles=16,
        )
        systems = {row["system"] for row in capsule["sources"]}
        self.assertIn("FUSE Ω∞", systems)
        self.assertIn("Federation Omega", systems)
        self.assertIn("Strategic FUSE", systems)
        self.assertGreater(len(capsule["missing_source_reads"]), 0)
        self.assertIn("DOMAIN_AUTHORITY_PRESERVED", capsule["authority_rules"])
        self.assertIn("NO_AUTHORITY_TRANSFER", capsule["embodiment_rule"])

    def test_snapshot_then_capsule_hydrates_persisted_full_text_without_flattening(self):
        self.fabric.register_manifest(observed_epoch=100)
        entry = self.fabric.manifest.by_id("STRATEGIC-SECONDARY-BRAIN-CURRENT")
        source_text = (
            "Strategic Secondary Brain durable workspace causal graph counterfactual portfolio "
            "proof calibration and event-triggered replanning."
        )
        self.fabric.ingest_snapshot(
            bible_id=entry["bible_id"],
            source_ref=entry["primary_ref"],
            title=entry["primary_title"],
            text=source_text,
            revision="rev-current",
            observed_epoch=101,
        )
        self.runtime.register_mission(
            MissionSpec("m2", "strategic causal replanning", {"state":"OPEN"}, {"state":"DONE"})
        )
        self.client.bind_mission("m2", owner_subject="owner")
        capsule = self.fabric.compile_capsule(
            mission_id="m2",
            objective="strategic causal replanning",
            requested_systems=("Strategic FUSE",),
            max_bibles=16,
        )
        matches = [row for row in capsule["sources"] if row["bible_id"] == entry["bible_id"]]
        self.assertEqual(matches[0]["status"], "HYDRATED")
        self.assertTrue(matches[0]["full_text_persisted"])
        self.assertIn("causal graph", matches[0]["text_excerpt"])


if __name__ == "__main__":
    unittest.main()
