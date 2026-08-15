from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from realityguard import RealityGuard
from realityguard.capability import CapabilityRegistry
from realityguard.learning import LearningLedger, PromotionState
from realityguard.schema import InputError
from realityguard.solutions import ReuseAction, SolutionRouter


ROOT = Path(__file__).resolve().parents[1]


def scan_payload() -> dict:
    return {
        "claim": {"text": "The capability is built.", "claimed_state": "BUILT", "subject": "capability"},
        "evidence": [{"kind": "FILE", "supports_state": "BUILT", "grade": "ARTIFACT", "reference": "sha256:test"}],
        "context": {},
    }


def manifest(*capabilities: dict) -> dict:
    return {"capabilities": list(capabilities)}


def capability(capability_id: str, provides: list[str], state: str = "VERIFIED_SCOPED", **extra) -> dict:
    return {
        "capability_id": capability_id,
        "name": capability_id,
        "provides": provides,
        "state": state,
        "current": True,
        "authority_ceiling": "A1",
        "source_ref": "test:" + capability_id,
        **extra,
    }


class CapabilityRoutingTests(unittest.TestCase):
    def setUp(self):
        self.guard = RealityGuard()
        self.scan = self.guard.scan(scan_payload())

    def route(self, registry_payload: dict, required: list[str], **extra):
        request = {
            "objective": "preserve and deliver the owner objective",
            "required_capabilities": required,
            "available_authority": "A2",
            "allow_external_effects": False,
            "maximum_recurring_cost": 0,
            **extra,
        }
        return SolutionRouter().route(self.scan, request, CapabilityRegistry.from_dict(registry_payload))

    def test_single_verified_capability_is_adopted(self):
        result = self.route(manifest(capability("CAP-1", ["a", "b"])), ["a", "b"])
        self.assertEqual(result.reuse_action, ReuseAction.ADOPT)
        self.assertFalse(result.gap_proof_required)

    def test_source_present_capability_is_adapted_not_claimed_live(self):
        result = self.route(manifest(capability("CAP-1", ["a"], "SOURCE_PRESENT")), ["a"])
        self.assertEqual(result.reuse_action, ReuseAction.ADAPT)
        self.assertFalse(result.external_execution_claimed)

    def test_complementary_capabilities_are_composed(self):
        result = self.route(manifest(capability("CAP-1", ["a"]), capability("CAP-2", ["b"])), ["a", "b"])
        self.assertEqual(result.reuse_action, ReuseAction.COMPOSE)
        self.assertEqual(set(result.selected_capability_ids), {"CAP-1", "CAP-2"})

    def test_new_build_requires_proven_gap(self):
        result = self.route(manifest(capability("UNRELATED", ["z"])), ["a"])
        self.assertEqual(result.reuse_action, ReuseAction.BUILD_NEW_ONLY_IF_GAP)
        self.assertTrue(result.gap_proof_required)
        self.assertFalse(result.build_authorized)

    def test_semantic_duplicate_is_suppressed(self):
        low = capability("LOW", ["a"], "SOURCE_PRESENT")
        high = capability("HIGH", ["a"], "VERIFIED_SCOPED")
        result = self.route(manifest(low, high), ["a"])
        self.assertEqual(result.selected_capability_ids, ("HIGH",))
        self.assertEqual(result.suppressed_duplicates, ("LOW",))

    def test_stale_live_claim_is_rejected(self):
        stale = capability("STALE", ["a"], "LIVE_BOUND", current=False)
        result = self.route(manifest(stale), ["a"])
        self.assertEqual(result.reuse_action, ReuseAction.BUILD_NEW_ONLY_IF_GAP)
        self.assertIn({"capability_id": "STALE", "reason": "STALE_OR_UNVERIFIED"}, result.rejected)

    def test_unauthorized_external_effect_is_rejected(self):
        external = capability("EXTERNAL", ["a"], external_effect_required=True)
        result = self.route(manifest(external), ["a"])
        self.assertIn({"capability_id": "EXTERNAL", "reason": "EXTERNAL_EFFECT_NOT_AUTHORIZED"}, result.rejected)

    def test_false_claim_is_blocked_while_objective_is_preserved(self):
        payload = json.loads((ROOT / "examples/chatbridge_solution_request.json").read_text())
        capabilities = json.loads((ROOT / "examples/federation_capabilities.json").read_text())
        result = self.guard.resolve(payload, capabilities)
        self.assertEqual(result["truth"]["verdict"], "BLOCK_FALSE_REALITY")
        self.assertEqual(result["solution"]["decision"], "BLOCK_CLAIM_PRESERVE_OBJECTIVE")
        self.assertEqual(result["solution"]["reuse_action"], "COMPOSE")
        self.assertEqual(result["solution"]["capability_gaps"], [
            "browser_extension_installation",
            "live_warning_interception",
            "signed_in_session_binding",
            "successor_chat_semantic_readback",
        ])
        self.assertIn("browser_button_integration", result["solution"]["covered_capabilities"])
        self.assertEqual(result["solution"]["manual_user_tasks"], [])
        self.assertFalse(result["solution"]["build_authorized"])

    def test_capability_dilution_rule_is_logged(self):
        payload = scan_payload()
        payload["context"]["objective_dropped_after_block"] = True
        codes = {finding.code for finding in self.guard.scan(payload).findings}
        self.assertIn("RG-025", codes)

    def test_executor_fallthrough_is_critical(self):
        payload = scan_payload()
        payload["context"]["executor_continued_after_gate_failure"] = True
        result = self.guard.scan(payload)
        finding = next(item for item in result.findings if item.code == "RG-026")
        self.assertEqual(finding.severity, "CRITICAL")
        self.assertEqual(result.verdict.value, "BLOCK_FALSE_REALITY")

    def test_premature_greenfield_construction_is_logged(self):
        payload = scan_payload()
        payload["context"]["new_build_without_reuse_preflight"] = True
        result = self.guard.scan(payload)
        finding = next(item for item in result.findings if item.code == "RG-027")
        self.assertEqual(finding.severity, "HIGH")
        self.assertEqual(result.verdict.value, "REWRITE_REQUIRED")


