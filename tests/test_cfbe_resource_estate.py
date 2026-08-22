import tempfile
import unittest
from pathlib import Path

from benchmarking.cfbe_omega.compatibility import (
    assess_drive_receipt_contract,
    normalize_drive_receipt_for_v3,
)
from benchmarking.cfbe_omega.estate_audit import (
    alpha_omega_lineage,
    census_repository,
    cluster_workflows,
    workflow_family_counts,
)
from benchmarking.cfbe_omega.resource_gate import (
    CapabilityCandidate,
    CapabilityRequirement,
    SufficiencyState,
    evaluate_requirement,
    evaluate_upgrade,
    upgrade_ready,
)


class ResourceGateTests(unittest.TestCase):
    def test_reuses_existing_capability_before_build(self):
        requirement = CapabilityRequirement("R1", "semantic_readback", min_fit=0.8)
        candidate = CapabilityCandidate(
            "C1",
            "semantic_readback",
            fit=0.9,
            evidence_factor=0.9,
            independent_verifier_available=True,
        )
        decision = evaluate_requirement(requirement, [candidate])
        self.assertEqual(decision.state, SufficiencyState.REUSE_EXISTING)

    def test_provider_gate_is_not_misreported_as_build_gap(self):
        requirement = CapabilityRequirement(
            "R2",
            "gemini_inference",
            min_fit=0.8,
            provider_live_required=True,
        )
        candidate = CapabilityCandidate(
            "TWIN",
            "gemini_inference",
            fit=0.95,
            evidence_factor=0.7,
            provider_live=False,
            independent_verifier_available=True,
            source_kind="SIMULATION",
        )
        decision = evaluate_requirement(requirement, [candidate])
        self.assertEqual(decision.state, SufficiencyState.PROVIDER_GATE)

    def test_unknown_cost_fails_closed(self):
        requirement = CapabilityRequirement("R3", "cloud_runtime", min_fit=0.8)
        candidate = CapabilityCandidate(
            "CLOUD",
            "cloud_runtime",
            fit=0.95,
            evidence_factor=0.8,
            independent_verifier_available=True,
            incremental_cost=None,
        )
        decision = evaluate_requirement(requirement, [candidate])
        self.assertEqual(decision.state, SufficiencyState.COST_GATE)

    def test_upgrade_ready_requires_all_requirements(self):
        requirements = [
            CapabilityRequirement("A", "read", min_fit=0.8),
            CapabilityRequirement("B", "write", min_fit=0.8),
        ]
        candidates = [
            CapabilityCandidate("R", "read", 1.0, 1.0, independent_verifier_available=True),
            CapabilityCandidate("W", "write", 1.0, 1.0, independent_verifier_available=True),
        ]
        self.assertTrue(upgrade_ready(evaluate_upgrade(requirements, candidates)))


class CompatibilityTests(unittest.TestCase):
    def _receipt(self):
        return {
            "discover": {"available": True},
            "authority": {"authorised": True},
            "snapshot": {"state": "INVENTORY_CAPTURED"},
            "deploy": {"state": "DOCUMENT_CREATED"},
            "execute": {"state": "CONTENT_WRITTEN"},
            "readback": {"pass": True},
            "health": {"pass": True},
            "persistence": {"pass": True},
            "rollback": {"target_absent": True},
            "proof": {"receipt_id": "SYNTHETIC-RECEIPT-001"},
        }

    def test_prior_receipt_is_reusable_for_evidence_not_write_authority(self):
        result = assess_drive_receipt_contract(self._receipt())
        self.assertTrue(result.compatible)
        self.assertIn("readback_validation", result.reusable_for)
        self.assertIn("provider_write", result.not_sufficient_for)
        self.assertIn("authority_grant", result.not_sufficient_for)
        self.assertIn("maturity_inheritance", result.not_sufficient_for)

    def test_normalized_observation_keeps_non_inheritance_boundary(self):
        observation = normalize_drive_receipt_for_v3(
            self._receipt(),
            entity_id="synthetic-drive-object",
            observed_at="2026-08-22T14:00:00+00:00",
        )
        self.assertEqual(observation["evidence_ref"], "SYNTHETIC-RECEIPT-001")
        self.assertFalse(observation["truth_boundary"]["provider_write_performed_here"])
        self.assertFalse(observation["truth_boundary"]["authority_inherited"])
        self.assertFalse(observation["truth_boundary"]["maturity_inherited"])

    def test_missing_receipt_section_fails_closed(self):
        receipt = self._receipt()
        del receipt["rollback"]
        result = assess_drive_receipt_contract(receipt)
        self.assertFalse(result.compatible)
        self.assertIn("missing:rollback", result.gaps)


class EstateAuditTests(unittest.TestCase):
    def test_lineage_uses_semantic_versions_not_directory_names(self):
        lineage = alpha_omega_lineage()
        self.assertEqual([node.generation for node in lineage], ["2.2.1", "2.4.0", "3.0"])
        self.assertEqual(lineage[0].name, "alpha_omega_v21")
        self.assertEqual(lineage[1].name, "alpha_omega_v2")
        self.assertTrue(all("RETAIN" in node.status for node in lineage[:2]))

    def test_release_siblings_are_review_candidates_not_auto_duplicates(self):
        names = [
            "alpha-omega-commercial-authority-action-binding.yml",
            "alpha-omega-commercial-authority-action-binding-release.yml",
            "other.yml",
        ]
        clusters = cluster_workflows(names)
        binding = [cluster for cluster in clusters if "action-binding" in cluster.cluster_key][0]
        self.assertTrue(binding.shared_primitive_candidate)
        self.assertFalse(binding.consolidation_candidate)
        self.assertEqual(len(binding.members), 2)

    def test_family_counts(self):
        counts = workflow_family_counts(
            [
                "alpha-omega-commercial-authority-a.yml",
                "alpha-omega-commercial-authority-b.yml",
                "alpha-omega-ci.yml",
                "misc.yml",
            ]
        )
        self.assertEqual(counts["alpha_omega_commercial_authority"], 2)
        self.assertEqual(counts["alpha_omega_other"], 1)
        self.assertEqual(counts["other_workflows"], 1)

    def test_repo_census(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pkg").mkdir()
            (root / "pkg" / "a.py").write_text("x=1")
            (root / "tests").mkdir()
            (root / "tests" / "test_a.py").write_text("pass")
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "ci.yml").write_text("name: ci")
            census = census_repository(root)
            self.assertEqual(census.files, 3)
            self.assertEqual(census.python_files, 2)
            self.assertEqual(census.test_files, 1)
            self.assertEqual(census.workflow_files, 1)
            self.assertIn("pkg", census.package_roots)


if __name__ == "__main__":
    unittest.main()
