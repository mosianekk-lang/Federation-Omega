from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sol_61_runtime.sol_62 import EffectContract, Sol62Runtime


class Sol62DispatchCancelEdgeTests(unittest.TestCase):
    def test_confirmed_pre_dispatch_failure_can_cancel_after_authorize(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = Sol62Runtime(Path(td) / "sol")
            try:
                contract = EffectContract(
                    effect_id="effect-cancel-edge",
                    provider="FUSE_GATEWAY",
                    operation="chat",
                    target="runtime",
                    semantics="IDEMPOTENT",
                    consequential=False,
                    rollback_required=False,
                    idempotency_key="idem-cancel-edge",
                    expected_readback={"status": "COMPLETE"},
                )
                runtime.control.prepare_effect(contract, {"intent": "canary"})
                runtime.control.transition_effect(
                    "effect-cancel-edge",
                    expected_state="PREPARED",
                    next_state="DISPATCHING",
                )
                cancelled = runtime.control.transition_effect(
                    "effect-cancel-edge",
                    expected_state="DISPATCHING",
                    next_state="CANCELLED",
                    result={"reason": "CONFIRMED_PRE_DISPATCH_FAILURE"},
                )
                self.assertEqual(cancelled["state"], "CANCELLED")
                self.assertEqual(
                    runtime.control.interrupted_effect_decision("effect-cancel-edge"),
                    {"action": "NOOP_TERMINAL", "state": "CANCELLED"},
                )
            finally:
                runtime.close()

    def test_dispatched_effect_still_cannot_be_cancelled_without_readback(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = Sol62Runtime(Path(td) / "sol")
            try:
                contract = EffectContract(
                    effect_id="effect-dispatched",
                    provider="FUSE_GATEWAY",
                    operation="chat",
                    target="runtime",
                    semantics="AT_MOST_ONCE",
                    consequential=False,
                    rollback_required=False,
                    idempotency_key="idem-dispatched",
                )
                runtime.control.prepare_effect(contract, {})
                runtime.control.transition_effect(
                    "effect-dispatched",
                    expected_state="PREPARED",
                    next_state="DISPATCHING",
                )
                runtime.control.transition_effect(
                    "effect-dispatched",
                    expected_state="DISPATCHING",
                    next_state="DISPATCHED",
                    provider_ref="provider-ref",
                )
                with self.assertRaisesRegex(Exception, "INVALID_EFFECT_TRANSITION"):
                    runtime.control.transition_effect(
                        "effect-dispatched",
                        expected_state="DISPATCHED",
                        next_state="CANCELLED",
                    )
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()
