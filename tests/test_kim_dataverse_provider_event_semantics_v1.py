from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_provider_event_semantics_v1 import ProviderEventReceipt, ProviderEventState, evaluate_provider_event_semantics


class KimDataverseProviderEventSemanticsTests(unittest.TestCase):
    def test_full_provider_native_wait_wake_handoff_reaches_readback_verified(self) -> None:
        receipt = ProviderEventReceipt("e", "p", True, True, True, True, False, ProviderEventState.WOKEN)
        self.assertEqual(ProviderEventState.READBACK_VERIFIED, evaluate_provider_event_semantics(receipt))

    def test_event_wake_without_full_readback_does_not_overclaim(self) -> None:
        receipt = ProviderEventReceipt("e", "p", True, True, False, False, False, ProviderEventState.WOKEN)
        self.assertEqual(ProviderEventState.WOKEN, evaluate_provider_event_semantics(receipt))

    def test_zero_compute_wait_alone_is_waiting_not_provider_verified(self) -> None:
        receipt = ProviderEventReceipt("e", "p", True, False, False, False, False, ProviderEventState.WAITING)
        self.assertEqual(ProviderEventState.WAITING, evaluate_provider_event_semantics(receipt))

    def test_external_effect_receipt_is_held_in_read_only_semantics_court(self) -> None:
        receipt = ProviderEventReceipt("e", "p", True, True, True, True, True, ProviderEventState.WOKEN)
        self.assertEqual(ProviderEventState.HELD, evaluate_provider_event_semantics(receipt))


if __name__ == "__main__":
    unittest.main()
