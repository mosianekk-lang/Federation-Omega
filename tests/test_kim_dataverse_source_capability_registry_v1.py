from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_source_capability_registry_v1 import source_capability_registry


class KimDataverseSourceCapabilityRegistryTests(unittest.TestCase):
    def test_registry_has_unique_capability_ids(self) -> None:
        registry = source_capability_registry()
        ids = [item.capability_id for item in registry]
        self.assertEqual(len(ids), len(set(ids)))

    def test_source_registry_does_not_make_operational_claims(self) -> None:
        self.assertTrue(all(not item.operational_claim for item in source_capability_registry()))

    def test_registry_assigns_provider_and_workforce_roles_to_sovara_and_bubbles(self) -> None:
        by_id = {item.capability_id: item for item in source_capability_registry()}
        self.assertEqual("Bubbles", by_id["dynamic-organization"].owner_layer)
        self.assertEqual("SOVARA", by_id["provider-event-semantics"].owner_layer)


if __name__ == "__main__":
    unittest.main()
