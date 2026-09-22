from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_persistent_carrier_contract_v1 import (
    CarrierCapability,
    CarrierKind,
    no_chat_continuity_claim,
    qualify_carrier,
    select_carrier,
)


class KimDataversePersistentCarrierContractTests(unittest.TestCase):
    def test_complete_internal_carrier_is_level7_continuity_candidate(self) -> None:
        qualification = qualify_carrier(
            CarrierCapability(
                carrier_id="durable-internal",
                kind=CarrierKind.DURABLE_WORKER,
                durable_state=True,
                cross_process_resume=True,
                event_wake=True,
                zero_compute_wait=True,
                idempotent_step=True,
                independent_readback=True,
            )
        )
        self.assertTrue(qualification.level7_continuity_candidate)
        self.assertEqual((), qualification.missing)
        self.assertFalse(qualification.external_effect_authorized)

    def test_external_carrier_requires_provider_verification_for_candidate(self) -> None:
        qualification = qualify_carrier(
            CarrierCapability(
                carrier_id="provider",
                kind=CarrierKind.CLOUD_RUN,
                durable_state=True,
                cross_process_resume=True,
                event_wake=True,
                zero_compute_wait=True,
                idempotent_step=True,
                independent_readback=True,
                external_effect=True,
                provider_verified=False,
            )
        )
        self.assertFalse(qualification.level7_continuity_candidate)
        self.assertFalse(qualification.external_effect_authorized)

    def test_missing_event_wake_and_wait_are_visible(self) -> None:
        qualification = qualify_carrier(
            CarrierCapability(
                carrier_id="github",
                kind=CarrierKind.GITHUB_ACTIONS,
                durable_state=True,
                cross_process_resume=True,
                event_wake=False,
                zero_compute_wait=False,
                idempotent_step=True,
                independent_readback=True,
            )
        )
        self.assertEqual(("event_wake", "zero_compute_wait"), qualification.missing)

    def test_no_chat_continuity_requires_observed_resumes_not_source_shape(self) -> None:
        qualification = qualify_carrier(
            CarrierCapability(
                carrier_id="worker",
                kind=CarrierKind.DURABLE_WORKER,
                durable_state=True,
                cross_process_resume=True,
                event_wake=True,
                zero_compute_wait=True,
                idempotent_step=True,
                independent_readback=True,
            )
        )
        self.assertFalse(no_chat_continuity_claim(qualification=qualification, observed_resume_receipts=("a", "b")))
        self.assertTrue(no_chat_continuity_claim(qualification=qualification, observed_resume_receipts=("a", "b", "c")))

    def test_duplicate_receipts_do_not_inflate_observed_continuity(self) -> None:
        qualification = qualify_carrier(
            CarrierCapability(
                carrier_id="worker",
                kind=CarrierKind.DURABLE_WORKER,
                durable_state=True,
                cross_process_resume=True,
                event_wake=True,
                zero_compute_wait=True,
                idempotent_step=True,
                independent_readback=True,
            )
        )
        self.assertFalse(no_chat_continuity_claim(qualification=qualification, observed_resume_receipts=("same", "same", "same")))

    def test_external_selection_fails_without_provider_verified_carrier(self) -> None:
        carrier = CarrierCapability(
            carrier_id="cloud",
            kind=CarrierKind.CLOUD_RUN,
            durable_state=True,
            cross_process_resume=True,
            event_wake=True,
            zero_compute_wait=True,
            idempotent_step=True,
            independent_readback=True,
            external_effect=True,
            provider_verified=False,
        )
        self.assertIsNone(select_carrier((carrier,), require_external_effect=True))


if __name__ == "__main__":
    unittest.main()
