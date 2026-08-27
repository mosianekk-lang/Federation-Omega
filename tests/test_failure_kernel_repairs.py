import json
import unittest
from types import SimpleNamespace

import select_route_v2
from failure_win_execution_guard import (
    ExecutionBlocked,
    consume_then_execute,
    require_stage_budget,
)


REGISTRY = {
    "surfaces": [
        {
            "id": "formation",
            "state": "ACTIVE_PARTIAL",
            "proof": 5,
            "privacy": 5,
            "latency": 1,
            "write": False,
        }
    ],
    "bundles": [
        {
            "id": "continuity-safe",
            "goals": ["continuity"],
            "members": ["formation"],
            "fallback": [],
        },
        {
            "id": "formatting",
            "goals": ["formatting"],
            "members": ["formation"],
            "fallback": [],
        },
    ],
}


class SelectorRepairTests(unittest.TestCase):
    def test_failure_kernel_phrase_selects_continuity(self):
        route = select_route_v2.select(
            REGISTRY,
            "load the failure to operational win kernel and improve current work",
        )[0]
        self.assertEqual(route["bundle"], "continuity-safe")
        self.assertTrue(route["eligible"])

    def test_failure_recovery_phrase_selects_continuity(self):
        self.assertIn(
            "continuity",
            select_route_v2.normalized_goals("recover from this failure"),
        )

    def test_unrelated_improvement_does_not_overroute(self):
        goals = select_route_v2.normalized_goals("improve spreadsheet formatting")
        self.assertNotIn("continuity", goals)
        self.assertEqual(select_route_v2.select(REGISTRY, "improve spreadsheet formatting")[0]["bundle"], "formatting")

    def test_existing_propagation_alias_is_preserved(self):
        self.assertIn("continuity", select_route_v2.normalized_goals("propagate rules"))


class PermitGuardTests(unittest.TestCase):
    def test_leading_hyphen_token_is_bound_as_one_argument(self):
        calls = []
        executed = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"decision": "CONSUMED", "authorized": True}),
            )

        value = consume_then_execute(
            packet_path="packet.json",
            permit_token="-leading-token",
            permit_db="permits.sqlite",
            executor=lambda: executed.append(True) or "done",
            runner=runner,
            gate_path="formation_gate.py",
        )
        self.assertEqual(value, "done")
        self.assertEqual(calls[0][0][3], "--consume-permit=-leading-token")
        self.assertEqual(executed, [True])

    def test_executor_is_blocked_on_nonzero_consume(self):
        executed = []

        def runner(command, **kwargs):
            return SimpleNamespace(returncode=2, stdout="{}")

        with self.assertRaises(ExecutionBlocked):
            consume_then_execute(
                packet_path="packet.json",
                permit_token="token",
                permit_db="permits.sqlite",
                executor=lambda: executed.append(True),
                runner=runner,
                gate_path="formation_gate.py",
            )
        self.assertEqual(executed, [])

    def test_executor_is_blocked_on_unauthorized_receipt(self):
        executed = []

        def runner(command, **kwargs):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {"decision": "DENY", "authorized": False, "reasons": ["expired"]}
                ),
            )

        with self.assertRaisesRegex(ExecutionBlocked, "expired"):
            consume_then_execute(
                packet_path="packet.json",
                permit_token="token",
                permit_db="permits.sqlite",
                executor=lambda: executed.append(True),
                runner=runner,
                gate_path="formation_gate.py",
            )
        self.assertEqual(executed, [])


class BudgetGateTests(unittest.TestCase):
    def test_warmed_route_fits_before_execution(self):
        receipt = require_stage_budget(
            started_at=1000,
            deadline_seconds=300,
            proof_reserve_seconds=30,
            stage_estimates_seconds=[20, 20, 10],
            now=1020,
        )
        self.assertEqual(receipt, {"remainingSeconds": 280.0, "requiredSeconds": 80.0})

    def test_slow_preflight_is_pruned_before_provider_execution(self):
        with self.assertRaisesRegex(ExecutionBlocked, "remaining_budget_insufficient"):
            require_stage_budget(
                started_at=1000,
                deadline_seconds=300,
                proof_reserve_seconds=30,
                stage_estimates_seconds=[20, 20, 10],
                now=1245,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
