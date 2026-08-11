from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent / "coordinator.py"
SPEC = importlib.util.spec_from_file_location("kimmie_workforce", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class KimmieWorkforceTests(unittest.TestCase):
    def test_manifest_has_exactly_199_unique_bots(self) -> None:
        manifest = MODULE.load_manifest()
        self.assertEqual(manifest["bot_count"], 199)
        self.assertEqual(len(manifest["bots"]), 199)
        self.assertEqual(len({b["bot_id"] for b in manifest["bots"]}), 199)
        self.assertEqual(len({b["collision_key"] for b in manifest["bots"]}), 199)

    def test_every_bot_is_packet_bound_and_proof_gated(self) -> None:
        deployment, receipt = MODULE.deploy()
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(deployment["assignment_count"], 199)
        self.assertTrue(all(p["state"] == "DEPLOYED_PACKET_BOUND" for p in deployment["assignments"]))
        self.assertTrue(all(p["lease"]["state"] == "RESERVED" for p in deployment["assignments"]))
        self.assertTrue(all(p["proof_requirements"] for p in deployment["assignments"]))
        self.assertTrue(all(p["completion_credit"] == "PROHIBITED_UNTIL_PROOF_AND_READBACK" for p in deployment["assignments"]))

    def test_independent_verifier_capacity_is_material(self) -> None:
        deployment, _ = MODULE.deploy()
        self.assertGreaterEqual(deployment["independent_verifier_count"], 40)

    def test_no_consequential_authority_is_granted(self) -> None:
        manifest = MODULE.load_manifest()
        authorities = {b["authority"] for b in manifest["bots"]}
        self.assertNotIn("A2", authorities)
        self.assertNotIn("UNBOUNDED", authorities)

    def test_runtime_boundary_is_truthful(self) -> None:
        manifest = MODULE.load_manifest()
        boundary = manifest["operating_boundary"]
        self.assertEqual(boundary["independent_model_processes"], "NOT_CLAIMED_WITHOUT_PROVIDER_RUNTIME_PROOF")
        self.assertEqual(boundary["financial_or_live_release"], "OWNER_GATE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
