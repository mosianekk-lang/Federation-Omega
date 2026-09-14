from __future__ import annotations

import unittest

from ao_harmonic_v3.forest_integrity import (
    CapabilityTruth,
    ComplexityBudget,
    ConfidenceBand,
    DecisionContract,
    EffectContract,
    EvidenceAtom,
    ForestFitnessObservation,
    ForestIntegrityError,
    FreshnessState,
    ObjectiveGenome,
    PathCandidate,
    ReadbackReceipt,
    effect_proved,
    rank_admissible_paths,
)
from ao_harmonic_v3.models import Maturity, TruthState


class ForestFirstIntegrityV1Tests(unittest.TestCase):
    def evidence(self, **overrides):
        payload = {
            "evidence_id": "E-1",
            "statement": "provider state was read back",
            "truth_state": TruthState.VERIFIED,
            "source_refs": ("provider:receipt:1",),
            "verified_at": "2026-08-30T10:00:00Z",
            "ttl_seconds": 3600,
            "confidence_band": ConfidenceBand.HIGH,
            "direct": True,
        }
        payload.update(overrides)
        return EvidenceAtom(**payload)

    def path(self, identity="P1", **overrides):
        payload = {
            "path_id": identity,
            "available": True,
            "authorised": True,
            "safe": True,
            "deadline_viable": True,
            "privacy_acceptable": True,
            "cost_acceptable": True,
            "dependencies_ready": True,
            "evidence_sufficient": True,
            "rollback_available": True,
            "strategic_value": 0.8,
            "proof_strength": 0.8,
            "reversibility": 0.9,
            "information_gain": 0.6,
            "owner_burden": 0.1,
            "maintenance_cost": 0.1,
        }
        payload.update(overrides)
        return PathCandidate(**payload)

    def objective(self):
        return ObjectiveGenome(
            objective_id="O1",
            objective="preserve the whole objective",
            desired_outcome="verified safe completion",
            success_conditions=("provider readback matches expected effect",),
            stop_conditions=("authority boundary changes",),
        )

    def test_verified_evidence_requires_source_and_timestamp(self):
        with self.assertRaisesRegex(ForestIntegrityError, "VERIFIED_EVIDENCE_REQUIRES_SOURCE_REF"):
            self.evidence(source_refs=())
        with self.assertRaisesRegex(ForestIntegrityError, "VERIFIED_EVIDENCE_REQUIRES_VERIFIED_AT"):
            self.evidence(verified_at=None)

    def test_ttl_downgrades_freshness_without_rewriting_truth_state(self):
        atom = self.evidence()
        self.assertEqual(atom.freshness(as_of="2026-08-30T10:30:00Z"), FreshnessState.CURRENT)
        self.assertEqual(atom.freshness(as_of="2026-08-30T12:00:01Z"), FreshnessState.STALE)
        self.assertEqual(atom.truth_state, TruthState.VERIFIED)
        self.assertFalse(atom.consequentially_usable(as_of="2026-08-30T12:00:01Z"))

    def test_synthetic_or_disputed_evidence_cannot_support_consequential_release(self):
        self.assertFalse(self.evidence(synthetic=True).consequentially_usable(as_of="2026-08-30T10:30:00Z"))
        self.assertFalse(self.evidence(disputed=True).consequentially_usable(as_of="2026-08-30T10:30:00Z"))

    def test_objective_genome_requires_success_definition(self):
        with self.assertRaisesRegex(ForestIntegrityError, "SUCCESS_CONDITION_REQUIRED"):
            ObjectiveGenome("O", "objective", "outcome", ())

    def test_inadmissible_path_cannot_win_even_with_higher_score(self):
        blocked = self.path("BLOCKED", authorised=False, strategic_value=100.0)
        admitted = self.path("ADMITTED", strategic_value=0.5)
        ranked = rank_admissible_paths((blocked, admitted))
        self.assertEqual([row.path_id for row in ranked], ["ADMITTED"])

    def test_high_irreversibility_requires_owner_authority_and_rollback(self):
        with self.assertRaisesRegex(ForestIntegrityError, "HIGH_IRREVERSIBILITY_REQUIRES_OWNER_AUTHORITY"):
            DecisionContract(
                "D1", self.objective(), ("E-1",), ("P1",), self.path(),
                ConfidenceBand.MODERATE, 0.8, False,
            )
        held = DecisionContract(
            "D2", self.objective(), ("E-1",), ("P1",), self.path(rollback_available=False),
            ConfidenceBand.MODERATE, 0.8, True, owner_approved=True,
        )
        self.assertFalse(held.release_allowed(as_of="2026-08-30T10:30:00Z"))

    def test_owner_required_decision_is_held_until_approved(self):
        decision = DecisionContract(
            "D3", self.objective(), ("E-1",), ("P1",), self.path(),
            ConfidenceBand.HIGH, 0.8, True, owner_approved=False,
        )
        self.assertFalse(decision.release_allowed(as_of="2026-08-30T10:30:00Z"))

    def test_effect_claim_requires_matching_semantic_provider_readback(self):
        contract = EffectContract(
            effect_id="FX1",
            target="provider:resource",
            prior_state_sha256="before",
            expected_delta={"status": "READY"},
            authority_ref="authority:A1",
            rollback_ref="rollback:R1",
            success_predicate="status == READY",
        )
        bad = ReadbackReceipt(
            effect_id="FX1",
            target="provider:resource",
            prior_state_sha256="before",
            after_state_sha256="after",
            observed_delta={"status": "PENDING"},
            provider_ref="provider:receipt:2",
            readback_at="2026-08-30T10:05:00Z",
            semantic_success=True,
        )
        good = ReadbackReceipt(
            effect_id="FX1",
            target="provider:resource",
            prior_state_sha256="before",
            after_state_sha256="after",
            observed_delta={"status": "READY", "other": "preserved"},
            provider_ref="provider:receipt:3",
            readback_at="2026-08-30T10:06:00Z",
            semantic_success=True,
        )
        self.assertFalse(effect_proved(contract, bad))
        self.assertTrue(effect_proved(contract, good))

    def test_source_presence_never_implies_executability(self):
        source_only = CapabilityTruth(
            capability_id="CAP",
            source_present=True,
            connected=False,
            authorised=False,
            provider_verified=False,
            semantic_success=False,
            fresh=False,
            maturity=Maturity.SOURCE_IMPLEMENTED,
        )
        self.assertFalse(source_only.executable())
        live = CapabilityTruth(
            capability_id="CAP",
            source_present=True,
            connected=True,
            authorised=True,
            provider_verified=True,
            semantic_success=True,
            fresh=True,
            maturity=Maturity.OPERATIONAL_VERIFIED,
        )
        self.assertTrue(live.executable())

    def test_complexity_budget_rejects_net_new_component_without_measurable_gain(self):
        no_gain = ComplexityBudget("C1", 3, 0, False, 0, 0, unique_failure_domain=True)
        self.assertFalse(no_gain.admitted())
        consolidation = ComplexityBudget("C2", 2, 5, True, -1, -1)
        self.assertTrue(consolidation.admitted())

    def test_empirical_fitness_rejects_synthetic_or_unproven_observation(self):
        synthetic = ForestFitnessObservation("F1", ("receipt:1",), True, 0, 0, 0, 1.0, 2.0, synthetic=True)
        unsupported = ForestFitnessObservation("F2", (), True, 0, 0, 0, 1.0, 2.0)
        observed = ForestFitnessObservation("F3", ("provider:receipt:3",), True, 0, 0, 0, 1.0, 2.0)
        self.assertFalse(synthetic.eligible_for_empirical_learning())
        self.assertFalse(unsupported.eligible_for_empirical_learning())
        self.assertTrue(observed.eligible_for_empirical_learning())


if __name__ == "__main__":
    unittest.main()
