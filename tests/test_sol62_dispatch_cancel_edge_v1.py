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

    def test_cancelled_effect_is_not_retryable_unknown_effect(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = Sol62Runtime(Path(td) / "sol")
            try:
                contract = EffectContract(
                    effect_id="effect-terminal-cancel",
                    provider="FUSE_GATEWAY",
                    operation="read",
                    target="runtime",
                    semantics="AT_MOST_ONCE",
                    consequential=False,
                    rollback_required=False,
                    idempotency_key="idem-terminal-cancel",
                )
                runtime.control.prepare_effect(contract, {})
                runtime.control.transition_effect(
                    "effect-terminal-cancel",
                    expected_state="PREPARED",
                    next_state="DISPATCHING",
                )
                runtime.control.transition_effect(
                    "effect-terminal-cancel",
                    expected_state="DISPATCHING",
                    next_state="CANCELLED",
                )
                decision = runtime.control.interrupted_effect_decision("effect-terminal-cancel")
                self.assertEqual(decision["action"], "NOOP_TERMINAL")
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()
