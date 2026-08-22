import json
import unittest

from sovara_operator_adapter.cfbe_sovereign_core import SovereignCoreError
from sovara_operator_adapter.cfbe_sovereign_envelope import (
    ENVELOPE_CONTRACT,
    execute_envelope,
    execute_json,
)


def payload(operation="RANK_ROUTES"):
    return {
        "contract": ENVELOPE_CONTRACT,
        "operation": operation,
        "mission": {
            "objective_id": "OBJ-PORTABLE-1",
            "capability": "benchmark.read",
            "authority_required": "A0_READ",
            "provider_execution_required": True,
            "included_cost_only": True,
        },
        "state": {"horizon": "H50-TEST"},
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


class CFBESovereignEnvelopeTests(unittest.TestCase):
    def test_envelope_is_deterministic(self):
        first = execute_envelope(payload())
        second = execute_envelope(payload())
        self.assertEqual(first["response_fingerprint"], second["response_fingerprint"])

    def test_json_transport_round_trip(self):
        result = json.loads(execute_json(json.dumps(payload())))
        self.assertEqual(result["contract"], ENVELOPE_CONTRACT)
        self.assertEqual(result["objective_id"], "OBJ-PORTABLE-1")

    def test_host_surface_can_be_excluded_without_changing_contract(self):
        request = payload()
        request["mission"]["excluded_surface_classes"] = ["CHATGPT"]
        result = execute_envelope(request)
        self.assertEqual(result["selected_route"]["adapter_id"], "github")

    def test_failover_recomputes_route(self):
        request = payload("FAILOVER")
        request["failed_adapter_ids"] = ["chatgpt"]
        result = execute_envelope(request)
        self.assertEqual(result["selected_route"]["adapter_id"], "github")
        self.assertEqual(result["failed_adapter_ids"], ["chatgpt"])

    def test_provider_effect_is_not_claimed(self):
        result = execute_envelope(payload())
        self.assertIn("not proof", result["truth_boundary"])

    def test_unknown_contract_fails_closed(self):
        request = payload()
        request["contract"] = "OTHER"
        with self.assertRaises(SovereignCoreError):
            execute_envelope(request)


if __name__ == "__main__":
    unittest.main()
