from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evidenceops.caseforge.maturation_candidate_builder import (
    CandidateBuildRequest,
    IndependentAssuranceCourt,
    SuperiorLogicCandidateBuilder,
    standard_challenger_missions,
)


ROOT = Path(__file__).resolve().parents[1]
HEAD = "28eb5bbbcabc3c48185c1b0c35e876dc0091e038"
NOW = "2026-08-31T01:30:00+02:00"
CAMPAIGN = ROOT / "benchmarking/cfbe_omega/bubbles_30_pair_observed_certification_20260830.json"


def work_package() -> dict[str, object]:
    return {
        "work_package_id": "SL-MAT-WP-canary",
        "gap_id": "GAP-CLOSED-LOOP-CANDIDATE-QUALIFICATION",
        "objective": "Create one branch-bound challenger and qualify it without direct canonical mutation.",
        "experiment_class": "BRANCH_BOUND_CHALLENGER",
        "next_safe_action": "BIND_TO_ADMITTED_CANDIDATE_BUILDER_WITH_PR_ONLY_OUTPUT",
        "required_evidence": [
            "champion_anchor", "candidate_lineage", "deterministic_tests", "adversarial_tests",
            "independent_readback", "restore_test", "rollback_ref", "no_regression", "airlock_receipt",
        ],
        "prohibited_effects": [
            "direct_main_mutation", "provider_authority_expansion", "credential_scope_expansion",
            "unapproved_recurring_cost", "external_consequential_effect",
        ],
        "authority_ceiling": "A1_INTERNAL",
        "external_effect": False,
    }


def request(**changes: object) -> CandidateBuildRequest:
    values: dict[str, object] = {
        "mission_id": "MISSION-CANARY",
        "run_id": "run-1",
        "head_sha": HEAD,
        "base_ref": "main",
        "target_branch": "codex/cfbe-bubbles-cognitive-court-v2-current-main",
        "observed_at": NOW,
        "work_package": work_package(),
        "challenger_missions": standard_challenger_missions(),
        "observed_campaign_path": CAMPAIGN,
    }
    values.update(changes)
    return CandidateBuildRequest(**values)


