from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from evidenceops.capability_heartbeat.engine import CapabilityHeartbeatEngine, HeartbeatError
from evidenceops.capability_heartbeat.tests.integration_helpers import NOW, authority, observation


ROOT = Path(__file__).resolve().parents[3]
REGISTRY = "evidenceops/capability_heartbeat/sources.json"
CONTEXT = "evidenceops/capability_heartbeat/current_workflow.json"


class CapabilityHeartbeatFacadeTests(unittest.TestCase):
    def test_verified_v4_is_the_only_recommendation_authority(self):
        active = authority()
        report = CapabilityHeartbeatEngine(ROOT, REGISTRY, authority=active).run(CONTEXT, now=NOW)
        self.assertEqual(report["source_count"], 8)
        self.assertTrue(report["decisions"])
        self.assertTrue(all(item["authority_ceiling"] == "A0" for item in report["decisions"]))
        self.assertTrue(all(item["policy_hash"] == active.policy.policy_hash for item in report["decisions"]))
        self.assertTrue(all(item["effectful_path_count"] == 0 for item in report["decisions"]))
        self.assertEqual(report["authority_source"], "VERIFIED_V4_FOUNDATION")
        self.assertFalse(any(report["live_awareness_flags"].values()))

    def test_catalogue_without_authority_cannot_recommend(self):
        engine = CapabilityHeartbeatEngine(ROOT, REGISTRY)
        sources, candidates = engine.collect()
        self.assertTrue(sources)
        self.assertTrue(candidates)
        self.assertTrue(all(not item.to_dict()["ingress_authorized"] for item in candidates))
        with self.assertRaisesRegex(HeartbeatError, "VERIFIED_V4_AUTHORITY_REQUIRED"):
            engine.run(CONTEXT, now=NOW)

    def test_external_catalogue_routes_are_never_selected(self):
        report = CapabilityHeartbeatEngine(ROOT, REGISTRY, authority=authority()).run(CONTEXT, now=NOW)
        selected = [
            decision["primary"] for decision in report["decisions"] if decision["primary"]
        ] + [
            item for decision in report["decisions"] for item in decision["assistants"]
        ]
        self.assertTrue(selected)
        self.assertTrue(all(not item["external_effect"] for item in selected))
        self.assertTrue(all(item["authority_source"] == "VERIFIED_V4_FOUNDATION" for item in selected))

    def test_context_rejects_raw_or_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = json.loads((ROOT / REGISTRY).read_text(encoding="utf-8"))
            source = registry["sources"][0]
            source["evidence_paths"] = ["proof.txt"]
            source["capabilities"] = [source["capabilities"][0]]
            (root / "proof.txt").write_text("synthetic", encoding="utf-8")
            (root / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
            context = {
                "schema": "EVIDENCEOPS-CURRENT-WORKFLOW-2",
                "fixture_mode": "SYNTHETIC_STATIC_WORKFLOW",
                "workflow_code": "WORKFLOW-SYNTHETIC",
                "workflow_version": 2,
                "requirements": [{
                    "requirement_id": "REQ-SYNTHETIC",
                    "tags": ["discover"],
                    "maximum_authority": "A0",
                    "effectful_permit": False,
                    "task_summary": "raw text is prohibited",
                }],
            }
            (root / "context.json").write_text(json.dumps(context), encoding="utf-8")
            with self.assertRaisesRegex(HeartbeatError, "unknown requirement field"):
                CapabilityHeartbeatEngine(root, "registry.json", authority=authority()).run(
                    "context.json", now=NOW
                )

    def test_registry_rejects_path_escape_and_non_synthetic_static_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = json.loads((ROOT / REGISTRY).read_text(encoding="utf-8"))
            registry["sources"][0]["evidence_paths"] = ["../secret"]
            (root / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
            with self.assertRaises(HeartbeatError):
                CapabilityHeartbeatEngine(root, "registry.json")
            registry["sources"][0]["evidence_paths"] = ["proof.txt"]
            registry["fixture_mode"] = "LIVE"
            (root / "proof.txt").write_text("synthetic", encoding="utf-8")
            (root / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
            with self.assertRaisesRegex(HeartbeatError, "explicitly synthetic"):
                CapabilityHeartbeatEngine(root, "registry.json")

    def test_duplicate_json_keys_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "registry.json").write_text(
                '{"schema":"EVIDENCEOPS-CAPABILITY-HEARTBEAT-2","schema":"EVIDENCEOPS-CAPABILITY-HEARTBEAT-2"}',
                encoding="utf-8",
            )
            with self.assertRaises(HeartbeatError):
                CapabilityHeartbeatEngine(root, "registry.json")

    def test_inventory_preserves_named_system_facades_without_granting_authority(self):
        systems = {
            item["system_code"]
            for item in CapabilityHeartbeatEngine(ROOT, REGISTRY).collect()[0]
        }
        self.assertTrue(
            {
                "SYSTEM-FEDERATION-OMEGA", "SYSTEM-SECONDARY-BRAIN",
                "SYSTEM-MODISA", "SYSTEM-EVIDENCEOPS",
            }.issubset(systems)
        )

    def test_missing_evidence_degrades_and_foundation_holds_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = {
                "source_id": "source-missing",
                "system_code": "SYSTEM-MISSING",
                "evidence_paths": ["missing.txt"],
                "capabilities": [{
                    "capability_id": "missing-capability",
                    "tags": ["discover"],
                    "route_code": "ROUTE-MISSING",
                    "state": "EXECUTABLE_NOW",
                    "proof_level": "TESTED",
                    "authority_class": "A0",
                    "external_effect": False,
                }],
            }
            registry = {
                "schema": "EVIDENCEOPS-CAPABILITY-HEARTBEAT-2",
                "version": 2,
                "fixture_mode": "SYNTHETIC_STATIC_CATALOGUE",
                "owner_code": "OWNER-A1B2C3D4",
                "matter_code": "MATTER-B1C2D3E4",
                "sources": [source],
            }
            context = {
                "schema": "EVIDENCEOPS-CURRENT-WORKFLOW-2",
                "fixture_mode": "SYNTHETIC_STATIC_WORKFLOW",
                "workflow_code": "WORKFLOW-SYNTHETIC",
                "workflow_version": 2,
                "requirements": [{
                    "requirement_id": "REQ-MISSING", "tags": ["discover"],
                    "maximum_authority": "A0", "effectful_permit": False,
                }],
            }
            (root / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
            (root / "context.json").write_text(json.dumps(context), encoding="utf-8")
            report = CapabilityHeartbeatEngine(
                root, "registry.json", authority=authority()
            ).run("context.json", now=NOW)
            self.assertEqual(report["heartbeats"][0]["status"], "DEGRADED")
            self.assertEqual(report["decisions"][0]["decision"], "GAP_OR_HELD")

    def test_unknown_requirement_returns_gap_without_fallback_authority(self):
        engine = CapabilityHeartbeatEngine(ROOT, REGISTRY, authority=authority())
        decision = engine.route_requirements(
            [{
                "requirement_id": "REQ-UNKNOWN", "tags": ["unmatched-tag"],
                "maximum_authority": "A0", "effectful_permit": False,
            }],
            now=NOW,
        )[0]
        self.assertEqual(decision["decision"], "GAP_OR_HELD")
        self.assertIsNone(decision["primary"])

    def test_source_fingerprint_changes_when_local_evidence_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            proof = root / "proof.txt"
            proof.write_text("one", encoding="utf-8")
            registry = {
                "schema": "EVIDENCEOPS-CAPABILITY-HEARTBEAT-2",
                "version": 2,
                "fixture_mode": "SYNTHETIC_STATIC_CATALOGUE",
                "owner_code": "OWNER-A1B2C3D4",
                "matter_code": "MATTER-B1C2D3E4",
                "sources": [{
                    "source_id": "source-one", "system_code": "SYSTEM-ONE",
                    "evidence_paths": ["proof.txt"],
                    "capabilities": [{
                        "capability_id": "capability-one", "tags": ["discover"],
                        "route_code": "ROUTE-ONE", "state": "VERIFY_ONLY",
                        "proof_level": "TESTED", "authority_class": "A0",
                        "external_effect": False,
                    }],
                }],
            }
            (root / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
            engine = CapabilityHeartbeatEngine(root, "registry.json")
            before = engine.collect()[0][0]["source_fingerprint"]
            proof.write_text("two", encoding="utf-8")
            after = engine.collect()[0][0]["source_fingerprint"]
            self.assertNotEqual(before, after)

    def test_duplicate_semantic_capability_is_coalesced_by_foundation(self):
        active = authority()
        first = observation(code="CAP-DUPLICATE")
        second = replace(first, confidence_bp=8000)
        result = active.recommend(observations=(first, second), now=NOW)
        self.assertEqual(len(result.recommendations), 1)
        self.assertEqual(result.recommendations[0].capability_code, "CAP-DUPLICATE")

    def test_report_does_not_emit_hash_only_bible_envelope(self):
        report = CapabilityHeartbeatEngine(ROOT, REGISTRY, authority=authority()).run(
            CONTEXT, now=NOW
        )
        self.assertNotIn("bible_node_heartbeat", report)
        self.assertFalse(any(report["live_awareness_flags"].values()))


if __name__ == "__main__":
    unittest.main()
