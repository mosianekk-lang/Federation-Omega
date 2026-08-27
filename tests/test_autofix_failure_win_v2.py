from __future__ import annotations

import json
import unittest

from ao_harmonic_v3.failure_win_v2 import (
    FailureEventType,
    FailureObservation,
    FailureToOperationalWinKernelV2,
    FailureWinRequest,
    FailureWinState,
    RecoveryRoute,
)
from ao_harmonic_v3.models import PerformanceVector
from bubbles.command_bus import build_receipt


class OmegaAutofixFailureWinV2ReceiverCanaryTests(unittest.TestCase):
    def test_cfre_native_recovery_then_v2_canary(self) -> None:
        command = {
            "schema": "BUBBLES-CONTROL-COMMAND-V1",
            "adapter_id": "bubbles_command_bus",
            "action": "recover_chat_failure",
            "effect": "READ",
            "target_alias": "EVIDENCEOPS_CFRE_LOCAL",
            "payload": {
                "event": {
                    "message": "tool call timeout",
                    "tool_inflight": True,
                    "tool_call_id": "fwv2-autofix-fixture",
                    "next_pending_action": "resume bounded operation",
                }
            },
        }
        receipt = build_receipt(
            json.dumps(command),
            actor="mosianekk-lang",
            event_name="pull_request",
            source_ref="FWV2-AUTOFIX-CANARY",
        )
        self.assertEqual("SUCCESS", receipt["state"])
        recovery = receipt["execution"]["recovery"]
        self.assertEqual("TOOL_OR_CONNECTOR_FAILURE", recovery["failure_class"])
        self.assertEqual("READBACK_TOOL_OUTCOME_BEFORE_RETRY", recovery["next_automated_action"])
        self.assertFalse(receipt["execution"]["provider_effects"])

        incumbent = PerformanceVector(quality=8, reliability=8, proof=8, speed=2, owner_burden=1)
        candidate = PerformanceVector(
            quality=8,
            reliability=8,
            proof=8,
            speed=5,
            owner_time_recovered=3,
            recovery_gain=3,
            owner_burden=0,
        )
        result = FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=FailureObservation(
                    event_id="FWV2-AUTOFIX-PRECURSOR-CANARY",
                    event_type=FailureEventType.PRECURSOR_RISK,
                    system_id="Ω-AUTOFIX",
                    objective="preempt a synthetic recovery-route recurrence",
                    claim="an in-flight tool failure may be replayed before readback",
                    observed_fruit="synthetic CFRE recovery receipt only; no provider effect",
                    desired_outcome="prewarm readback-before-retry and alternate-route recovery",
                    failure_code="SYNTHETIC_AUTOFIX_RECOVERY_DRIFT",
                    material=False,
                    precursor_signals=("tool-timeout-fixture", "readback-before-retry-fixture"),
                ),
                incumbent=incumbent,
                routes=(
                    RecoveryRoute(
                        route_id="autofix-readback-before-retry-fixture",
                        route_type="REROUTE",
                        performance=candidate,
                        proof_strength=1.0,
                        reversibility=1.0,
                        strategic_value=1.0,
                        expected_value=2.0,
                    ),
                ),
            )
        )
        self.assertEqual(FailureWinState.PREEMPTION_READY, result.state)
        self.assertTrue(result.vector_gate_passed)
        self.assertFalse(result.proof_graph.complete)
        self.assertNotEqual(FailureWinState.OPERATIONAL_WIN_VERIFIED, result.state)


if __name__ == "__main__":
    unittest.main()