class CandidateBuilderTests(unittest.TestCase):
    def test_builds_five_canary_executions_and_binds_thirty_observed_pairs(self) -> None:
        receipt = SuperiorLogicCandidateBuilder().build(request())
        self.assertEqual("CANDIDATE_EMPIRICAL_GATE_ASSURED_NO_PROMOTION", receipt.status)
        self.assertEqual(5, len(receipt.canary_receipts))
        self.assertTrue(all(item.canary_execution for item in receipt.canary_receipts))
        self.assertTrue(all(item.evidence_mode == "CANARY_EXECUTED_NO_EFFECT" for item in receipt.canary_receipts))
        self.assertTrue(all(not item.provider_execution for item in receipt.canary_receipts))
        self.assertEqual(30, receipt.assurance.observed_pair_count)
        self.assertTrue(receipt.assurance.empirical_gate_satisfied)

    def test_integrates_bubbles_court_without_effect_authority(self) -> None:
        receipt = SuperiorLogicCandidateBuilder().build(request())
        self.assertTrue(all(item.court_state == "SELECTED_NO_EFFECT" for item in receipt.canary_receipts))
        self.assertTrue(all(not item.effect_authorized for item in receipt.canary_receipts))
        self.assertTrue(all(len(item.court_receipt_sha256) == 64 for item in receipt.canary_receipts))

    def test_independent_assurance_passes_but_holds_stable_promotion(self) -> None:
        receipt = SuperiorLogicCandidateBuilder().build(request())
        self.assertTrue(receipt.assurance.assurance_passed)
        self.assertEqual("EMPIRICAL_GATE_SATISFIED_NO_PROMOTION", receipt.assurance.decision)
        self.assertFalse(receipt.assurance.stable_promotion_authorized)
        self.assertEqual(30, receipt.assurance.required_stable_pair_count)
        self.assertEqual(30, receipt.assurance.observed_pair_count)

    def test_candidate_is_pr_only_and_rollback_bound_to_exact_head(self) -> None:
        manifest = SuperiorLogicCandidateBuilder().build(request()).candidate_manifest
        self.assertEqual("main", manifest.base_ref)
        self.assertNotEqual("main", manifest.target_branch)
        self.assertFalse(manifest.direct_main_mutation)
        self.assertFalse(manifest.provider_authority_expansion)
        self.assertEqual(HEAD, manifest.rollback_ref)
        self.assertTrue(manifest.exact_rollback_tested)

    def test_all_expected_challengers_are_selected_and_quality_is_protected(self) -> None:
        canaries = SuperiorLogicCandidateBuilder().build(request()).canary_receipts
        self.assertTrue(all(item.expectation_met for item in canaries))
        self.assertTrue(all(item.quality_protected for item in canaries))

    def test_receipt_and_candidate_identity_are_deterministic(self) -> None:
        first = SuperiorLogicCandidateBuilder().build(request())
        second = SuperiorLogicCandidateBuilder().build(request())
        self.assertEqual(first.candidate_manifest.candidate_id, second.candidate_manifest.candidate_id)
        self.assertEqual(first.to_dict()["receipt_sha256"], second.to_dict()["receipt_sha256"])
        self.assertEqual(first.assurance.receipt_sha256, second.assurance.receipt_sha256)

    def test_main_target_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "NON_CANONICAL_BRANCH"):
            SuperiorLogicCandidateBuilder().build(request(target_branch="main"))

    def test_external_effect_work_package_fails_closed(self) -> None:
        package = work_package()
        package["external_effect"] = True
        with self.assertRaisesRegex(ValueError, "EXTERNAL_EFFECT"):
            SuperiorLogicCandidateBuilder().build(request(work_package=package))

    def test_incomplete_prohibitions_fail_closed(self) -> None:
        package = work_package()
        package["prohibited_effects"] = ["direct_main_mutation"]
        with self.assertRaisesRegex(ValueError, "PROHIBITIONS_INCOMPLETE"):
            SuperiorLogicCandidateBuilder().build(request(work_package=package))

    def test_wrong_pair_count_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "EXACTLY_FIVE"):
            SuperiorLogicCandidateBuilder().build(request(challenger_missions=standard_challenger_missions()[:4]))

    def test_assurance_detects_manifest_hash_tampering(self) -> None:
        receipt = SuperiorLogicCandidateBuilder().build(request())
        tampered = replace(receipt.candidate_manifest, target_branch="main")
        assurance = IndependentAssuranceCourt().assure(
            manifest=tampered,
            canary_receipts=receipt.canary_receipts,
            observed_campaign_raw=CAMPAIGN.read_bytes(),
        )
        self.assertFalse(assurance.assurance_passed)
        self.assertEqual("REJECT", assurance.decision)

    def test_assurance_detects_canary_tampering(self) -> None:
        receipt = SuperiorLogicCandidateBuilder().build(request())
        changed = replace(receipt.canary_receipts[0], provider_execution=True)
        assurance = IndependentAssuranceCourt().assure(
            manifest=receipt.candidate_manifest,
            canary_receipts=(changed,) + receipt.canary_receipts[1:],
            observed_campaign_raw=CAMPAIGN.read_bytes(),
        )
        self.assertFalse(assurance.assurance_passed)

    def test_assurance_rejects_any_observed_campaign_byte_drift(self) -> None:
        receipt = SuperiorLogicCandidateBuilder().build(request())
        assurance = IndependentAssuranceCourt().assure(
            manifest=receipt.candidate_manifest,
            canary_receipts=receipt.canary_receipts,
            observed_campaign_raw=CAMPAIGN.read_bytes() + b"\n",
        )
        self.assertFalse(assurance.assurance_passed)
        self.assertTrue(any("OBSERVED_CAMPAIGN_REJECTED" in item for item in assurance.independent_checks))

    def test_write_receipts_persists_five_hash_bound_artifacts(self) -> None:
        receipt = SuperiorLogicCandidateBuilder().build(request())
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = SuperiorLogicCandidateBuilder.write_receipts(receipt, Path(temp_dir))
            self.assertEqual(5, len(paths))
            self.assertTrue(all(path.is_file() for path in paths))
            assurance = json.loads((Path(temp_dir) / "independent_assurance.json").read_text())
            canaries = json.loads((Path(temp_dir) / "canary_challenger_receipts.json").read_text())
            self.assertTrue(assurance["assurance_passed"])
            self.assertEqual(30, assurance["observed_pair_count"])
            self.assertEqual(5, len(canaries))

    def test_cli_executes_from_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            package_path = temp / "work-package.json"
            package_path.write_text(json.dumps(work_package()), encoding="utf-8")
            command = [
                sys.executable, "-m", "evidenceops.caseforge.maturation_candidate_builder_cli",
                "--input-work-package", str(package_path), "--output-dir", str(temp / "receipts"),
                "--mission-id", "MISSION-CLI", "--run-id", "run-cli", "--head-sha", HEAD,
                "--base-ref", "main", "--target-branch", "codex/cfbe-bubbles-cognitive-court-v2-current-main",
                "--observed-at", NOW,
                "--observed-campaign", str(CAMPAIGN),
            ]
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(0, completed.returncode, msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
            payload = json.loads((temp / "receipts" / "candidate_builder_receipt.json").read_text())
            self.assertEqual("CANDIDATE_EMPIRICAL_GATE_ASSURED_NO_PROMOTION", payload["status"])

    def test_workflow_is_pr_only_read_permission_canary(self) -> None:
        workflow = (ROOT / ".github/workflows/superior-logic-candidate-builder-canary.yml").read_text()
        self.assertIn("pull_request:", workflow)
        self.assertIn("branches: [main]", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("test_cfbe_observed_campaign_admission.py", workflow)
        self.assertIn("bubbles_30_pair_observed_certification_20260830.json", workflow)


if __name__ == "__main__":
    unittest.main()