class LearningLedgerTests(unittest.TestCase):
    def incident(self):
        return json.loads((ROOT / "examples/capability_dilution_incident.json").read_text())

    def test_duplicate_incident_increments_recurrence_without_duplicate_record(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "learning.json"
            ledger = LearningLedger(path)
            first = ledger.record(self.incident())
            second = ledger.record(self.incident())
            stored = json.loads(path.read_text())
        self.assertEqual(first.recurrence, 1)
        self.assertEqual(second.recurrence, 2)
        self.assertTrue(second.duplicate_suppressed)
        self.assertEqual(len(stored["incidents"]), 1)

    def test_tested_state_requires_regression_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(InputError):
                LearningLedger(Path(temp) / "learning.json").record(self.incident(), promotion_state=PromotionState.TESTED)

    def test_registration_and_behavior_proof_cannot_self_promote(self):
        with tempfile.TemporaryDirectory() as temp:
            for state in (PromotionState.REGISTERED, PromotionState.BEHAVIOR_PROVEN):
                with self.assertRaises(InputError):
                    LearningLedger(Path(temp) / "learning.json").record(
                        self.incident(), promotion_state=state, regression_tests=("test_canary",)
                    )

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "learning.json"
            receipt = LearningLedger(path).record(self.incident(), dry_run=True)
            self.assertFalse(path.exists())
            self.assertEqual(receipt.recurrence, 1)


class AdaptiveCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "realityguard.cli", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env={"PYTHONPATH": str(ROOT / "src")},
        )

    def test_resolve_cli_emits_truth_and_solution(self):
        proc = self.run_cli(
            "resolve", "--input", "examples/chatbridge_solution_request.json",
            "--capabilities", "examples/federation_capabilities.json",
        )
        self.assertEqual(proc.returncode, 3)
        value = json.loads(proc.stdout)
        self.assertIn("truth", value)
        self.assertIn("solution", value)

    def test_learn_cli_records_tested_incident(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / "learning.json")
            proc = self.run_cli(
                "learn", "--incident", "examples/capability_dilution_incident.json",
                "--ledger", path, "--promotion-state", "TESTED",
                "--regression-test", "test_false_claim_is_blocked_while_objective_is_preserved",
            )
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(json.loads(proc.stdout)["promotion_state"], "TESTED")


if __name__ == "__main__":
    unittest.main()
