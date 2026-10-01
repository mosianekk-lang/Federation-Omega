from __future__ import annotations

import json
import sys
import types
import unittest
from dataclasses import dataclass

from superior_logic.engineering_operator import SLOSEngineeringOperator
from superior_logic.engineering_runtime import SLOSReadinessCourt


class OperatorTests(unittest.TestCase):
    def request(self):
        return {
            "mission_id": "M-OP-1",
            "base_revision": "abc123",
            "objective": "build repository intelligence and verified engineering runtime",
            "required_capabilities": ["repository_intelligence", "prepared_workspace", "verification_supercourt"],
            "optional_capabilities": ["parallelism"],
            "repository_files": {
                "superior_logic/a.py": "def build_runtime():\n    return 1\n",
                "tests/test_a.py": "from superior_logic.a import build_runtime\n",
            },
            "toolchain": {"python": "3.13"},
            "dependencies": {},
        }

    def test_compile_is_deterministic_and_no_effect(self):
        op = SLOSEngineeringOperator()
        a = op.compile_blueprint(self.request())
        b = op.compile_blueprint(dict(reversed(list(self.request().items()))))
        self.assertEqual("COMPILED_NO_EFFECT", a.status)
        self.assertEqual(a.canonical_json(), b.canonical_json())
        self.assertEqual("M-OP-1", a.payload["mission_id"])
        self.assertTrue(a.payload["required_final_proofs"])

    def test_readiness_preserves_incomplete_truth(self):
        op = SLOSEngineeringOperator()
        rows = [{"signal_id": "SOURCE_ADMISSION", "passed": True, "proof_ref": "p1", "receiver": "ci"}]
        receipt = op.assess_readiness(rows)
        self.assertEqual("INCOMPLETE", receipt.status)
        self.assertIn("AIRLOCK", receipt.payload["missing"])

    def test_readiness_can_reach_ready_only_with_two_receivers(self):
        op = SLOSEngineeringOperator()
        rows = []
        for i, signal in enumerate(SLOSReadinessCourt.REQUIRED):
            rows.append({"signal_id": signal, "passed": True, "proof_ref": f"proof:{signal}", "receiver": "ci" if i % 2 == 0 else "independent"})
        receipt = op.assess_readiness(rows)
        self.assertEqual("SLOS_ENGINEERING_RUNTIME_READY", receipt.status)

    def test_tenx_delegates_to_codeforge_without_duplication(self):
        @dataclass
        class Metrics:
            task_set_id: str
            acceptance_hash: str
            accepted_task_rate: float
            median_wall_seconds: float
            owner_interventions: float
            tool_round_trips: float
            regression_escape_rate: float
            verified_readback_rate: float
            sample_size: int = 1
            median_cost: float = 0.0

        @dataclass
        class Verdict:
            multiplier: float
            target_met: bool
            hard_regression: bool
            reason: str

        class Court:
            def compare(self, b, c):
                self.last = (b, c)
                return Verdict(12.0, True, False, "TENX_VERIFIED")

        module = types.ModuleType("superior_logic.codeforge")
        module.EngineeringMetrics = Metrics
        module.TenXEngineeringCourt = Court
        old = sys.modules.get("superior_logic.codeforge")
        sys.modules["superior_logic.codeforge"] = module
        try:
            base = dict(task_set_id="same", acceptance_hash="same", accepted_task_rate=1.0, median_wall_seconds=100, owner_interventions=1, tool_round_trips=4, regression_escape_rate=0.0, verified_readback_rate=1.0, sample_size=30, median_cost=1.0)
            cand = dict(base, median_wall_seconds=10)
            receipt = SLOSEngineeringOperator().assess_tenx(base, cand)
            self.assertEqual("TENX_VERIFIED", receipt.status)
            self.assertEqual(12.0, receipt.payload["multiplier"])
        finally:
            if old is None:
                sys.modules.pop("superior_logic.codeforge", None)
            else:
                sys.modules["superior_logic.codeforge"] = old

    def test_tenx_requires_codeforge_when_absent(self):
        # Simulate a genuinely unavailable module even when codeforge.py exists
        # in the consolidated candidate. A None sys.modules entry makes Python
        # fail the relative import instead of re-importing the on-disk module.
        marker = object()
        old = sys.modules.get("superior_logic.codeforge", marker)
        sys.modules["superior_logic.codeforge"] = None
        try:
            with self.assertRaisesRegex(RuntimeError, "CODEFORGE_REQUIRED_FOR_TENX_COURT"):
                SLOSEngineeringOperator().assess_tenx({}, {})
        finally:
            if old is marker:
                sys.modules.pop("superior_logic.codeforge", None)
            else:
                sys.modules["superior_logic.codeforge"] = old


if __name__ == "__main__":
    unittest.main()
