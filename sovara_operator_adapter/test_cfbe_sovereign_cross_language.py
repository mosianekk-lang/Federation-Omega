import json
from pathlib import Path
import shutil
import subprocess
import unittest

from sovara_operator_adapter.cfbe_sovereign_envelope import (
    ENVELOPE_CONTRACT,
    execute_envelope,
)

ROOT = Path(__file__).resolve().parent
JS_ADAPTER = ROOT / "cfbe_sovereign_adapter.js"


def sample(operation="RANK_ROUTES"):
    return {
        "contract": ENVELOPE_CONTRACT,
        "operation": operation,
        "mission": {
            "objective_id": "OBJ-PARITY-1",
            "capability": "benchmark.read",
            "authority_required": "A0_READ",
            "provider_execution_required": True,
            "included_cost_only": True,
        },
        "state": {"benchmark": "CFBE"},
        "adapters": [
            {
                "adapter_id": "chatgpt",
                "surface_class": "CHATGPT",
                "capabilities": ["benchmark.read"],
                "authority_ceiling": "A1_INTERNAL",
                "presence_state": "CONNECTED_VERIFIED",
                "provider_execution_state": "PROVIDER_VERIFIED_SCOPED",
                "freshness_state": "CURRENT",
                "cost_class": "INCLUDED",
                "reversible": True,
                "semantic_readback": True,
                "proof_ref": "proof:chatgpt",
            },
            {
                "adapter_id": "google-runtime",
                "surface_class": "GOOGLE_RUNTIME",
                "capabilities": ["benchmark.read"],
                "authority_ceiling": "A1_INTERNAL",
                "presence_state": "CONNECTED_VERIFIED",
                "provider_execution_state": "PROVIDER_VERIFIED_SCOPED",
                "freshness_state": "CURRENT",
                "cost_class": "INCLUDED",
                "reversible": True,
                "semantic_readback": True,
                "proof_ref": "proof:google",
            },
            {
                "adapter_id": "github",
                "surface_class": "GITHUB_ACTIONS",
                "capabilities": ["benchmark.read"],
                "authority_ceiling": "A1_INTERNAL",
                "presence_state": "CONNECTED_VERIFIED",
                "provider_execution_state": "CI_AND_SOURCE_LIVE",
                "freshness_state": "CURRENT",
                "cost_class": "INCLUDED",
                "reversible": True,
                "semantic_readback": True,
                "proof_ref": "proof:github",
            },
        ],
    }


def run_js(payload):
    node = shutil.which("node")
    if not node:
        raise AssertionError("Node runtime is required for cross-language parity proof")
    script = r"""
const adapter = require(process.argv[1]);
const payload = JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(adapter.cfbeExecuteEnvelope(payload)));
"""
    completed = subprocess.run(
        [node, "-e", script, str(JS_ADAPTER), json.dumps(payload, separators=(",", ":"))],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


class CFBESovereignCrossLanguageTests(unittest.TestCase):
    def assert_route_parity(self, request):
        py = execute_envelope(request)
        js = run_js(request)
        self.assertEqual(py["objective_id"], js["objective_id"])
        self.assertEqual(py["operation"], js["operation"])
        self.assertEqual(
            [(r["adapter_id"], r["rank_score"]) for r in py["ranked_routes"]],
            [(r["adapter_id"], r["rank_score"]) for r in js["ranked_routes"]],
        )
        self.assertEqual(py["selected_route"]["adapter_id"], js["selected_route"]["adapter_id"])

    def test_rank_routes_parity(self):
        self.assert_route_parity(sample())

    def test_chatgpt_exclusion_parity(self):
        request = sample()
        request["mission"]["excluded_surface_classes"] = ["CHATGPT"]
        self.assert_route_parity(request)

    def test_failover_parity(self):
        request = sample("FAILOVER")
        request["failed_adapter_ids"] = ["chatgpt", "github"]
        self.assert_route_parity(request)

    def test_control_plane_rejected_by_both(self):
        request = sample()
        request["adapters"] = [
            {
                "adapter_id": "control",
                "surface_class": "GOOGLE_CONTROL_PLANE",
                "capabilities": ["benchmark.read"],
                "authority_ceiling": "A1_INTERNAL",
                "presence_state": "CONNECTED_VERIFIED",
                "provider_execution_state": "CONTROL_PLANE_ONLY",
                "freshness_state": "CURRENT",
                "cost_class": "INCLUDED",
                "reversible": True,
                "semantic_readback": False,
            }
        ]
        py = execute_envelope(request)
        js = run_js(request)
        self.assertEqual(py["ranked_routes"], [])
        self.assertEqual(js["ranked_routes"], [])
        self.assertIsNone(py["selected_route"])
        self.assertIsNone(js["selected_route"])


if __name__ == "__main__":
    unittest.main()
