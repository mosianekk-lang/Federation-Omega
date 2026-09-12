import json
import os
import tempfile
import unittest

from federation.bubbles_autopilot_policy import (
    HIGH_CONSEQUENCE,
    NO_EFFECT,
    REVERSIBLE_EXTERNAL,
    REVERSIBLE_INTERNAL,
)
from federation.federation_autopilot_runtime import (
    FORBIDDEN_UNATTENDED_OPERATIONS,
    AutopilotCycleInput,
    AutopilotWorkItem,
    FederationAutopilotRuntime,
)


def work(
    work_id="W1",
    *,
    effect=NO_EFFECT,
    operation="INTERNAL_WORK",
    priority=1.0,
    blocked=False,
    alternate=False,
    authority=False,
    readback=False,
    owner_choice=False,
):
    return AutopilotWorkItem(
        work_id=work_id,
        objective=f"objective-{work_id}",
        effect_class=effect,
        operation_kind=operation,
        priority=priority,
        blocked=blocked,
        alternate_route_available=alternate,
        authority_proven=authority,
        provider_readback_available=readback,
        owner_choice_required=owner_choice,
    )


def cycle(*items, head=3, watermark=3, scheduled="2026-09-04T20:00:00+00:00", observed="2026-09-04T20:00:00+00:00"):
    return AutopilotCycleInput(
        source_ref="main:test",
        canonical_head=head,
        local_watermark=watermark,
        scheduled_at=scheduled,
        observed_at=observed,
        owner_present=False,
        work_items=tuple(items),
    )


class FederationAutopilotRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = FederationAutopilotRuntime()

    def test_01_no_effect_continues(self):
        r = self.runtime.run_cycle(cycle(work()))
        self.assertEqual(r.selected_work_ids, ("W1",))
        self.assertFalse(r.owner_interrupt_required)

    def test_02_internal_reversible_continues(self):
        r = self.runtime.run_cycle(cycle(work(effect=REVERSIBLE_INTERNAL)))
        self.assertEqual(r.selected_work_ids, ("W1",))

    def test_03_external_without_authority_holds(self):
        r = self.runtime.run_cycle(cycle(work(effect=REVERSIBLE_EXTERNAL)))
        self.assertEqual(r.held_work_ids, ("W1",))
        self.assertTrue(r.owner_interrupt_required)

    def test_04_external_with_authority_and_readback_continues(self):
        r = self.runtime.run_cycle(cycle(work(effect=REVERSIBLE_EXTERNAL, authority=True, readback=True)))
        self.assertEqual(r.selected_work_ids, ("W1",))
        self.assertTrue(r.provider_effect_authorized)

    def test_05_forbidden_email_stays_held_even_if_external_gate_proven(self):
        r = self.runtime.run_cycle(cycle(work(effect=REVERSIBLE_EXTERNAL, operation="EMAIL_SEND", authority=True, readback=True)))
        self.assertEqual(r.held_work_ids, ("W1",))
        self.assertFalse(r.provider_effect_authorized)

    def test_06_every_forbidden_operation_holds(self):
        for operation in FORBIDDEN_UNATTENDED_OPERATIONS:
            with self.subTest(operation=operation):
                r = self.runtime.run_cycle(cycle(work(effect=REVERSIBLE_EXTERNAL, operation=operation, authority=True, readback=True)))
                self.assertEqual(r.held_work_ids, ("W1",))

    def test_07_high_consequence_holds(self):
        r = self.runtime.run_cycle(cycle(work(effect=HIGH_CONSEQUENCE)))
        self.assertTrue(r.owner_interrupt_required)
        self.assertFalse(r.high_consequence_authorized)

    def test_08_owner_choice_holds(self):
        r = self.runtime.run_cycle(cycle(work(owner_choice=True)))
        self.assertEqual(r.held_work_ids, ("W1",))

    def test_09_blocked_with_alternate_reroutes(self):
        r = self.runtime.run_cycle(cycle(work(blocked=True, alternate=True)))
        self.assertEqual(r.reroute_work_ids, ("W1",))
        self.assertTrue(r.continue_without_owner)

    def test_10_blocked_without_route_holds(self):
        r = self.runtime.run_cycle(cycle(work(blocked=True)))
        self.assertEqual(r.held_work_ids, ("W1",))

    def test_11_stale_watermark_forces_catchup_before_normal_work(self):
        r = self.runtime.run_cycle(cycle(work(), head=4, watermark=3))
        self.assertTrue(r.catch_up_required)
        self.assertEqual(r.currentness_state, "ACTIVE_STALE_CATCH_UP_REQUIRED")
        self.assertEqual(r.held_work_ids, ("W1",))
        self.assertTrue(r.continue_without_owner)

    def test_12_watermark_cannot_exceed_head(self):
        with self.assertRaises(ValueError):
            self.runtime.run_cycle(cycle(head=2, watermark=3))

    def test_13_priority_order_is_deterministic(self):
        r = self.runtime.run_cycle(cycle(work("LOW", priority=1), work("HIGH", priority=9)))
        self.assertEqual(r.selected_work_ids, ("HIGH", "LOW"))

    def test_14_duplicate_work_ids_rejected(self):
        with self.assertRaises(ValueError):
            self.runtime.run_cycle(cycle(work("X"), work("X")))

    def test_15_missed_tick_counted(self):
        r = self.runtime.run_cycle(cycle(scheduled="2026-09-04T18:00:00+00:00", observed="2026-09-04T20:05:00+00:00"))
        self.assertEqual(r.missed_ticks, 2)

    def test_16_idle_cycle_is_valid_heartbeat(self):
        r = self.runtime.run_cycle(cycle())
        self.assertTrue(r.continue_without_owner)
        self.assertFalse(r.owner_interrupt_required)
        self.assertEqual(r.selected_work_ids, ())

    def test_17_receipt_hash_is_stable(self):
        a = self.runtime.run_cycle(cycle(work()))
        b = self.runtime.run_cycle(cycle(work()))
        self.assertEqual(a.receipt_sha256, b.receipt_sha256)

    def test_18_truth_boundary_names_consequential_holds(self):
        r = self.runtime.run_cycle(cycle())
        joined = " ".join(r.truth_boundary)
        self.assertIn("Email send", joined)
        self.assertIn("legal filing", joined)
        self.assertIn("IAM", joined)
        self.assertIn("billing", joined)


if __name__ == "__main__":
    unittest.main()
