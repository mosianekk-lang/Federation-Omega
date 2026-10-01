from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from sol_61_runtime.sol_62 import (
    GatewayPolicy,
    MissionSpec,
    Sol62Runtime,
    TransitionSpec,
    WorkloadIdentityPolicy,
)
from sol_61_runtime.sol_62_complete_client_runtime import (
    Sol62CompleteClientRuntime,
    TransitionBinding,
)


class Sol62IntelligenceRuntimeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = int(time.time())
        self.rt = Sol62Runtime(
            Path(self.tmp.name) / "sol",
            gateway_policy=GatewayPolicy("sol-gateway", "sol-6.2"),
            identity_policy=WorkloadIdentityPolicy(
                allowed_issuers={"https://token.actions.githubusercontent.com"},
                audience="sol-runtime",
                subject_prefix="repo:mosianekk-lang/Federation-Omega:",
                max_ttl_seconds=600,
            ),
        )
        self.client = Sol62CompleteClientRuntime(self.rt)

    def tearDown(self):
        self.rt.close()
        self.tmp.cleanup()

    def _register(self, *, consequential=False, risk_class="LOW"):
        self.rt.register_mission(MissionSpec(
            "m-intel",
            "Resolve a difficult multi-stage mission with current evidence and verified reality.",
            {"state": "OPEN"},
            {"state": "DONE"},
            constraints=("CURRENT_EVIDENCE", "PROOF_REQUIRED"),
        ))
        self.rt.register_transition(TransitionSpec(
            "t-intel",
            "m-intel",
            "analyze",
            "fuse/result",
            {"state": "OPEN"},
            {"state": "DONE"},
            risk_class=risk_class,
            consequential=consequential,
            source_version="src1",
        ))
        self.client.bind_mission("m-intel", owner_subject="owner")
        self.client.bind_transition(TransitionBinding(
            "t-intel",
            {"intent": "analyze"},
            {"status": "COMPLETE"},
            rollback_required=consequential,
        ))

    def test_bind_mission_automatically_compiles_intelligence_plan(self):
        self._register()
        row = self.client._get(
            "sol62.client.intelligence_plan", "m-intel|MISSION"
        )
        self.assertIsNotNone(row)
        plan = row["value"]
        self.assertTrue(plan["plan_id"].startswith("IA-"))
        self.assertGreaterEqual(plan["reasoning_budget"], 1)
        self.assertIn("VALUE_OF_INFORMATION_NEXT_ACTION", plan["required_checks"])
        self.assertFalse(plan["authority_expansion"])
        self.assertFalse(plan["provider_effect_authorized"])

    def test_transition_refresh_increases_assurance_for_consequential_work(self):
        self._register(consequential=True, risk_class="CRITICAL")
        row = self.client.refresh_intelligence_plan(
            "m-intel", transition_id="t-intel"
        )
        plan = row["value"]
        self.assertEqual(plan["mode"], "ADVERSARIAL")
        self.assertGreaterEqual(plan["reasoning_budget"], 6)
        self.assertTrue(plan["independent_verifier_required"])
        self.assertIn("ROBUSTNESS_SENSITIVITY_GATE", plan["required_checks"])
        self.assertIn("STAGNATION_MUTATION_GUARD", plan["required_checks"])

    def test_mission_status_exposes_current_intelligence_plan(self):
        self._register()
        status = self.client.mission_status("m-intel", now_epoch=self.now)
        self.assertTrue(status["intelligence_plan"]["plan_id"].startswith("IA-"))
        self.assertEqual(status["intelligence_plan"]["mission_id"], "m-intel")


if __name__ == "__main__":
    unittest.main()
