from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from federation.modisa_v3_federation import (
    Authority,
    Disposition,
    ManifestError,
    ModisaFederationCompiler,
    ReceiverProfile,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "governance" / "modisa_v3_federation_propagation_v1.json"


class ModisaV3FederationPropagationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_manifest: dict[str, Any] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.compiler = ModisaFederationCompiler.from_path(MANIFEST_PATH)

    def test_manifest_has_exact_37_capabilities(self) -> None:
        self.assertEqual(self.compiler.manifest["capability_count"], 37)
        self.assertEqual(len(self.compiler.manifest["capabilities"]), 37)

    def test_source_tree_is_content_addressed(self) -> None:
        receipt = self.compiler.verify_source_tree(ROOT)
        self.assertEqual(receipt["state"], "SOURCE_TREE_VERIFIED")
        self.assertEqual(receipt["file_count"], 66)
        self.assertIs(receipt["provider_effect"], False)

    def test_every_source_module_exists(self) -> None:
        source = ROOT / self.compiler.manifest["source"]["root"]
        for capability in self.compiler.manifest["capabilities"]:
            for relative in capability["source_modules"]:
                with self.subTest(capability=capability["id"], module=relative):
                    self.assertTrue((source / relative).is_file())

    def test_manifest_rejects_non_additive_mode(self) -> None:
        candidate = copy.deepcopy(self.raw_manifest)
        candidate["propagation_mode"] = "REPLACE"
        with self.assertRaisesRegex(ManifestError, "additive"):
            ModisaFederationCompiler(candidate)

    def test_manifest_rejects_truth_boundary_weakening(self) -> None:
        fields = (
            "credentials_inherited",
            "effect_authority_inherited",
            "provider_runtime_claimed",
            "hidden_chat_access_claimed",
        )
        for field in fields:
            with self.subTest(field=field):
                candidate = copy.deepcopy(self.raw_manifest)
                candidate["truth_boundary"][field] = True
                with self.assertRaisesRegex(ManifestError, field):
                    ModisaFederationCompiler(candidate)

    def test_manifest_rejects_duplicate_capability(self) -> None:
        candidate = copy.deepcopy(self.raw_manifest)
        candidate["capabilities"].append(copy.deepcopy(candidate["capabilities"][0]))
        candidate["capability_count"] += 1
        with self.assertRaisesRegex(ManifestError, "duplicate"):
            ModisaFederationCompiler(candidate)

    def test_manifest_rejects_unknown_dependency(self) -> None:
        candidate = copy.deepcopy(self.raw_manifest)
        candidate["capabilities"][0]["dependencies"] = ["missing"]
        with self.assertRaisesRegex(ManifestError, "unknown dependencies"):
            ModisaFederationCompiler(candidate)

    def test_manifest_rejects_dependency_cycle(self) -> None:
        candidate = copy.deepcopy(self.raw_manifest)
        candidate["capabilities"][0]["dependencies"] = [candidate["capabilities"][1]["id"]]
        with self.assertRaisesRegex(ManifestError, "cycle"):
            ModisaFederationCompiler(candidate)

    def test_universal_capability_adopts_on_python_receiver(self) -> None:
        plan = self.compiler.compile(ReceiverProfile("R", frozenset({"CORE"}), frozenset({"PYTHON", "SQLITE"})))
        decision = next(item for item in plan["decisions"] if item["capability_id"] == "immutable_mission_ir")
        self.assertEqual(decision["disposition"], Disposition.ADOPT)

    def test_missing_runtime_requires_adapter(self) -> None:
        plan = self.compiler.compile(ReceiverProfile("R", frozenset({"CORE"}), frozenset()))
        decision = next(item for item in plan["decisions"] if item["capability_id"] == "immutable_mission_ir")
        self.assertEqual(decision["disposition"], Disposition.ADAPT)

    def test_domain_mismatch_is_not_applicable(self) -> None:
        plan = self.compiler.compile(ReceiverProfile("R", frozenset({"CORE"}), frozenset({"PYTHON", "SQLITE"})))
        decision = next(item for item in plan["decisions"] if item["capability_id"] == "encrypted_evidence_vault")
        self.assertEqual(decision["disposition"], Disposition.NOT_APPLICABLE)

    def test_existing_equivalent_is_preserved(self) -> None:
        profile = ReceiverProfile(
            "R",
            frozenset({"CORE"}),
            frozenset({"PYTHON", "SQLITE"}),
            existing_capabilities=frozenset({"durable_hash_journal"}),
        )
        plan = self.compiler.compile(profile)
        decision = next(item for item in plan["decisions"] if item["capability_id"] == "durable_hash_journal")
        self.assertEqual(decision["disposition"], Disposition.ALREADY_PRESENT)

    def test_lower_authority_receiver_holds_a1_capability(self) -> None:
        profile = ReceiverProfile("R", frozenset({"CORE"}), frozenset({"PYTHON", "SQLITE"}), Authority.A0)
        plan = self.compiler.compile(profile)
        decision = next(item for item in plan["decisions"] if item["capability_id"] == "atomic_resource_budgets")
        self.assertEqual(decision["disposition"], Disposition.HELD)

    def test_plan_has_exactly_one_decision_per_capability(self) -> None:
        plan = self.compiler.compile(self.compiler.receiver_profiles()[0])
        ids = [item["capability_id"] for item in plan["decisions"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 37)
        self.assertIs(plan["complete_coverage"], True)

    def test_plan_never_inherits_credentials_or_effect_authority(self) -> None:
        plan = self.compiler.compile(self.compiler.receiver_profiles()[0])
        self.assertIs(plan["credentials_inherited"], False)
        self.assertIs(plan["effect_authority_inherited"], False)
        self.assertTrue(all(item["credentials_inherited"] is False for item in plan["decisions"]))
        self.assertTrue(all(item["effect_authority_inherited"] is False for item in plan["decisions"]))

    def test_plan_hash_detects_tampering(self) -> None:
        plan = self.compiler.compile(self.compiler.receiver_profiles()[0])
        plan["decisions"][0]["disposition"] = Disposition.REJECTED
        with self.assertRaisesRegex(ManifestError, "hash mismatch"):
            self.compiler.verify_plan(plan)

    def test_fleet_covers_all_declared_receivers(self) -> None:
        profiles = self.compiler.receiver_profiles()
        fleet = self.compiler.compile_fleet(profiles)
        self.assertEqual(fleet["receiver_count"], 15)
        self.assertEqual(fleet["capability_receiver_pairs"], 555)
        self.assertEqual(
            {plan["receiver_id"] for plan in fleet["plans"]},
            set(self.compiler.manifest["receiver_targets"]),
        )

    def test_fleet_is_source_registered_not_runtime_promoted(self) -> None:
        fleet = self.compiler.compile_fleet(self.compiler.receiver_profiles())
        self.assertEqual(fleet["propagation_state"], "SOURCE_REGISTERED_RECEIVER_ACTIVATION_PROOF_REQUIRED")
        self.assertIs(fleet["provider_effect"], False)

    def test_duplicate_receiver_is_rejected(self) -> None:
        receiver = self.compiler.receiver_profiles()[0]
        with self.assertRaisesRegex(ManifestError, "duplicate receiver"):
            self.compiler.compile_fleet([receiver, receiver])

    def test_evidenceops_preserves_existing_absorbed_capabilities(self) -> None:
        receiver = next(item for item in self.compiler.receiver_profiles() if item.receiver_id == "EVIDENCEOPS")
        plan = self.compiler.compile(receiver)
        dispositions = {item["capability_id"]: item["disposition"] for item in plan["decisions"]}
        self.assertEqual(dispositions["deterministic_crash_replay"], Disposition.ALREADY_PRESENT)
        self.assertEqual(dispositions["runtime_observability_benchmarks"], Disposition.ALREADY_PRESENT)

    def test_all_receiver_plans_verify(self) -> None:
        for receiver in self.compiler.receiver_profiles():
            with self.subTest(receiver=receiver.receiver_id):
                self.compiler.verify_plan(self.compiler.compile(receiver))


if __name__ == "__main__":
    unittest.main()
