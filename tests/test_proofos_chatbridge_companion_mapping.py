from __future__ import annotations

import unittest
from pathlib import Path

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
BASE = "1" * 40
HEAD = "2" * 40

CURRENT_PATHS = [
    "chatbridge-companion/manifest.json",
    "chatbridge-companion/package.json",
    "chatbridge-companion/src/background.js",
    "chatbridge-companion/src/bridge-core.js",
    "chatbridge-companion/src/content-script.js",
    "chatbridge-companion/tests/bridge-core.test.js",
    "bubbles/chatbridge_omega4/test_browser_companion_source_contract.py",
]

def compile_for(paths):
    policy = ProofPolicy.from_path(POLICY)
    impact = ImpactCompiler(policy).assess(paths)
    manifest = ProofSelector(policy).compile_manifest(
        base_sha=BASE, head_sha=HEAD, impact=impact
    )
    return policy, impact, manifest

class ChatBridgeCompanionProofOSMappingTests(unittest.TestCase):
    def test_current_companion_paths_use_bounded_court_without_full_fallback(self):
        _, impact, manifest = compile_for(CURRENT_PATHS)
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("CHATBRIDGE_COMPANION", impact.direct_subsystems)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertIn("chatbridge_companion_contract", selected)
        self.assertNotIn("full_federation_fallback", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])

    def test_companion_court_is_registered_and_subsystem_bounded(self):
        policy, _, _ = compile_for(CURRENT_PATHS)
        test = policy.tests["chatbridge_companion_contract"]
        self.assertEqual(test.kind, "unittest_module")
        self.assertEqual(
            test.target,
            "bubbles.chatbridge_omega4.test_browser_companion_source_contract",
        )
        self.assertEqual(test.block_scope, "SUBSYSTEM")

    def test_unknown_future_chatbridge_path_still_fails_safe(self):
        unknown = "chatbridge-next-generation/runtime.js"
        _, impact, manifest = compile_for([unknown])
        self.assertEqual((unknown,), impact.unmapped_production_paths)
        self.assertIn(
            "full_federation_fallback",
            {item.test_id for item in manifest.selected_tests},
        )

if __name__ == "__main__":
    unittest.main()
