from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_level8_frontier_v1 import (
    InformationRoute,
    TimescaleObjective,
    compile_frontier_plan,
    multi_timescale_objective_plan,
    select_information_route,
)


class KimDataverseLevel8FrontierTests(unittest.TestCase):
    def test_multi_timescale_plan_preserves_long_horizon_option_value(self) -> None:
        ordered = multi_timescale_objective_plan(
            (
                TimescaleObjective("urgent", "NOW", 5, 5, 0, 1),
                TimescaleObjective("strategic", "LONG", 8, 2, 8, 1),
            )
        )
        self.assertEqual(2, len(ordered))
        self.assertIn("strategic", ordered)
        self.assertIn("urgent", ordered)

    def test_unknown_horizon_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            multi_timescale_objective_plan((TimescaleObjective("x", "FOREVER", 1, 1, 1, 1),))

    def test_information_route_prefers_information_and_value_per_cost_and_burden(self) -> None:
        route = select_information_route(
            (
                InformationRoute("heavy", 10, 10, 20, 20),
                InformationRoute("efficient", 8, 8, 1, 1),
            )
        )
        self.assertEqual("efficient", route)

    def test_external_effect_route_is_not_selected_by_information_budget(self) -> None:
        route = select_information_route((InformationRoute("effect", 100, 100, 0, 0, external_effect=True),))
        self.assertIsNone(route)

    def test_frontier_plan_never_authorizes_external_effect(self) -> None:
        plan = compile_frontier_plan(
            (TimescaleObjective("a", "NOW", 1, 1, 1, 0),),
            (InformationRoute("read", 1, 1, 0, 0),),
        )
        self.assertFalse(plan.external_effect_authorized)
        self.assertEqual("read", plan.information_route)

    def test_frontier_receipt_is_deterministic(self) -> None:
        objectives = (TimescaleObjective("a", "NOW", 1, 1, 1, 0),)
        routes = (InformationRoute("read", 1, 1, 0, 0),)
        self.assertEqual(compile_frontier_plan(objectives, routes).receipt, compile_frontier_plan(objectives, routes).receipt)


if __name__ == "__main__":
    unittest.main()
