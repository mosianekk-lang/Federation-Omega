import json
import unittest

from benchmarking.cfbe_omega.empirical_frontier_closure_v1 import (
    MINIMUM_OWNER_VALUE_PAIRS,
    ProofState,
    current_snapshot,
    held_external_lanes,
    next_executable_lanes,
    render_json,
)
from frontier_convergence.empirical_frontier_canary_v1 import hosted_canary_projection


class EmpiricalFrontierClosureV1Tests(unittest.TestCase):
    def test_exact_nine_lanes_and_provider_verified_gates(self):
        closure = current_snapshot()
        by_id = {lane.lane_id: lane for lane in closure.lanes}
        self.assertEqual(9, len(by_id))
        self.assertEqual(ProofState.PROVIDER_VERIFIED, by_id["WORKLOAD_IDENTITY"].state)
        self.assertEqual(ProofState.PROVIDER_VERIFIED, by_id["SLSA_ATTESTATION"].state)
        self.assertIn("github-actions:33450913670", by_id["WORKLOAD_IDENTITY"].evidence_refs)
        self.assertIn("github-attestation:44277491", by_id["SLSA_ATTESTATION"].evidence_refs)
        self.assertFalse(any(lane.provider_effect_authorized for lane in closure.lanes))
        self.assertFalse(any(lane.stable_promotion_authorized for lane in closure.lanes))

    def test_hosted_proof_does_not_inherit_serving_provider_deployment(self):
        closure = current_snapshot()
        runtime = next(lane for lane in closure.lanes if lane.lane_id == "DURABLE_RUNTIME")
        self.assertEqual(ProofState.HOSTED_VERIFIED, runtime.state)
        self.assertEqual(
            "SERVING_PROVIDER_DEPLOYMENT_AND_HEALTH_READBACK_REQUIRED",
            runtime.terminal_gate,
        )
        self.assertFalse(runtime.provider_effect_authorized)

    def test_toolbox_and_openrouter_are_not_overcertified(self):
        closure = current_snapshot()
        by_id = {lane.lane_id: lane for lane in closure.lanes}
        self.assertEqual(ProofState.SOURCE_READY, by_id["TOOLBOX_GOVERNANCE"].state)
        self.assertEqual(ProofState.HOLD_CREDENTIAL_BINDING, by_id["MULTI_PROVIDER_ROUTING"].state)
        self.assertIn("OPENROUTER_ACTIONS_CREDENTIAL_BINDING_REQUIRED", by_id["MULTI_PROVIDER_ROUTING"].terminal_gate)

    def test_owner_value_stays_held_until_real_minimum_cohort(self):
        held = current_snapshot(owner_value_pairs=0)
        owner = next(lane for lane in held.lanes if lane.lane_id == "OWNER_VALUE")
        self.assertEqual(ProofState.HOLD_REAL_OBSERVATIONS, owner.state)
        self.assertEqual("MINIMUM_10_OBSERVED_OWNER_VALUE_PAIRS_REQUIRED", owner.terminal_gate)

        eligible = current_snapshot(owner_value_pairs=MINIMUM_OWNER_VALUE_PAIRS)
        owner = next(lane for lane in eligible.lanes if lane.lane_id == "OWNER_VALUE")
        self.assertEqual(ProofState.HOSTED_VERIFIED, owner.state)
        self.assertIsNone(owner.terminal_gate)

    def test_closure_hash_and_json_are_deterministic(self):
        a = current_snapshot()
        b = current_snapshot()
        self.assertEqual(a.closure_sha256, b.closure_sha256)
        self.assertEqual(a.to_dict(), b.to_dict())
        decoded = json.loads(render_json())
        self.assertEqual(a.closure_sha256, decoded["closure_sha256"])
        self.assertEqual(9, decoded["lane_count"])

    def test_safe_next_lanes_exclude_credential_and_value_holds(self):
        closure = current_snapshot()
        executable = set(next_executable_lanes(closure))
        self.assertEqual(
            {"DURABLE_RUNTIME", "LIVE_AGENT_TELEMETRY", "TRACE_EVAL_OPTIMIZER", "AI_ASSET_VALUE_GOVERNANCE"},
            executable,
        )
        held = set(held_external_lanes(closure))
        self.assertIn("MULTI_PROVIDER_ROUTING", held)
        self.assertIn("OWNER_VALUE", held)
        self.assertIn("TOOLBOX_GOVERNANCE", held)

    def test_hosted_canary_is_no_effect_and_bound_to_closure(self):
        closure = current_snapshot()
        canary = hosted_canary_projection()
        self.assertEqual(closure.closure_sha256, canary["closure_sha256"])
        self.assertEqual(9, canary["lane_count"])
        self.assertFalse(canary["provider_effect_authorized"])
        self.assertFalse(canary["stable_promotion_authorized"])


if __name__ == "__main__":
    unittest.main()
