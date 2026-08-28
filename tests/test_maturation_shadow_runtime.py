from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evidenceops.caseforge.maturation_shadow_runtime import (
    ShadowRuntimeInput,
    SuperiorLogicMaturationShadowRuntime,
    classify_trigger,
)


ROOT = Path(__file__).resolve().parents[1]


class MaturationShadowRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = SuperiorLogicMaturationShadowRuntime()

    def _input(
        self,
        *,
        event: str = "schedule",
        actor: str = "github-actions[bot]",
        successes: int = 0,
        manual: int = 0,
        system_dispatch: int = 0,
        head: str = "4f3c6286ba33f6d178c4b849eb51c69a0aa2f12c",
    ) -> ShadowRuntimeInput:
        return ShadowRuntimeInput(
            run_id=f"run-{successes + 1}",
            head_sha=head,
            event=event,
            actor=actor,
            observed_at="2026-08-28T00:00:00Z",
            previous_successful_cycles=successes,
            previous_manual_cycles=manual,
            previous_system_dispatch_cycles=system_dispatch,
        )

    def _assert_entrypoint_executes(self, prefix: list[str]) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "receipts"
            command = prefix + [
                "--output-dir",
                str(output_dir),
                "--run-id",
                "provider-entrypoint-regression",
                "--head-sha",
                "8563d8bc6d7df559cf65aaa5dd301e733c7ac011",
                "--event",
                "push",
                "--actor",
                "github-actions[bot]",
                "--observed-at",
                "2026-08-28T00:00:00Z",
                "--previous-successful-cycles",
                "0",
                "--previous-manual-cycles",
                "0",
                "--previous-system-dispatch-cycles",
                "0",
            ]
            completed = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                0,
                completed.returncode,
                msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
            )
            receipt = json.loads((output_dir / "maturation_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual("SHADOW_MATURATION_CYCLE_VERIFIED", receipt["status"])
            self.assertFalse(receipt["external_effect"])
            self.assertEqual("github-actions[bot]", receipt["actor"])
            self.assertEqual("SOURCE_PUSH_AUTOMATION", receipt["trigger_class"])
            self.assertFalse(receipt["current_owner_intervention"])
            self.assertTrue(receipt["transaction_id"].startswith("matx-"))
            self.assertTrue(receipt["idempotency_key"].startswith("maturation:"))

    def test_first_cycle_is_chat_independent_shadow_only(self) -> None:
        receipt = self.runtime.run(self._input())
        self.assertEqual("SHADOW_MATURATION_CYCLE_VERIFIED", receipt.status)
        self.assertEqual(1, receipt.cycle_number)
        self.assertEqual("SCHEDULED_AUTONOMY", receipt.trigger_class)
        self.assertFalse(receipt.current_owner_intervention)
        self.assertEqual(0.0, receipt.owner_intervention_rate)
        self.assertEqual("GAP-REPEATED-SHADOW-CYCLES", receipt.selected_gap_id)
        self.assertFalse(receipt.external_effect)
        self.assertFalse(receipt.self_sustaining)
        self.assertTrue(receipt.transaction_id.startswith("matx-"))
        self.assertTrue(receipt.idempotency_key.startswith("maturation:"))
        self.assertEqual("ACCUMULATE_THREE_REPEATED_PROVIDER_NATIVE_CYCLES", receipt.next_gate)

    def test_third_cycle_selects_closed_loop_candidate_qualification(self) -> None:
        receipt = self.runtime.run(self._input(successes=2, manual=0, system_dispatch=1))
        self.assertEqual(3, receipt.cycle_number)
        self.assertEqual("GAP-CLOSED-LOOP-CANDIDATE-QUALIFICATION", receipt.selected_gap_id)
        self.assertEqual("BRANCH_BOUND_CHALLENGER", receipt.candidate_work_package.experiment_class)
        self.assertEqual(
            "ADMIT_PR_ONLY_CANDIDATE_BUILDER_AND_INDEPENDENT_ASSURANCE",
            receipt.next_gate,
        )
        self.assertFalse(receipt.self_sustaining)

    def test_high_proven_human_rate_becomes_owner_burden_gap(self) -> None:
        receipt = self.runtime.run(self._input(successes=9, manual=3))
        self.assertEqual("GAP-OWNER-INTERVENTION-RATE", receipt.selected_gap_id)
        self.assertGreater(receipt.owner_intervention_rate, 0.10)
        self.assertFalse(receipt.self_sustaining)

    def test_work_package_explicitly_forbids_direct_main_and_authority_expansion(self) -> None:
        receipt = self.runtime.run(self._input(successes=2))
        prohibited = set(receipt.candidate_work_package.prohibited_effects)
        self.assertIn("direct_main_mutation", prohibited)
        self.assertIn("provider_authority_expansion", prohibited)
        self.assertIn("credential_scope_expansion", prohibited)
        self.assertFalse(receipt.candidate_work_package.external_effect)

    def test_same_head_cycle_and_gap_yield_stable_transaction_identity(self) -> None:
        first = self.runtime.run(self._input(successes=2))
        second = self.runtime.run(self._input(successes=2))
        self.assertEqual(first.transaction_id, second.transaction_id)
        self.assertEqual(first.idempotency_key, second.idempotency_key)
        different_epoch = self.runtime.run(
            self._input(
                successes=3,
                head="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            )
        )
        self.assertNotEqual(first.transaction_id, different_epoch.transaction_id)

    def test_write_receipts_persists_hash_verifiable_evidence(self) -> None:
        receipt = self.runtime.run(self._input())
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self.runtime.write_receipts(receipt, Path(temp_dir))
            self.assertEqual(3, len(paths))
            self.assertTrue(all(path.is_file() for path in paths))
            payload = json.loads(paths[0].read_text(encoding="utf-8"))
            expected = payload.pop("receipt_sha256")
            actual = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
            ).hexdigest()
            self.assertEqual(expected, actual)
            work = json.loads(paths[1].read_text(encoding="utf-8"))
            heartbeat = json.loads(paths[2].read_text(encoding="utf-8"))
            self.assertEqual(receipt.candidate_work_package.work_package_id, work["work_package_id"])
            self.assertEqual("SHADOW_MATURATION_CYCLE_VERIFIED", heartbeat["status"])
            self.assertEqual(receipt.actor, heartbeat["actor"])
            self.assertEqual(receipt.trigger_class, heartbeat["trigger_class"])
            self.assertFalse(heartbeat["external_effect"])

    def test_many_shadow_cycles_still_do_not_false_claim_self_sustaining(self) -> None:
        receipt = self.runtime.run(self._input(successes=99, manual=0))
        self.assertFalse(receipt.self_sustaining)
        missing = set(receipt.self_sustaining_missing)
        self.assertIn("automatic_repair_or_candidate_generation", missing)
        self.assertIn("independent_proof", missing)
        self.assertIn("verified_rollback", missing)
        self.assertIn("measurable_operational_value", missing)
        self.assertIn("cross_receiver_learning_with_compatibility_proof", missing)
        self.assertNotIn("owner_intervention_rate", missing)

    def test_human_dispatch_is_measured_not_hidden(self) -> None:
        receipt = self.runtime.run(
            self._input(
                event="workflow_dispatch",
                actor="mosianekk-lang",
                successes=0,
                manual=0,
            )
        )
        self.assertEqual("OWNER_OR_HUMAN_DISPATCH", receipt.trigger_class)
        self.assertTrue(receipt.current_owner_intervention)
        self.assertEqual(1.0, receipt.owner_intervention_rate)
        self.assertFalse(receipt.self_sustaining)

    def test_system_dispatched_canary_is_not_false_owner_burden(self) -> None:
        receipt = self.runtime.run(
            self._input(
                event="workflow_dispatch",
                actor="github-actions[bot]",
                successes=0,
                manual=0,
            )
        )
        self.assertEqual("SYSTEM_AUTOMATION_DISPATCH", receipt.trigger_class)
        self.assertFalse(receipt.current_owner_intervention)
        self.assertEqual(0.0, receipt.owner_intervention_rate)
        self.assertNotIn("owner_intervention_rate", receipt.self_sustaining_missing)

    def test_trigger_classification_is_actor_bound(self) -> None:
        self.assertEqual(
            "SYSTEM_AUTOMATION_DISPATCH",
            classify_trigger("workflow_dispatch", "github-actions[bot]"),
        )
        self.assertEqual(
            "OWNER_OR_HUMAN_DISPATCH",
            classify_trigger("workflow_dispatch", "mosianekk-lang"),
        )
        self.assertEqual("SCHEDULED_AUTONOMY", classify_trigger("schedule", "github-actions[bot]"))
        self.assertEqual("SOURCE_PUSH_AUTOMATION", classify_trigger("push", "mosianekk-lang"))

    def test_canonical_package_entrypoint_executes_from_repository_root(self) -> None:
        self._assert_entrypoint_executes(
            [sys.executable, "-m", "evidenceops.caseforge.maturation_shadow_cli"]
        )

    def test_compatibility_script_entrypoint_executes_from_repository_root(self) -> None:
        self._assert_entrypoint_executes(
            [sys.executable, str(ROOT / "tools" / "superior_logic_maturation_shadow.py")]
        )


if __name__ == "__main__":
    unittest.main()
