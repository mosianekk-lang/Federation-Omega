from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from benchmarking.cfbe_omega.closure_matrix_v1 import load_matrix, plan_wave
from benchmarking.cfbe_omega.convergence_closure_runtime_v1 import (
    FailureGenomeObservation,
    assemble_foundry_readiness,
    compile_preregistered_observation,
    evaluate_universal_closure_court,
    load_preregistration,
    plan_convergence_wave,
    project_capability_registry,
)
from federation.living_state.store import LivingStateStore
from federation.living_state.world_model import (
    LivingWorldModel,
    NodeKind,
    ProofMaturity,
    Provenance,
    WorldNode,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-30T19:30:00+02:00"
STALE = "2026-08-29T19:30:00+02:00"
MAIN = "642958d6a60e1f2509f802e668a39d09c69684aa"
MISSION = "MISSION-CFBE-OMEGA-CONVERGENCE-COMPLETE"


class ConvergenceClosureRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.matrix = load_matrix()

    def _model(self, *, source_main=MAIN, observed_at=NOW, ttl=3600):
        model = LivingWorldModel()
        for row in self.matrix["rows"]:
            capability_id = row["id"]
            model.observe_node(
                WorldNode(
                    node_id=f"capability:{capability_id}",
                    kind=NodeKind.CAPABILITY,
                    label=row["capability"],
                    state="ACTIVE",
                    payload={
                        "source_main_sha": source_main,
                        "latency_ms": 1.0,
                        "cost_units": 0.0,
                        "failure_domains": [],
                        "proof_refs": [f"source:{capability_id}", f"test:{capability_id}"],
                    },
                    provenance=Provenance(
                        source_ref="cfbe-closure-test",
                        proof_ref=f"proof:{capability_id}",
                        observed_at=observed_at,
                        proof_maturity=ProofMaturity.DETERMINISTIC_TESTED,
                        ttl_seconds=ttl,
                        confidence=0.9,
                    ),
                )
            )
        return model

    def _registry(self, model=None):
        model = model or self._model()
        with tempfile.TemporaryDirectory() as td:
            with LivingStateStore(Path(td) / "living.sqlite3") as store:
                store_receipt = store.seal(model, now=NOW, fabric_id="CFBE-CLOSURE")
        return project_capability_registry(
            self.matrix,
            model,
            now=NOW,
            current_main_sha=MAIN,
            store_receipt=store_receipt,
        )

    def _observation(self, **overrides):
        preregistration = load_preregistration()
        observation = {
            "schema": "CFBE-OMEGA-CONVERGENCE-CLOSURE-OBSERVATION-V1",
            "window_id": preregistration["window_id"],
            "mission_id": preregistration["mission_id"],
            "source_main_sha": preregistration["source_main_sha"],
            "branch_head_sha": "b" * 40,
            "observed_at_sast": NOW,
            "observation_command": preregistration["observation_command"],
            "exit_code": 0,
            "command_output_sha256": "c" * 64,
            "evidence_class": "OBSERVED_FEDERATION_EXPERIMENT",
            "synthetic": False,
            "evidence_refs": ("local:focused-closure-suite", "git:preregistered-before-runtime"),
            "telemetry": {
                "canary.failure_modes_falsified": 12.0,
                "canary.closure_cells_advanced": 4.0,
                "canary.proof_layers_verified": 3.0,
                "canary.rollback_routes_verified": 1.0,
                "canary.incremental_cost_usd": 0.0,
                "canary.elapsed_seconds": 1.0,
                "canary.manual_owner_actions": 0.0,
                "canary.external_effects_or_harm_signals": 0.0,
            },
        }
        observation.update(overrides)
        return preregistration, observation

    def _measurement(self):
        preregistration, observation = self._observation()
        return compile_preregistered_observation(preregistration, observation)

    def _failures(self, *, second_mission=MISSION, second_observed=True):
        return (
            FailureGenomeObservation(
                "gap:phoenix-stale-semantics",
                MISSION,
                "admission regression semantics drift from current source",
                MAIN,
                ("github:PR852", "github:run:33323797229"),
            ),
            FailureGenomeObservation(
                "gap:sovara-stale-semantics",
                second_mission,
                "admission regression semantics drift from current source",
                MAIN,
                ("github:PR853", "github:run:33324196123"),
                observed=second_observed,
            ),
        )

    def _foundry(self, **overrides):
        values = {
            "registry": self._registry(),
            "measurement": self._measurement(),
            "failure_observations": self._failures(),
            "mission_id": MISSION,
            "regression_baseline_id": f"git:main:{MAIN}",
            "regression_proof_refs": ("local:2615-tests", "github:airlock:33324629811"),
        }
        values.update(overrides)
        return assemble_foundry_readiness(**values)

    def test_stale_main_projection_fails_closed(self):
        registry = self._registry(self._model(source_main="a" * 40))
        self.assertEqual("REGISTRY_HELD", registry.state)
        self.assertTrue(all("STALE_MAIN_PROJECTION" in item.blockers for item in registry.projections))

    def test_stale_living_state_evidence_fails_closed(self):
        registry = self._registry(self._model(observed_at=STALE, ttl=60))
        self.assertEqual("REGISTRY_HELD", registry.state)
        self.assertTrue(all("STALE_LIVING_STATE" in item.blockers for item in registry.projections))

    def test_split_brain_living_state_evidence_fails_closed(self):
        model = self._model()
        prior = model.current_nodes()["capability:C03"]
        model.observe_node(
            WorldNode(
                prior.node_id,
                prior.kind,
                prior.label,
                "FAILED",
                prior.payload,
                Provenance(
                    "independent-cfbe-readback",
                    "proof:split-brain",
                    NOW,
                    ProofMaturity.DETERMINISTIC_TESTED,
                    3600,
                    0.95,
                ),
            )
        )
        registry = self._registry(model)
        c03 = next(item for item in registry.projections if item.capability_id == "C03")
        self.assertFalse(c03.schedulable)
        self.assertIn("SPLIT_BRAIN_LIVING_STATE", c03.blockers)

    def test_registry_and_durable_store_receipts_are_deterministic(self):
        first = self._registry(self._model())
        second = self._registry(self._model())
        self.assertEqual("REGISTRY_READY", first.state)
        self.assertTrue(first.store_readback_verified)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        self.assertEqual(first.graph_sha256, second.graph_sha256)

    def test_dependency_must_be_terminal_before_selection(self):
        receipt = plan_wave(self.matrix, completed_ids=("C02",))
        selected = {item.capability_id for item in receipt.selected}
        held = {item.capability_id: item for item in receipt.held}
        self.assertIn("C03", selected)
        self.assertIn("DEPENDENCY_NOT_TERMINAL:C03", held["C05"].blockers)

    def test_c03_and_c05_cannot_enter_same_wave(self):
        receipt = plan_wave(
            self.matrix,
            completed_ids=("C02",),
            roles={"C03": "PRIMARY", "C05": "CHALLENGER"},
        )
        selected = {item.capability_id for item in receipt.selected}
        self.assertIn("C03", selected)
        self.assertNotIn("C05", selected)

    def test_each_rail_allows_at_most_one_primary_and_one_challenger(self):
        receipt = plan_wave(
            self.matrix,
            completed_ids=("C02", "C03"),
            roles={"C01": "PRIMARY", "C05": "CHALLENGER", "C08": "CHALLENGER"},
        )
        self.assertLessEqual(receipt.selected_roles_per_rail["A"]["PRIMARY"], 1)
        self.assertLessEqual(receipt.selected_roles_per_rail["A"]["CHALLENGER"], 1)
        challenger_holds = [
            item for item in receipt.held if "RAIL_CHALLENGER_LIMIT" in item.blockers
        ]
        self.assertTrue(challenger_holds)

    def test_blocked_rail_does_not_contaminate_another_rail(self):
        receipt = plan_wave(self.matrix, completed_ids=("C03",))
        selected = {item.capability_id for item in receipt.selected}
        held = {item.capability_id: item for item in receipt.held}
        self.assertIn("DATA_NEEDED", held["C07"].blockers)
        self.assertIn("C10", selected)

    def test_critical_regression_preempts_new_architecture_on_its_rail(self):
        receipt = plan_wave(
            self.matrix,
            completed_ids=("C02", "C03"),
            critical_regression_ids=("C05",),
        )
        selected = {item.capability_id for item in receipt.selected}
        held = {item.capability_id: item for item in receipt.held}
        self.assertIn("C05", selected)
        self.assertIn("CRITICAL_REGRESSION_PREEMPTION", held["C01"].blockers)

    def test_data_needed_cell_requires_observed_live_override(self):
        registry = self._registry()
        without = plan_convergence_wave(
            self.matrix,
            registry,
            completed_ids=("C02", "C03"),
            roles={"C07": "CHALLENGER"},
        )
        with_observation = plan_convergence_wave(
            self.matrix,
            registry,
            completed_ids=("C02", "C03"),
            roles={"C07": "CHALLENGER"},
            measurement=self._measurement(),
        )
        self.assertIn("DATA_NEEDED", next(x for x in without.held if x.capability_id == "C07").blockers)
        self.assertIn("C07", {item.capability_id for item in with_observation.selected})

    def test_cross_mission_foundry_stitching_is_held(self):
        foundry = self._foundry(
            failure_observations=self._failures(second_mission="OTHER-MISSION")
        )
        self.assertEqual("HELD_CROSS_MISSION_EVIDENCE", foundry.state)
        self.assertIn("CROSS_MISSION_OR_MAIN_GAP_STITCHING_PROHIBITED", foundry.blockers)

    def test_foundry_rejects_synthetic_single_unproven_or_baseline_free_packets(self):
        preregistration, observation = self._observation(synthetic=True)
        with self.assertRaisesRegex(ValueError, "OBSERVED_EXPERIMENT_REQUIRED"):
            compile_preregistered_observation(preregistration, observation)

        single = self._foundry(failure_observations=self._failures()[:1])
        self.assertEqual("INSTRUMENTED_REPEATED_GAP_EVIDENCE_REQUIRED", single.state)

        unproven = self._foundry(
            failure_observations=self._failures(second_observed=False)
        )
        self.assertEqual("INSTRUMENTED_REPEATED_GAP_EVIDENCE_REQUIRED", unproven.state)

        baseline_free = self._foundry(
            regression_baseline_id="",
            regression_proof_refs=(),
        )
        self.assertEqual("HELD_REGRESSION_BASELINE_REQUIRED", baseline_free.state)

    def test_complete_observed_packet_passes_c01_without_promotion_claim(self):
        registry = self._registry()
        measurement = self._measurement()
        foundry = assemble_foundry_readiness(
            registry,
            measurement,
            self._failures(),
            mission_id=MISSION,
            regression_baseline_id=f"git:main:{MAIN}",
            regression_proof_refs=("local:2615-tests", "github:airlock:33324629811"),
        )
        self.assertEqual("DATA_READY", foundry.state)
        court = evaluate_universal_closure_court(
            registry,
            measurement,
            foundry,
            regression_baseline_id=f"git:main:{MAIN}",
            regression_proof_refs=("local:2615-tests", "github:airlock:33324629811"),
        )
        self.assertEqual("PASS_INTERNAL_DATA_READY", court.status)
        self.assertTrue(court.hard_gates_pass)
        self.assertFalse(court.promotion_allowed)

    def test_repository_observation_compiles_to_eight_dimension_packet(self):
        observation_path = (
            ROOT
            / "benchmarking"
            / "cfbe_omega"
            / "convergence_closure_observation_20260830_v1.json"
        )
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
        report = compile_preregistered_observation(load_preregistration(), observation)
        self.assertEqual("MEASUREMENT_PACKET_READY", report.state)
        self.assertEqual("OBSERVED_OPTION_READY", report.normalized_state)
        self.assertEqual(8, len(report.rows))
        self.assertTrue(all(row["Source_Work_ID"] == MISSION for row in report.rows))

    def test_repository_closure_receipt_is_hash_bound_and_non_promoting(self):
        receipt_path = (
            ROOT
            / "benchmarking"
            / "cfbe_omega"
            / "convergence_closure_receipt_20260830_v1.json"
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        claimed = receipt.pop("receipt_sha256")
        computed = sha256(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(claimed, computed)
        self.assertEqual("REGISTRY_READY", receipt["registry"]["state"])
        self.assertEqual("MEASUREMENT_PACKET_READY", receipt["economic_window"]["state"])
        self.assertEqual("DATA_READY", receipt["foundry"]["state"])
        self.assertEqual("PASS_INTERNAL_DATA_READY", receipt["court"]["status"])
        self.assertFalse(receipt["court"]["promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
