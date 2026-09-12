from __future__ import annotations

from pathlib import Path
import unittest

from ao_harmonic_v3.high_coupling_policy_shadow import run_c4_high_coupling_policy_shadow
from evidenceops.caseforge.blind_runner import BlindIsolationError, ModelBinding, assert_blind_payload
from evidenceops.caseforge.replication import IndependentReplicationGate, ReplicationRun
from evidenceops.caseforge.scientia import EpistemicState, Hypothesis, ScientificObservation, ScientiaKernel
from superior_logic.runtime import DONE_PREDICATES, SuperiorLogicRuntime

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "superior-logic-maturation-shadow.yml"
WRAPPER = ROOT / "tools" / "superior_logic_maturation_shadow.py"
CLI = ROOT / "evidenceops" / "caseforge" / "maturation_shadow_cli.py"


class ForestFirstC4RepositoryShellBindingTests(unittest.TestCase):
    def test_superior_logic_workflow_uses_caseforge_canonical_entrypoint(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        wrapper = WRAPPER.read_text(encoding="utf-8")
        cli = CLI.read_text(encoding="utf-8")
        self.assertIn("python -m evidenceops.caseforge.maturation_shadow_cli", workflow)
        self.assertIn("evidenceops/caseforge/maturation_shadow_runtime.py", workflow)
        self.assertIn("evidenceops/caseforge/maturation_shadow_cli.py", workflow)
        self.assertIn("Compatibility entrypoint", wrapper)
        self.assertIn("from evidenceops.caseforge.maturation_shadow_cli import main", wrapper)
        self.assertIn("from .maturation_shadow_runtime import", cli)

    def test_workflow_remains_read_only_and_no_effect(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("contents: read", workflow)
        self.assertIn("actions: read", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("assert receipt['external_effect'] is False", workflow)
        self.assertIn("assert receipt['self_sustaining'] is False", workflow)

    def test_c4_portable_shadow_is_green_from_repository_shell(self):
        report = run_c4_high_coupling_policy_shadow()
        self.assertEqual(report["scenario_count"], 10)
        self.assertTrue(report["pass"])
        self.assertFalse(report["external_effect"])
        self.assertFalse(report["physical_migration_executed"])
        self.assertFalse(report["provider_runtime_proved"])
        self.assertFalse(report["superior_logic_runtime_rewired"])
        self.assertFalse(report["caseforge_authority_expanded"])

    def test_real_superior_logic_completion_gate_fails_closed(self):
        runtime = SuperiorLogicRuntime(":memory:")
        try:
            complete = {name: True for name in DONE_PREDICATES}
            done, missing = runtime.derive_done(complete)
            self.assertTrue(done)
            self.assertEqual([], missing)

            incomplete = dict(complete)
            incomplete["independent_observation_verified"] = False
            done, missing = runtime.derive_done(incomplete)
            self.assertFalse(done)
            self.assertIn("independent_observation_verified", missing)
        finally:
            runtime.close()

    def test_real_caseforge_scientia_requires_competing_falsifiable_hypotheses(self):
        scientia = ScientiaKernel()
        observations = (
            ScientificObservation(
                "O1",
                "Observed source behavior",
                EpistemicState.VERIFIED_FACT,
                ("SRC-1",),
            ),
        )
        hypotheses = (
            Hypothesis(
                "H1",
                "Policy split preserves behavior",
                ("C4 remains green",),
                ("canonical regression fails",),
            ),
            Hypothesis(
                "H2",
                "Policy split introduces drift",
                ("a regression should fail",),
                ("all independent checks remain green",),
            ),
        )
        design = scientia.validate_case_design(
            observations=observations,
            hypotheses=hypotheses,
        )
        self.assertEqual("SCIENTIFIC_DESIGN_VALID", design["status"])
        self.assertEqual(2, design["hypotheses"])
        self.assertEqual("A1_INTERNAL", design["authority_ceiling"])
        self.assertFalse(design["external_effect"])

        with self.assertRaises(ValueError):
            scientia.validate_case_design(
                observations=observations,
                hypotheses=(
                    hypotheses[0],
                    Hypothesis(
                        "H3",
                        "Unfalsifiable candidate",
                        ("something happens",),
                        (),
                    ),
                ),
            )

    def test_real_caseforge_blind_and_provider_readback_gates_fail_closed(self):
        safe_hash = assert_blind_payload(
            {"case_id": "C4-BLIND", "facts": ["public synthetic fact"]}
        )
        self.assertEqual(64, len(safe_hash))

        with self.assertRaises(BlindIsolationError):
            assert_blind_payload(
                {"case_id": "C4-BLIND", "answer_key": "hidden"}
            )

        unreadback = ModelBinding(
            provider="fixture-provider",
            model="fixture-model",
            version="fixture-v1",
            configuration={"temperature": 0},
            execution_state="PROVIDER_VERIFIED",
            provider_readback_ref="",
        )
        with self.assertRaises(BlindIsolationError):
            unreadback.validate()

        readback = ModelBinding(
            provider="fixture-provider",
            model="fixture-model",
            version="fixture-v1",
            configuration={"temperature": 0},
            execution_state="PROVIDER_VERIFIED",
            provider_readback_ref="provider:readback:C4",
        )
        readback.validate()

    def test_real_caseforge_independent_replication_gate_preserves_independence(self):
        common = {
            "case_id": "C4-REP",
            "blind_input_sha256": "a" * 64,
            "tested_output_sha256": "b" * 64,
            "model": "fixture-model",
            "model_version_ref": "fixture-v1",
            "configuration_sha256": "c" * 64,
            "provider_readback_ref": "provider:verified",
            "provider_verified": True,
        }
        primary = ReplicationRun(
            run_id="R1",
            provider="provider-A",
            execution_route_id="route-A",
            **common,
        )
        independent = ReplicationRun(
            run_id="R2",
            provider="provider-B",
            execution_route_id="route-A",
            **common,
        )
        non_independent = ReplicationRun(
            run_id="R3",
            provider="provider-A",
            execution_route_id="route-A",
            **common,
        )

        gate = IndependentReplicationGate()
        positive = gate.evaluate(primary, independent)
        negative = gate.evaluate(primary, non_independent)

        self.assertTrue(positive.independent)
        self.assertIn("PROVIDER", positive.independence_dimensions)
        self.assertFalse(negative.independent)
        self.assertIn("MATERIAL_INDEPENDENCE_NOT_PROVEN", negative.reason_codes)
        self.assertFalse(positive.external_effect)
        self.assertFalse(negative.external_effect)


if __name__ == "__main__":
    unittest.main()
