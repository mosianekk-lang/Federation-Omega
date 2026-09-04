from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from federation.modisa_v3_federation import (
    Authority,
    Disposition,
    ManifestError,
    ModisaFederationCompiler,
    ReceiverProfile,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "governance" / "modisa_v3_federation_propagation_v1.json"


@pytest.fixture()
def raw_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def compiler() -> ModisaFederationCompiler:
    return ModisaFederationCompiler.from_path(MANIFEST_PATH)


def test_manifest_has_exact_37_capabilities(compiler: ModisaFederationCompiler) -> None:
    assert compiler.manifest["capability_count"] == 37
    assert len(compiler.manifest["capabilities"]) == 37


def test_source_tree_is_content_addressed(compiler: ModisaFederationCompiler) -> None:
    receipt = compiler.verify_source_tree(ROOT)
    assert receipt["state"] == "SOURCE_TREE_VERIFIED"
    assert receipt["file_count"] == 66
    assert receipt["provider_effect"] is False


def test_every_source_module_exists(compiler: ModisaFederationCompiler) -> None:
    source = ROOT / compiler.manifest["source"]["root"]
    for capability in compiler.manifest["capabilities"]:
        for relative in capability["source_modules"]:
            assert (source / relative).is_file(), (capability["id"], relative)


def test_manifest_rejects_non_additive_mode(raw_manifest: dict) -> None:
    candidate = copy.deepcopy(raw_manifest)
    candidate["propagation_mode"] = "REPLACE"
    with pytest.raises(ManifestError, match="additive"):
        ModisaFederationCompiler(candidate)


@pytest.mark.parametrize(
    "field",
    ["credentials_inherited", "effect_authority_inherited", "provider_runtime_claimed", "hidden_chat_access_claimed"],
)
def test_manifest_rejects_truth_boundary_weakening(raw_manifest: dict, field: str) -> None:
    candidate = copy.deepcopy(raw_manifest)
    candidate["truth_boundary"][field] = True
    with pytest.raises(ManifestError, match=field):
        ModisaFederationCompiler(candidate)


def test_manifest_rejects_duplicate_capability(raw_manifest: dict) -> None:
    candidate = copy.deepcopy(raw_manifest)
    candidate["capabilities"].append(copy.deepcopy(candidate["capabilities"][0]))
    candidate["capability_count"] += 1
    with pytest.raises(ManifestError, match="duplicate"):
        ModisaFederationCompiler(candidate)


def test_manifest_rejects_unknown_dependency(raw_manifest: dict) -> None:
    candidate = copy.deepcopy(raw_manifest)
    candidate["capabilities"][0]["dependencies"] = ["missing"]
    with pytest.raises(ManifestError, match="unknown dependencies"):
        ModisaFederationCompiler(candidate)


def test_manifest_rejects_dependency_cycle(raw_manifest: dict) -> None:
    candidate = copy.deepcopy(raw_manifest)
    candidate["capabilities"][0]["dependencies"] = [candidate["capabilities"][1]["id"]]
    with pytest.raises(ManifestError, match="cycle"):
        ModisaFederationCompiler(candidate)


def test_universal_capability_adopts_on_python_receiver(compiler: ModisaFederationCompiler) -> None:
    plan = compiler.compile(ReceiverProfile("R", frozenset({"CORE"}), frozenset({"PYTHON", "SQLITE"})))
    decision = next(item for item in plan["decisions"] if item["capability_id"] == "immutable_mission_ir")
    assert decision["disposition"] == Disposition.ADOPT


def test_missing_runtime_requires_adapter(compiler: ModisaFederationCompiler) -> None:
    plan = compiler.compile(ReceiverProfile("R", frozenset({"CORE"}), frozenset()))
    decision = next(item for item in plan["decisions"] if item["capability_id"] == "immutable_mission_ir")
    assert decision["disposition"] == Disposition.ADAPT


def test_domain_mismatch_is_not_applicable(compiler: ModisaFederationCompiler) -> None:
    plan = compiler.compile(ReceiverProfile("R", frozenset({"CORE"}), frozenset({"PYTHON", "SQLITE"})))
    decision = next(item for item in plan["decisions"] if item["capability_id"] == "encrypted_evidence_vault")
    assert decision["disposition"] == Disposition.NOT_APPLICABLE


def test_existing_equivalent_is_preserved(compiler: ModisaFederationCompiler) -> None:
    profile = ReceiverProfile(
        "R",
        frozenset({"CORE"}),
        frozenset({"PYTHON", "SQLITE"}),
        existing_capabilities=frozenset({"durable_hash_journal"}),
    )
    plan = compiler.compile(profile)
    decision = next(item for item in plan["decisions"] if item["capability_id"] == "durable_hash_journal")
    assert decision["disposition"] == Disposition.ALREADY_PRESENT


def test_lower_authority_receiver_holds_a1_capability(compiler: ModisaFederationCompiler) -> None:
    profile = ReceiverProfile("R", frozenset({"CORE"}), frozenset({"PYTHON", "SQLITE"}), Authority.A0)
    plan = compiler.compile(profile)
    decision = next(item for item in plan["decisions"] if item["capability_id"] == "atomic_resource_budgets")
    assert decision["disposition"] == Disposition.HELD


def test_plan_has_exactly_one_decision_per_capability(compiler: ModisaFederationCompiler) -> None:
    plan = compiler.compile(compiler.receiver_profiles()[0])
    ids = [item["capability_id"] for item in plan["decisions"]]
    assert len(ids) == len(set(ids)) == 37
    assert plan["complete_coverage"] is True


def test_plan_never_inherits_credentials_or_effect_authority(compiler: ModisaFederationCompiler) -> None:
    plan = compiler.compile(compiler.receiver_profiles()[0])
    assert plan["credentials_inherited"] is False
    assert plan["effect_authority_inherited"] is False
    assert all(item["credentials_inherited"] is False for item in plan["decisions"])
    assert all(item["effect_authority_inherited"] is False for item in plan["decisions"])


def test_plan_hash_detects_tampering(compiler: ModisaFederationCompiler) -> None:
    plan = compiler.compile(compiler.receiver_profiles()[0])
    plan["decisions"][0]["disposition"] = Disposition.REJECTED
    with pytest.raises(ManifestError, match="hash mismatch"):
        compiler.verify_plan(plan)


def test_fleet_covers_all_declared_receivers(compiler: ModisaFederationCompiler) -> None:
    profiles = compiler.receiver_profiles()
    fleet = compiler.compile_fleet(profiles)
    assert fleet["receiver_count"] == 15
    assert fleet["capability_receiver_pairs"] == 555
    assert {plan["receiver_id"] for plan in fleet["plans"]} == set(compiler.manifest["receiver_targets"])


def test_fleet_is_source_registered_not_runtime_promoted(compiler: ModisaFederationCompiler) -> None:
    fleet = compiler.compile_fleet(compiler.receiver_profiles())
    assert fleet["propagation_state"] == "SOURCE_REGISTERED_RECEIVER_ACTIVATION_PROOF_REQUIRED"
    assert fleet["provider_effect"] is False


def test_duplicate_receiver_is_rejected(compiler: ModisaFederationCompiler) -> None:
    receiver = compiler.receiver_profiles()[0]
    with pytest.raises(ManifestError, match="duplicate receiver"):
        compiler.compile_fleet([receiver, receiver])


def test_evidenceops_preserves_existing_absorbed_capabilities(compiler: ModisaFederationCompiler) -> None:
    receiver = next(item for item in compiler.receiver_profiles() if item.receiver_id == "EVIDENCEOPS")
    plan = compiler.compile(receiver)
    dispositions = {item["capability_id"]: item["disposition"] for item in plan["decisions"]}
    assert dispositions["deterministic_crash_replay"] == Disposition.ALREADY_PRESENT
    assert dispositions["runtime_observability_benchmarks"] == Disposition.ALREADY_PRESENT


def test_all_receiver_plans_verify(compiler: ModisaFederationCompiler) -> None:
    for receiver in compiler.receiver_profiles():
        compiler.verify_plan(compiler.compile(receiver))
