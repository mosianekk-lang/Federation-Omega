from __future__ import annotations

import unittest
from pathlib import Path

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
BASE = "1" * 40
HEAD = "2" * 40

DURABLE_PATHS = [
    "federation/durable_scheduler_bus_v1.py",
    "federation/durable_scheduler_virtual_org_v1.py",
    "scheduler/github_issue_bus.py",
    "virtual-org/operate.py",
    "virtual-org/durable-queue/FUSE-DURABLE-SCHEDULER-CANARY-001.json",
    "governance/proofos_omega_policy_extension_durable_scheduler_bus_v1.json",
]


def compile_for(paths):
    policy = ProofPolicy.from_path(POLICY)
    impact = ImpactCompiler(policy).assess(paths)
    manifest = ProofSelector(policy).compile_manifest(
        base_sha=BASE, head_sha=HEAD, impact=impact
    )
    return policy, impact, manifest


class DurableSchedulerProofOSMappingV1Tests(unittest.TestCase):
    def test_durable_paths_owned_without_full_fallback(self):
        _, impact, manifest = compile_for(DURABLE_PATHS)
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("DURABLE_SCHEDULER_BUS_V1", impact.direct_subsystems)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertIn("durable_scheduler_bus_v1_core", selected)
        self.assertIn("durable_scheduler_virtual_org_v1", selected)
        self.assertIn("durable_scheduler_proofos_mapping_v1", selected)
        self.assertNotIn("full_federation_fallback", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])

    def test_durable_proof_ids_registered(self):
        policy, _, _ = compile_for(DURABLE_PATHS)
        ids = set(policy.tests)
        self.assertIn("durable_scheduler_bus_v1_core", ids)
        self.assertIn("durable_scheduler_virtual_org_v1", ids)
        self.assertIn("durable_scheduler_proofos_mapping_v1", ids)

    def test_unknown_future_scheduler_path_still_fails_safe(self):
        unknown = "future_scheduler_unknown/runtime.py"
        _, impact, manifest = compile_for([unknown])
        self.assertEqual((unknown,), impact.unmapped_production_paths)
        self.assertIn("full_federation_fallback", {x.test_id for x in manifest.selected_tests})

    def test_authority_ceiling_unchanged(self):
        policy, _, _ = compile_for(DURABLE_PATHS)
        self.assertEqual("A1_INTERNAL", policy.raw["authority_ceiling"])
        self.assertFalse(policy.raw["external_effect_default"])


if __name__ == "__main__":
    unittest.main()
