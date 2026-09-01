import unittest
from pathlib import Path

from benchmarking.omega_one_cfbe_local import run_campaign
from omega_one.hyperperformance import (
    ExactlyOnceFinalizer,
    FinalizationDecision,
    MissionMeasurement,
    OutcomeState,
    PairedMissionObservation,
    evaluate_paired_campaign,
)
from omega_one.interop import EffectClass, OmegaInteropSpine, UniversalCapabilityContract
from omega_one.portfolio import maturity_records, validate_blueprint_baseline
from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"


class OmegaOneCurrentReanchorTests(unittest.TestCase):
    def test_exact_100_capability_blueprint_is_preserved(self):
        result = validate_blueprint_baseline(maturity_records())
        self.assertEqual(result["record_count"], 100)
        self.assertEqual(result["unique_id_count"], 100)
        self.assertTrue(result["ids_exact"])
        self.assertTrue(result["all_zero_dilution"])

    def test_external_effect_contract_remains_held_without_sovara_authority(self):
        contract = UniversalCapabilityContract(
            capability_id="CAP-SEND",
            name="Send Message",
            description="Bounded effect test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            effect_class=EffectClass.EXTERNAL_EFFECT,
            rollback_required=True,
        )
        bundle = OmegaInteropSpine.compile(contract, mission_id="M-REANCHOR")
        self.assertFalse(bundle.mcp.execution_ready)
        self.assertEqual(bundle.mcp.hold_reason, "SOVARA_EFFECT_AUTHORITY_REQUIRED")
        self.assertFalse(bundle.a2a.execution_ready)

    def test_exactly_once_replay_keeps_one_canonical_receipt(self):
        finalizer = ExactlyOnceFinalizer()
        first = finalizer.finalize(
            "op-1", {"x": 1}, {"ok": True}, {"proof": "p"}, OutcomeState.SUCCEEDED
        )
        replay = finalizer.finalize(
            "op-1", {"x": 1}, {"ok": True}, {"proof": "p"}, OutcomeState.SUCCEEDED
        )
        self.assertEqual(first.decision, FinalizationDecision.COMMITTED)
        self.assertEqual(replay.decision, FinalizationDecision.REPLAYED)
        self.assertEqual(first.receipt, replay.receipt)
        self.assertEqual(finalizer.committed_count, 1)

    def test_paired_campaign_can_only_qualify_local_non_provider_measurement(self):
        pairs = tuple(
            PairedMissionObservation(
                MissionMeasurement(f"m-{i}", f"sha256:oracle-{i}", 10.0, 1.0),
                MissionMeasurement(f"m-{i}", f"sha256:oracle-{i}", 5.0, 1.0),
            )
            for i in range(30)
        )
        verdict = evaluate_paired_campaign(pairs)
        self.assertEqual(verdict.state, "QUALIFIED_LOCAL")
        self.assertIn("NO_PROVIDER", verdict.truth_boundary)

    def test_benchmark_harness_keeps_no_provider_truth_boundary(self):
        result = run_campaign(pair_count=3, operations=5, attempts=3)
        self.assertEqual(result["source"], "LOCAL_OBSERVED_NON_PROVIDER")
        self.assertIn("NO_PROVIDER", result["truth_boundary"])

    def test_current_proofos_selects_omega_one_without_full_fallback(self):
        policy = ProofPolicy.from_path(POLICY)
        impact = ImpactCompiler(policy).assess(
            [
                "omega_one/hyperperformance.py",
                "benchmarking/omega_one_cfbe_local.py",
                "tests/test_omega_one_current_reanchor_v1.py",
            ]
        )
        manifest = ProofSelector(policy).compile_manifest(
            base_sha="a" * 40,
            head_sha="b" * 40,
            impact=impact,
        )
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("omega_one_current_reanchor_v1", selected)
        self.assertIn("omega_one_v085_portfolio", selected)
        self.assertIn("omega_one_v085_promotion", selected)
        self.assertIn("omega_one_v085_schema_adapter", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])


if __name__ == "__main__":
    unittest.main()
