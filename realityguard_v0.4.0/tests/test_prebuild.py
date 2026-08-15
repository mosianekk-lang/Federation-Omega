from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from realityguard.capability import CapabilityRegistry
from realityguard.prebuild import PrebuildDecisionCode, PrebuildGate, manifest_snapshot_hash
from realityguard.schema import InputError
from realityguard.solutions import ReuseAction


ROOT = Path(__file__).resolve().parents[1]


def capability(capability_id: str, provides: list[str], **extra) -> dict:
    return {
        "capability_id": capability_id,
        "name": capability_id,
        "provides": provides,
        "state": "VERIFIED_SCOPED",
        "current": True,
        "authority_ceiling": "A1",
        "source_ref": "test:" + capability_id,
        **extra,
    }


def manifest(*items: dict) -> dict:
    return {"capabilities": list(items)}


def request(manifest_payload: dict, required: list[str], *, new: bool = True, target: str = "", provides=None) -> dict:
    proposed = {
        "component_id": "PROPOSAL-1",
        "is_new_component": new,
        "provides": provides or required,
    }
    if target:
        proposed["existing_target_id"] = target
    return {
        "objective": "meet the objective without duplicate construction",
        "requested_capabilities": required,
        "proposed_component": proposed,
        "inventory": {
            "enumerated": True,
            "inspected_to_end": True,
            "snapshot_current": True,
            "snapshot_hash": manifest_snapshot_hash(manifest_payload),
            "sources": ["test:manifest"],
        },
        "gap_proof": {},
        "available_authority": "A2",
        "allow_external_effects": False,
        "maximum_recurring_cost": 0,
    }


class PrebuildGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = PrebuildGate()

    def test_unverified_inventory_blocks_before_build(self):
        capabilities = manifest(capability("CAP-1", ["a"]))
        payload = request(capabilities, ["a"])
        payload["inventory"]["inspected_to_end"] = False
        result = self.gate.evaluate(payload, capabilities)
        self.assertEqual(result.decision, PrebuildDecisionCode.BLOCK_BUILD_INVENTORY_UNVERIFIED)
        self.assertFalse(result.proposed_action_authorized)

    def test_manifest_hash_mismatch_blocks_stale_snapshot(self):
        capabilities = manifest(capability("CAP-1", ["a"]))
        payload = request(capabilities, ["a"])
        payload["inventory"]["snapshot_hash"] = "sha256:" + "0" * 64
        result = self.gate.evaluate(payload, capabilities)
        self.assertFalse(result.inventory_verified)
        self.assertEqual(result.decision, PrebuildDecisionCode.BLOCK_BUILD_INVENTORY_UNVERIFIED)

    def test_existing_complete_capability_blocks_duplicate_component(self):
        capabilities = manifest(capability("CAP-1", ["a", "b"]))
        result = self.gate.evaluate(request(capabilities, ["a", "b"]), capabilities)
        self.assertEqual(result.decision, PrebuildDecisionCode.BLOCK_DUPLICATE_BUILD)
        self.assertEqual(result.reuse_action, ReuseAction.ADOPT)
        self.assertTrue(result.reuse_route_authorized)
        self.assertFalse(result.build_authorized)

    def test_scoped_patch_of_existing_component_is_authorized(self):
        capabilities = manifest(capability("CAP-1", ["a"]))
        payload = request(capabilities, ["a", "b"], new=False, target="CAP-1", provides=["b"])
        result = self.gate.evaluate(payload, capabilities)
        self.assertEqual(result.decision, PrebuildDecisionCode.ROUTE_PATCH_EXISTING)
        self.assertEqual(result.reuse_action, ReuseAction.PATCH_EXISTING)
        self.assertTrue(result.proposed_action_authorized)
        self.assertEqual(result.authorized_build_scope, ("b",))

    def test_incomplete_patch_is_not_authorized(self):
        capabilities = manifest(capability("CAP-1", ["a"]))
        payload = request(capabilities, ["a", "b", "c"], new=False, target="CAP-1", provides=["b"])
        result = self.gate.evaluate(payload, capabilities)
        self.assertEqual(result.decision, PrebuildDecisionCode.ROUTE_PATCH_EXISTING)
        self.assertFalse(result.proposed_action_authorized)

    def test_multiple_partial_capabilities_route_to_composition(self):
        capabilities = manifest(capability("CAP-1", ["a"]), capability("CAP-2", ["b"]))
        result = self.gate.evaluate(request(capabilities, ["a", "b", "c"], provides=["c"]), capabilities)
        self.assertEqual(result.decision, PrebuildDecisionCode.ROUTE_COMPOSE_EXISTING)
        self.assertEqual(result.reuse_action, ReuseAction.COMPOSE)
        self.assertFalse(result.proposed_action_authorized)

    def test_missing_gap_proof_blocks_genuinely_uncovered_scope(self):
        capabilities = manifest(capability("UNRELATED", ["z"]))
        result = self.gate.evaluate(request(capabilities, ["a"]), capabilities)
        self.assertEqual(result.decision, PrebuildDecisionCode.BLOCK_BUILD_GAP_PROOF_REQUIRED)

    def test_exact_gap_proof_allows_bounded_new_component(self):
        capabilities = manifest(capability("UNRELATED", ["z"]))
        payload = request(capabilities, ["a"])
        payload["gap_proof"] = {
            "performed": True,
            "alternatives_evaluated": True,
            "uncovered_capabilities": ["a"],
            "evidence_refs": ["test:negative-capability-search"],
        }
        result = self.gate.evaluate(payload, capabilities)
        self.assertEqual(result.decision, PrebuildDecisionCode.ALLOW_BOUNDED_NEW_BUILD)
        self.assertTrue(result.proposed_action_authorized)
        self.assertEqual(result.authorized_build_scope, ("a",))

    def test_new_component_cannot_exceed_proven_gap(self):
        capabilities = manifest(capability("UNRELATED", ["z"]))
        payload = request(capabilities, ["a"], provides=["a", "unproven_extra"])
        payload["gap_proof"] = {
            "performed": True,
            "alternatives_evaluated": True,
            "uncovered_capabilities": ["a"],
            "evidence_refs": ["test:negative-capability-search"],
        }
        result = self.gate.evaluate(payload, capabilities)
        self.assertEqual(result.decision, PrebuildDecisionCode.BLOCK_BUILD_GAP_PROOF_REQUIRED)
        self.assertFalse(result.build_authorized)

    def test_chatbridge_replacement_is_blocked_as_duplicate(self):
        capabilities = json.loads((ROOT / "examples/federation_capabilities.json").read_text())
        required = [
            "browser_button_integration", "conversation_context_capture", "continuity_capsule",
            "target_context_injection", "continuation_validation", "route_preservation",
            "one_time_transfer",
        ]
        result = self.gate.evaluate(request(capabilities, required), capabilities)
        self.assertEqual(result.decision, PrebuildDecisionCode.BLOCK_DUPLICATE_BUILD)
        self.assertEqual(result.selected_capability_ids, ("CHATBRIDGE-COMPANION-0.2.0",))

    def test_chatbridge_lifecycle_gaps_cannot_justify_replacement_source(self):
        capabilities = json.loads((ROOT / "examples/federation_capabilities.json").read_text())
        required = [
            "browser_button_integration", "browser_extension_installation",
            "signed_in_session_binding", "live_warning_interception",
            "successor_chat_semantic_readback",
        ]
        payload = request(capabilities, required, provides=[
            "browser_extension_installation", "signed_in_session_binding",
            "live_warning_interception", "successor_chat_semantic_readback",
        ])
        gaps = [
            "browser_extension_installation", "signed_in_session_binding",
            "live_warning_interception", "successor_chat_semantic_readback",
        ]
        payload["gap_proof"] = {
            "performed": True,
            "alternatives_evaluated": True,
            "existing_adaptation_assessed": True,
            "adaptation_rejection_reasons": ["not applicable: these are execution states"],
            "uncovered_capabilities": gaps,
            "lifecycle_proof_gaps": gaps,
            "evidence_refs": ["local:chatbridge-companion/BUILD_CONTRACT.json"],
        }
        result = self.gate.evaluate(payload, capabilities)
        self.assertEqual(result.decision, PrebuildDecisionCode.BLOCK_BUILD_LIFECYCLE_GAP)
        self.assertFalse(result.build_authorized)

    def test_explicit_successor_suppresses_legacy_route(self):
        capabilities = manifest(
            capability("LEGACY", ["a"]),
            capability("CURRENT", ["a", "b"], supersedes=["LEGACY"]),
        )
        selection = CapabilityRegistry.from_dict(capabilities).select(["a"])
        self.assertEqual(tuple(item.capability_id for item in selection.selected), ("CURRENT",))
        self.assertIn("LEGACY", selection.suppressed_duplicates)

    def test_duplicate_capability_ids_are_invalid(self):
        with self.assertRaises(InputError):
            CapabilityRegistry.from_dict(manifest(capability("DUP", ["a"]), capability("DUP", ["b"])))


class PrebuildCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "realityguard.cli", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env={"PYTHONPATH": str(ROOT / "src")},
        )

    def test_cli_blocks_chatbridge_duplicate_with_dedicated_exit_code(self):
        proc = self.run_cli(
            "prebuild", "--input", "examples/chatbridge_prebuild_request.json",
            "--capabilities", "examples/federation_capabilities.json",
        )
        self.assertEqual(proc.returncode, 4)
        self.assertEqual(json.loads(proc.stdout)["decision"], "BLOCK_DUPLICATE_BUILD")

    def test_cli_allows_exact_genuine_gap(self):
        proc = self.run_cli(
            "prebuild", "--input", "examples/genuine_gap_prebuild_request.json",
            "--capabilities", "examples/genuine_gap_capabilities.json",
        )
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(json.loads(proc.stdout)["build_authorized"])


if __name__ == "__main__":
    unittest.main()
