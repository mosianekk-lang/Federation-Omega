from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evidenceops.capability_heartbeat.engine import CapabilityHeartbeatEngine, HeartbeatError


ROOT = Path(__file__).resolve().parents[3]
REGISTRY = "evidenceops/capability_heartbeat/sources.json"
CONTEXT = "evidenceops/capability_heartbeat/current_workflow.json"


class CapabilityHeartbeatTests(unittest.TestCase):
    def test_current_workflow_receives_all_named_heartbeats(self):
        report = CapabilityHeartbeatEngine(ROOT, REGISTRY).run(CONTEXT)
        systems = {item["system"] for item in report["heartbeats"]}
        self.assertTrue({"Federation Omega", "Secondary Brain / Kim DataVerse", "MODISA", "EvidenceOps"}.issubset(systems))
        self.assertEqual(report["source_count"], 8)
        self.assertFalse(report["external_execution_attempted"])

    def test_current_workflow_selects_primary_and_cross_system_assistants(self):
        report = CapabilityHeartbeatEngine(ROOT, REGISTRY).run(CONTEXT)
        self.assertTrue(all(item["primary"] for item in report["decisions"]))
        self.assertTrue(any(item["assistants"] for item in report["decisions"]))
        self.assertTrue(all(item["decision"] == "ADOPT_SUPERIOR_VERIFIED_ROUTE" for item in report["decisions"]))

    def test_effectful_routes_are_held_without_permit(self):
        report = CapabilityHeartbeatEngine(ROOT, REGISTRY).run(CONTEXT)
        held_reasons = {
            reason
            for decision in report["decisions"]
            for held in decision["held"]
            for reason in held["reasons"]
        }
        self.assertIn("EFFECTFUL_PERMIT_REQUIRED", held_reasons)
        self.assertTrue(all(item["effectful_path_count"] <= 1 for item in report["decisions"]))

    def test_missing_evidence_degrades_and_holds_capability(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = {
                "schema": "EVIDENCEOPS-CAPABILITY-HEARTBEAT-1",
                "sources": [{
                    "source_id": "missing-source",
                    "system": "Missing",
                    "evidence_paths": ["missing.txt"],
                    "capabilities": [self._capability("missing-cap")],
                }],
            }
            context = self._context(["discover"])
            self._write(root / "registry.json", registry)
            self._write(root / "context.json", context)
            report = CapabilityHeartbeatEngine(root, "registry.json").run("context.json")
            self.assertEqual(report["heartbeats"][0]["status"], "DEGRADED")
            self.assertEqual(report["decisions"][0]["decision"], "GAP_OR_HELD")

    def test_duplicate_semantic_route_is_collapsed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "evidence.txt").write_text("proof", encoding="utf-8")
            first = self._capability("cap-one")
            second = self._capability("cap-two")
            registry = {
                "schema": "EVIDENCEOPS-CAPABILITY-HEARTBEAT-1",
                "sources": [{
                    "source_id": "source-one",
                    "system": "One",
                    "evidence_paths": ["evidence.txt"],
                    "capabilities": [first, second],
                }],
            }
            self._write(root / "registry.json", registry)
            self._write(root / "context.json", self._context(["discover"]))
            decision = CapabilityHeartbeatEngine(root, "registry.json").run("context.json")["decisions"][0]
            self.assertEqual(decision["duplicate_candidates_removed"], 1)

    def test_safety_regression_cannot_win_on_quality(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "evidence.txt").write_text("proof", encoding="utf-8")
            unsafe = self._capability("unsafe", quality=1.0, safety=0.2)
            safe = self._capability("safe", quality=0.8, safety=0.95, route="safe-route")
            registry = {
                "schema": "EVIDENCEOPS-CAPABILITY-HEARTBEAT-1",
                "sources": [{
                    "source_id": "source-one",
                    "system": "One",
                    "evidence_paths": ["evidence.txt"],
                    "capabilities": [unsafe, safe],
                }],
            }
            context = self._context(["discover"])
            context["requirements"][0]["baseline_safety"] = 0.8
            self._write(root / "registry.json", registry)
            self._write(root / "context.json", context)
            decision = CapabilityHeartbeatEngine(root, "registry.json").run("context.json")["decisions"][0]
            self.assertEqual(decision["primary"]["capability_id"], "safe")
            self.assertIn("SAFETY_REGRESSION", decision["held"][0]["reasons"])

    def test_unknown_requirement_returns_gap(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "evidence.txt").write_text("proof", encoding="utf-8")
            registry = {
                "schema": "EVIDENCEOPS-CAPABILITY-HEARTBEAT-1",
                "sources": [{
                    "source_id": "source-one",
                    "system": "One",
                    "evidence_paths": ["evidence.txt"],
                    "capabilities": [self._capability("cap-one")],
                }],
            }
            self._write(root / "registry.json", registry)
            self._write(root / "context.json", self._context(["unmatched-tag"]))
            decision = CapabilityHeartbeatEngine(root, "registry.json").run("context.json")["decisions"][0]
            self.assertEqual(decision["decision"], "GAP_OR_HELD")

    def test_source_fingerprint_changes_with_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "evidence.txt"
            evidence.write_text("one", encoding="utf-8")
            registry = {
                "schema": "EVIDENCEOPS-CAPABILITY-HEARTBEAT-1",
                "sources": [{
                    "source_id": "source-one",
                    "system": "One",
                    "evidence_paths": ["evidence.txt"],
                    "capabilities": [self._capability("cap-one")],
                }],
            }
            self._write(root / "registry.json", registry)
            self._write(root / "context.json", self._context(["discover"]))
            engine = CapabilityHeartbeatEngine(root, "registry.json")
            before = engine.run("context.json")["heartbeats"][0]["source_fingerprint"]
            evidence.write_text("two", encoding="utf-8")
            after = engine.run("context.json")["heartbeats"][0]["source_fingerprint"]
            self.assertNotEqual(before, after)

    def test_registry_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = {
                "schema": "EVIDENCEOPS-CAPABILITY-HEARTBEAT-1",
                "sources": [{
                    "source_id": "source-one",
                    "system": "One",
                    "evidence_paths": ["../secret"],
                    "capabilities": [self._capability("cap-one")],
                }],
            }
            self._write(root / "registry.json", registry)
            with self.assertRaises(HeartbeatError):
                CapabilityHeartbeatEngine(root, "registry.json")

    @staticmethod
    def _capability(capability_id: str, *, quality: float = 0.8, safety: float = 0.9, route: str = "shared-route") -> dict:
        return {
            "capability_id": capability_id,
            "name": capability_id,
            "tags": ["discover", "reuse"],
            "route": route,
            "state": "EXECUTABLE_NOW",
            "proof_level": "TESTED",
            "quality": quality,
            "safety": safety,
            "reuse": 0.9,
            "cost": 0,
            "authority_class": "A0",
            "external_effect": False,
        }

    @staticmethod
    def _context(tags: list[str]) -> dict:
        return {
            "schema": "EVIDENCEOPS-CURRENT-WORKFLOW-1",
            "workflow_id": "test-workflow",
            "workflow_version": 1,
            "requirements": [{
                "requirement_id": "test-requirement",
                "tags": tags,
                "minimum_proof": "TESTED",
                "maximum_authority": "A1",
                "baseline_score": 0.2,
                "baseline_safety": 0,
                "improvement_threshold": 0.05,
                "effectful_permit": False,
            }],
        }

    @staticmethod
    def _write(path: Path, value: dict) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
