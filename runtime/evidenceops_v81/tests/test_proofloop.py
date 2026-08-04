from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from proofloop import (  # noqa: E402
    AuthorityGateway,
    MatterTwin,
    MatterTwinError,
    ProofContractError,
    ValueLedger,
    compile_proof_contract,
    run_bounded_cycle,
    verify_release_state,
)


class ProofLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest_path = (
            HERE / "config" / "mpmb1435_26_control_manifest.json"
        )
        self.manifest = json.loads(
            self.manifest_path.read_text(encoding="utf-8")
        )

    def test_arbitrary_or_malformed_hash_is_rejected(self) -> None:
        candidate = json.loads(json.dumps(self.manifest))
        candidate["sources"][0]["sha256"] = "a" * 63
        with self.assertRaises(ProofContractError):
            compile_proof_contract(candidate)

    def test_verified_fact_requires_registered_source(self) -> None:
        twin = MatterTwin("MATTER-1")
        with self.assertRaises(MatterTwinError):
            twin.assert_fact(
                fact_id="F1",
                proposition="An unsupported proposition",
                classification="VERIFIED_FACT",
                source_ids=[],
            )

    def test_cross_matter_write_is_blocked(self) -> None:
        twin = MatterTwin("MATTER-1", excluded_matter_ids=["MATTER-2"])
        with self.assertRaises(MatterTwinError):
            twin.append_event(
                "ILLEGAL_CROSS_WRITE",
                {"value": True},
                target_matter_id="MATTER-2",
            )

    def test_verified_fact_cannot_be_silently_overwritten(self) -> None:
        twin = MatterTwin("MATTER-1")
        twin.register_source(
            {
                "source_id": "S1",
                "source_state": "VERIFIED_BYTES",
                "sha256": "1" * 64,
                "pages": 1,
                "external_effect": False,
            }
        )
        twin.assert_fact(
            fact_id="F1",
            proposition="Original fact",
            classification="VERIFIED_FACT",
            source_ids=["S1"],
        )
        with self.assertRaises(MatterTwinError):
            twin.assert_fact(
                fact_id="F1",
                proposition="Changed without supersession",
                classification="VERIFIED_FACT",
                source_ids=["S1"],
            )
        twin.supersede_fact(
            old_fact_id="F1",
            new_fact_id="F2",
            proposition="Properly superseding fact",
            classification="VERIFIED_FACT",
            source_ids=["S1"],
        )
        self.assertEqual(
            twin.state["facts"]["F1"]["superseded_by"], "F2"
        )

    def test_consequential_actions_are_denied(self) -> None:
        gateway = AuthorityGateway("A1")
        for action in ("send", "file", "serve", "publish", "settle"):
            decision = gateway.evaluate(action)
            self.assertFalse(decision.allowed)
            self.assertEqual(decision.external_effects, 0)
        self.assertTrue(gateway.evaluate("audit").allowed)

    def test_value_ledger_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            ledger = ValueLedger(path)
            ledger.append(
                {
                    "schema": "TEST",
                    "cycle_key": "C1",
                    "external_effects": 0,
                }
            )
            record = json.loads(
                path.read_text(encoding="utf-8").strip()
            )
            record["external_effects"] = 1
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaises(MatterTwinError):
                ledger.verify()

    def test_end_to_end_cycle_and_readback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            old_suffix = os.environ.get("EVIDENCEOPS_CYCLE_SUFFIX")
            os.environ["EVIDENCEOPS_CYCLE_SUFFIX"] = "unittest-e2e"
            try:
                receipt = run_bounded_cycle(self.manifest_path, state)
                verified = verify_release_state(state)
            finally:
                if old_suffix is None:
                    os.environ.pop("EVIDENCEOPS_CYCLE_SUFFIX", None)
                else:
                    os.environ["EVIDENCEOPS_CYCLE_SUFFIX"] = old_suffix
            self.assertEqual(receipt, verified)
            self.assertEqual(
                receipt["engineering_state"],
                "EVIDENCEOPS_V81_ENGINEERING_COMPLETE_VERIFIED",
            )
            self.assertEqual(
                receipt["longitudinal_state"],
                "ACTIVE_EVIDENCE_ACCUMULATING",
            )
            self.assertEqual(receipt["consequential_authority"], "HELD")
            self.assertEqual(receipt["external_effects"], 0)
            dashboard = json.loads(
                (state / "dashboard.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                dashboard["living_matter_twin"]["sources"], 4
            )
            self.assertEqual(dashboard["living_matter_twin"]["facts"], 5)
            self.assertEqual(
                dashboard["release_gate"]["state"],
                "INTERNAL_HOLD_DISPLAYED_FOR_REVIEW",
            )
            self.assertIn(
                "CROSS_MATTER_WRITE_BLOCKED",
                dashboard["controls_prevented"],
            )

    def test_replay_is_idempotent_inside_same_provider_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            old_suffix = os.environ.get("EVIDENCEOPS_CYCLE_SUFFIX")
            os.environ["EVIDENCEOPS_CYCLE_SUFFIX"] = "unittest-idempotent"
            try:
                first = run_bounded_cycle(self.manifest_path, state)
                event_count = len(
                    json.loads(
                        (state / "matter_twin.json").read_text()
                    )["events"]
                )
                ledger_count = len(
                    (state / "value_ledger.jsonl").read_text().splitlines()
                )
                second = run_bounded_cycle(self.manifest_path, state)
            finally:
                if old_suffix is None:
                    os.environ.pop("EVIDENCEOPS_CYCLE_SUFFIX", None)
                else:
                    os.environ["EVIDENCEOPS_CYCLE_SUFFIX"] = old_suffix
            self.assertEqual(
                first["value_cycle_sha256"],
                second["value_cycle_sha256"],
            )
            self.assertEqual(
                event_count,
                len(
                    json.loads(
                        (state / "matter_twin.json").read_text()
                    )["events"]
                ),
            )
            self.assertEqual(
                ledger_count,
                len((state / "value_ledger.jsonl").read_text().splitlines()),
            )

    def test_prohibited_inference_catalog_is_present(self) -> None:
        contract = compile_proof_contract(self.manifest)
        self.assertGreaterEqual(len(contract["prohibited_inferences"]), 5)
        self.assertTrue(
            any(
                "missing ccma reply" in item.casefold()
                for item in contract["prohibited_inferences"]
            )
        )


if __name__ == "__main__":
    unittest.main()
