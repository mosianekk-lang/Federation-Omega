from __future__ import annotations

import unittest

from ao_harmonic_v3.forest_integrity import (
    CapabilityTruth,
    ConfidenceBand,
    DecisionContract,
    EvidenceAtom,
    ObjectiveGenome,
    PathCandidate,
    rank_admissible_paths,
)
from ao_harmonic_v3.models import Maturity, TruthState


class PhoenixProviderCutoverV3ForestIntegrityTests(unittest.TestCase):
    def test_integrity_tranche_is_fail_closed_before_runtime_binding(self):
        evidence = EvidenceAtom(
            evidence_id="E-CANONICAL",
            statement="provider state was semantically read back",
            truth_state=TruthState.VERIFIED,
            source_refs=("provider:receipt:canonical",),
            verified_at="2026-08-30T10:00:00Z",
            ttl_seconds=3600,
            confidence_band=ConfidenceBand.HIGH,
            direct=True,
        )
        self.assertTrue(evidence.consequentially_usable(as_of="2026-08-30T10:30:00Z"))
        self.assertFalse(evidence.consequentially_usable(as_of="2026-08-30T12:00:01Z"))

        blocked = PathCandidate(
            path_id="BLOCKED-HIGH-SCORE",
            available=True,
            authorised=False,
            safe=True,
            deadline_viable=True,
            privacy_acceptable=True,
            cost_acceptable=True,
            dependencies_ready=True,
            evidence_sufficient=True,
            rollback_available=True,
            strategic_value=100.0,
            proof_strength=100.0,
        )
        admitted = PathCandidate(
            path_id="ADMITTED-LOWER-SCORE",
            available=True,
            authorised=True,
            safe=True,
            deadline_viable=True,
            privacy_acceptable=True,
            cost_acceptable=True,
            dependencies_ready=True,
            evidence_sufficient=True,
            rollback_available=True,
            strategic_value=1.0,
            proof_strength=1.0,
            reversibility=1.0,
        )
        ranked = rank_admissible_paths((blocked, admitted), rollback_required=True)
        self.assertEqual(tuple(path.path_id for path in ranked), ("ADMITTED-LOWER-SCORE",))

        objective = ObjectiveGenome(
            objective_id="O-CANONICAL",
            objective="preserve the whole objective",
            desired_outcome="verified safe completion",
            success_conditions=("semantic provider readback matches expected effect",),
            stop_conditions=("authority boundary changes",),
        )
        held_decision = DecisionContract(
            decision_id="D-CANONICAL",
            objective=objective,
            evidence_refs=(evidence.evidence_id,),
            alternatives=(blocked.path_id, admitted.path_id),
            selected_path=admitted,
            uncertainty_band=ConfidenceBand.MODERATE,
            irreversibility=0.8,
            owner_authority_required=True,
            owner_approved=False,
        )
        self.assertFalse(held_decision.release_allowed(as_of="2026-08-30T10:30:00Z"))

        source_only = CapabilityTruth(
            capability_id="CAP-SOURCE-ONLY",
            source_present=True,
            connected=False,
            authorised=False,
            provider_verified=False,
            semantic_success=False,
            fresh=False,
            maturity=Maturity.SOURCE_IMPLEMENTED,
        )
        self.assertFalse(source_only.executable())

    def test_integrity_tranche_does_not_claim_external_effect_or_provider_runtime(self):
        source_only = CapabilityTruth(
            capability_id="CAP-BOUNDED",
            source_present=True,
            connected=False,
            authorised=False,
            provider_verified=False,
            semantic_success=False,
            fresh=False,
            maturity=Maturity.DETERMINISTIC_TESTED,
        )
        self.assertFalse(source_only.executable(minimum_maturity=Maturity.WORKFLOW_VERIFIED))


if __name__ == "__main__":
    unittest.main()
