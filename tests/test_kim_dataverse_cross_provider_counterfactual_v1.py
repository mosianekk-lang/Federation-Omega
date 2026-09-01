from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_cross_provider_counterfactual_v1 import ProviderScenario, provider_loss_resilience, rank_provider_counterfactuals


class KimDataverseCrossProviderCounterfactualTests(unittest.TestCase):
    def test_unavailable_provider_is_excluded_without_global_failure(self) -> None:
        routes = rank_provider_counterfactuals(
            (
                ProviderScenario("google", False, 1.0, 1.0, 0, 10, False),
                ProviderScenario("openrouter", True, 0.9, 0.9, 1, 100, False),
            )
        )
        self.assertEqual(("openrouter",), tuple(item.provider_id for item in routes))

    def test_provider_verified_state_is_preserved_not_inferred(self) -> None:
        routes = rank_provider_counterfactuals((ProviderScenario("p", True, 0.9, 0.9, 1, 100, False),))
        self.assertFalse(routes[0].provider_live_claim)

    def test_two_available_routes_provide_provider_loss_resilience_candidate(self) -> None:
        scenarios = (
            ProviderScenario("a", True, 0.9, 0.9, 1, 100, True),
            ProviderScenario("b", True, 0.8, 0.9, 1, 100, False),
        )
        self.assertTrue(provider_loss_resilience(scenarios))

    def test_duplicate_provider_id_fails_closed(self) -> None:
        item = ProviderScenario("a", True, 0.9, 0.9, 1, 100, True)
        with self.assertRaises(ValueError):
            rank_provider_counterfactuals((item, item))


if __name__ == "__main__":
    unittest.main()
