from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.sol62_client_runtime.alpha_omega_formation_binding import (
    AUTHORITY_CEILING,
    Sol62AlphaOmegaFormationBinding,
    receipt_to_dict,
)
from sol_61_runtime.sol_62_complete_client_runtime import RouteCandidate


ROOT = Path(__file__).resolve().parents[1]


class Sol62AlphaOmegaFormationBindingTests(unittest.TestCase):
    def binding(self, workspace: str):
        return Sol62AlphaOmegaFormationBinding(
            repo_root=ROOT,
            workspace=workspace,
            learning_policy_path=ROOT / "governance" / "federation_learning_policy.json",
        )

    def test_existing_qualified_route_prefers_reuse_without_alpha_omega_build(self):
        with tempfile.TemporaryDirectory() as td:
            receipt = self.binding(td).compile(
                mission_id="m-reuse",
                objective="continue mission through an already-qualified route",
                reason="ROUTE_REEVALUATION",
                routes=(
                    RouteCandidate(
                        "fuse-auto",
                        "FUSE_GATEWAY",
                        current=True,
                        callable=True,
                        authorized=True,
                        privacy_ok=True,
                        priority=100,
                    ),
                ),
                selected_upgrade_genes=(),
            )
        body = receipt_to_dict(receipt)
        self.assertEqual(receipt.selected_family, "REUSE_OR_OPTIMISE")
        self.assertEqual(receipt.reuse_vs_build, "REUSE")
        self.assertFalse(receipt.implementation_required)
        self.assertIsNone(receipt.alpha_omega_result)
        self.assertEqual(receipt.authority_ceiling, AUTHORITY_CEILING)
        self.assertFalse(receipt.external_effect)
        self.assertTrue(body["truth_boundary"]["formation_foundry_executed"])
        self.assertTrue(body["truth_boundary"]["formation_foundry_passed"])
        self.assertTrue(body["truth_boundary"]["formation_receipt_bound_to_decision"])

    def test_hard_gap_with_residual_gene_invokes_alpha_omega_plan_only(self):
        with tempfile.TemporaryDirectory() as td:
            receipt = self.binding(td).compile(
                mission_id="m-build",
                objective="close missing durable browser carrier recovery capability",
                reason="NO_QUALIFIED_ROUTE",
                routes=(),
                constraints=("proof-before-claim", "no-authority-expansion"),
                preferred_surfaces=("LOCAL_FUSE", "GENESIS"),
                selected_upgrade_genes=(
                    {
                        "gene_id": "HG-SOL62-101",
                        "category": "DURABLE_EXECUTION",
                        "mechanism": "eager_start_with_durable_fallback",
                        "tags": ["latency", "start", "retry"],
                        "provenance": "runtime harvest",
                        "maturity": "CANDIDATE_RESIDUAL",
                    },
                ),
            )
        body = receipt_to_dict(receipt)
        self.assertEqual(receipt.selected_family, "MATERIALLY_NEW_OR_INNOVATIVE")
        self.assertEqual(receipt.reuse_vs_build, "HARVEST")
        self.assertTrue(receipt.implementation_required)
        self.assertIsNotNone(receipt.alpha_omega_result)
        self.assertEqual(receipt.alpha_omega_result["producer"], "ALPHA_OMEGA_TURNKEY_BUILD_ENGINE")
        self.assertFalse(receipt.alpha_omega_result["local_build_executed"])
        self.assertFalse(receipt.alpha_omega_result["provider_runtime_verified"])
        self.assertFalse(body["truth_boundary"]["external_effect_created"])
        self.assertFalse(body["truth_boundary"]["authority_widened"])
        self.assertFalse(body["truth_boundary"]["source_admitted"])

    def test_formation_result_is_real_canonical_foundry_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            receipt = self.binding(td).compile(
                mission_id="m-foundry",
                objective="repair failure using changed mechanism and regression proof",
                reason="QUALIFIED_ROUTES_EXHAUSTED",
                routes=(),
                selected_upgrade_genes=(
                    {
                        "gene_id": "HG-SOL62-200",
                        "category": "SELF_IMPROVEMENT_EVALUATION",
                        "mechanism": "mechanism_change_required_on_repeat_failure",
                        "tags": ["failure", "repair", "mechanism"],
                        "provenance": "runtime harvest",
                        "maturity": "CANDIDATE_RESIDUAL",
                    },
                ),
            )
        foundry = receipt.formation_foundry_result
        self.assertEqual(foundry["status"], "PASSED")
        self.assertFalse(foundry["external_effect"])
        self.assertEqual(foundry["authority_ceiling"], "A1_INTERNAL")
        self.assertEqual(
            receipt.formation_decision["foundry_cycle_ref"],
            foundry["receipt_sha256"],
        )
        self.assertEqual(foundry["proof"]["learning_chain"]["status"], "PASSED")
        self.assertEqual(foundry["proof"]["evolution_chain"]["status"], "PASSED")


if __name__ == "__main__":
    unittest.main()
