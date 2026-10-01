import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _run_node(path: str) -> dict:
    proc = subprocess.run(
        ["node", str(ROOT / path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    return json.loads(proc.stdout)


class HyperIntelligencePerformanceBindingTests(unittest.TestCase):
    def test_hyper_intelligence_performance_court(self) -> None:
        report = _run_node("benchmarks/hyper_intelligence_performance_court_v1.mjs")
        self.assertTrue(report["passed"])
        self.assertEqual(report["cases"], 20)
        self.assertEqual(report["failures"], [])

    def test_hyper_binding_is_in_bootstrap_and_mirror_contracts(self) -> None:
        mirror = json.loads((ROOT / "config" / "fuse-output-mirror-v3.json").read_text(encoding="utf-8"))
        bootstrap = json.loads((ROOT / "config" / "fuse-bootstrap-inheritance-v3.json").read_text(encoding="utf-8"))
        manifest = json.loads((ROOT / "respawn" / "federation_manifest.json").read_text(encoding="utf-8"))

        hipb = mirror["hyper_intelligence_performance"]
        self.assertEqual(hipb["contract_id"], "FUSE-HIPB-001")
        self.assertTrue(hipb["enabled"])
        self.assertEqual(hipb["version"], "2.0.0")
        self.assertTrue(hipb["matched_benchmark_required_for_hyper_performance_claim"])
        self.assertEqual(hipb["owner_intent_drift_ceiling"], 0)
        self.assertEqual(hipb["unrequested_recurrence_ceiling"], 0)
        self.assertEqual(hipb["executable_next_action_withheld_ceiling"], 0)
        self.assertTrue(hipb["self_repair_required_on_assistant_caused_reversible_drift"])

        order = bootstrap["required_order"]
        self.assertIn("HYPER_INTELLIGENCE_PERFORMANCE_BINDING", order)
        self.assertLess(order.index("HYPER_INTELLIGENCE_PERFORMANCE_BINDING"), order.index("ROUTE_COMPILE"))
        self.assertEqual(bootstrap["hyper_intelligence_performance"]["contract_id"], "FUSE-HIPB-001")

        boot = manifest["bootstrap_order"]
        self.assertIn("load_hyper_intelligence_performance_contract", boot)
        self.assertIn("compile_hyper_intelligence_plan", boot)
        self.assertIn("hyper_pre_compile_gate", boot)
        self.assertIn("hyper_pre_effect_gate", boot)
        self.assertIn("hyper_post_effect_update", boot)
        self.assertLess(boot.index("compile_hyper_intelligence_plan"), boot.index("execute"))
        self.assertLess(boot.index("hyper_pre_compile_gate"), boot.index("execute"))
        self.assertLess(boot.index("hyper_pre_effect_gate"), boot.index("execute"))
        self.assertGreater(boot.index("hyper_post_effect_update"), boot.index("execute"))
        self.assertIn("HYPER_INTELLIGENCE_PERFORMANCE_BINDING_REQUIRED", manifest["bootstrap_invariants"])
        self.assertIn("HYPER_PERFORMANCE_CLAIMS_REQUIRE_MATCHED_EMPIRICAL_PROOF", manifest["bootstrap_invariants"])

    def test_source_binding_does_not_inflate_runtime_proof(self) -> None:
        governance = json.loads(
            (ROOT / "governance" / "hyper_intelligence_performance_binding_v1.json").read_text(encoding="utf-8")
        )
        boundary = governance["truth_boundary"]
        self.assertFalse(boundary["sentience_claimed"])
        self.assertFalse(boundary["omniscience_claimed"])
        self.assertTrue(boundary["hyper_performance_requires_matched_empirical_proof"])
        self.assertFalse(boundary["source_binding_proves_live_owner_runtime"])
        self.assertFalse(boundary["source_binding_proves_universal_provider_enforcement"])
        self.assertEqual(governance["version"], "2.0.0")
        hooks = governance["sovereign_kernel_hooks"]
        self.assertEqual(hooks["schema"], "FUSE_SOVEREIGN_ADAPTIVE_COGNITION_HOOK_V2")
        self.assertEqual(hooks["phases"], ["PRE_COMPILE", "PRE_EFFECT", "POST_EFFECT"])
        self.assertFalse(hooks["authority_expansion"])


if __name__ == "__main__":
    unittest.main()
