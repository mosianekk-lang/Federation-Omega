import unittest

from formation_omega.autonomic_fabric import AuthorityCeiling
from formation_omega.institutional_cognition import (
    Anomaly,
    AnomalySeverity,
    ConstitutionKernel,
    CouncilMember,
    EvidenceWeightedCouncil,
    FederatedCognitiveInstitution,
    FractalDelegationGuard,
    Horizon,
    HorizonObjective,
    ImprovementCandidate,
    InstitutionalImmuneSystem,
    InstitutionalMemory,
    InstitutionalProposal,
    InstitutionalRole,
    MultiTimescalePlanner,
    PolicyCandidate,
    PolicyEvolutionLab,
    PolicyStage,
    RecursiveImprovementGate,
    RobustScenarioPlanner,
    ScenarioOption,
    Delegation,
)


class InstitutionalCognitionTests(unittest.TestCase):
    def members(self):
        return (
            CouncilMember("builder", InstitutionalRole.BUILDER, "engineering", 0.9, 0.9, 0.8, 1.0),
            CouncilMember("falsifier", InstitutionalRole.FALSIFIER, "adversarial", 0.9, 0.9, 0.8, 0.8),
            CouncilMember("auditor", InstitutionalRole.AUDITOR, "audit", 0.9, 0.9, 0.8, 0.9),
        )

    def test_constitution_rejects_authority_expansion(self):
        proposal = InstitutionalProposal("P1", "Expand provider authority", AuthorityCeiling.A2_BOUNDED_EFFECT)
        result = ConstitutionKernel().evaluate(proposal, institutional_ceiling=AuthorityCeiling.A1_INTERNAL)
        self.assertFalse(result.admitted)
        self.assertIn("AUTHORITY_CEILING_EXCEEDED", result.vetoes)

    def test_constitution_rejects_self_certification(self):
        proposal = InstitutionalProposal("P1", "Self certify closure", AuthorityCeiling.A1_INTERNAL, self_certified=True)
        result = ConstitutionKernel().evaluate(proposal)
        self.assertFalse(result.admitted)
        self.assertIn("SELF_CERTIFICATION_PROHIBITED", result.vetoes)

    def test_owner_intent_change_requires_owner(self):
        proposal = InstitutionalProposal("P1", "Change owner objective", AuthorityCeiling.A1_INTERNAL, owner_intent_change=True)
        blocked = ConstitutionKernel().evaluate(proposal)
        allowed = ConstitutionKernel().evaluate(proposal, owner_approval=True)
        self.assertFalse(blocked.admitted)
        self.assertTrue(allowed.admitted)
        self.assertTrue(allowed.owner_gate_required)

    def test_council_requires_independent_domains(self):
        members = (
            CouncilMember("a", InstitutionalRole.BUILDER, "same", 1, 1, 1, 1),
            CouncilMember("b", InstitutionalRole.VERIFIER, "same", 1, 1, 1, 1),
            CouncilMember("c", InstitutionalRole.AUDITOR, "same", 1, 1, 1, 1),
        )
        result = EvidenceWeightedCouncil().decide(members)
        self.assertEqual(result.outcome, "HELD_INSUFFICIENT_INDEPENDENCE")

    def test_critical_falsifier_veto_holds_even_with_support(self):
        members = list(self.members())
        members[1] = CouncilMember("falsifier", InstitutionalRole.FALSIFIER, "adversarial", 0.9, 0.9, 0.8, 1.0, critical_veto=True)
        result = EvidenceWeightedCouncil().decide(members)
        self.assertEqual(result.outcome, "HELD_CRITICAL_VETO")

    def test_evidence_weighted_quorum_can_admit(self):
        result = EvidenceWeightedCouncil().decide(self.members())
        self.assertEqual(result.outcome, "ADMIT")
        self.assertEqual(result.independent_domains, 3)

    def test_timescale_planner_prevents_long_horizon_starvation(self):
        objectives = (
            HorizonObjective("T", Horizon.TACTICAL, 1.0, 1.0, 0.1, 0.1),
            HorizonObjective("O", Horizon.OPERATIONAL, 0.9, 0.8, 0.4, 0.3),
            HorizonObjective("S", Horizon.STRATEGIC, 0.8, 0.5, 0.8, 0.8),
            HorizonObjective("G", Horizon.GENERATIONAL, 0.7, 0.2, 1.0, 0.9),
        )
        selected = MultiTimescalePlanner().select(objectives, slots=4)
        self.assertEqual({item.horizon for item in selected}, set(Horizon))

    def test_ageing_increases_priority(self):
        young = HorizonObjective("young", Horizon.STRATEGIC, 0.5, 0.5, 0.5, 0.5, age_cycles=0)
        old = HorizonObjective("old", Horizon.STRATEGIC, 0.5, 0.5, 0.5, 0.5, age_cycles=20)
        self.assertGreater(old.priority, young.priority)

    def test_robust_planner_uses_minimax_regret(self):
        options = (
            ScenarioOption("fragile", {"growth": 1.0, "stress": 0.1}, irreversible_risk=0.5, evidence_strength=0.8),
            ScenarioOption("robust", {"growth": 0.8, "stress": 0.7}, irreversible_risk=0.1, evidence_strength=0.9),
        )
        result = RobustScenarioPlanner().choose(options)
        self.assertEqual(result.option_id, "robust")

    def test_policy_cannot_skip_stages(self):
        policy = PolicyCandidate("POL1", PolicyStage.CANDIDATE)
        result = PolicyEvolutionLab().promote(policy, PolicyStage.CANARY)
        self.assertFalse(result.admitted)
        self.assertIn("STAGE_SKIP_PROHIBITED", result.blockers)

    def test_policy_adoption_requires_replication_rollback_and_owner_when_consequential(self):
        base = PolicyCandidate(
            "POL1",
            PolicyStage.CANARY,
            measured_gain=0.2,
            regression_score=0.0,
            independent_replications=2,
            rollback_verified=True,
            consequential=True,
            owner_approved=False,
        )
        blocked = PolicyEvolutionLab().promote(base, PolicyStage.ADOPTED)
        self.assertIn("OWNER_APPROVAL_REQUIRED", blocked.blockers)
        approved = PolicyEvolutionLab().promote(
            PolicyCandidate(**{**base.__dict__, "owner_approved": True}),
            PolicyStage.ADOPTED,
        )
        self.assertTrue(approved.admitted)

    def test_recursive_improvement_requires_real_gain_and_reproduction(self):
        candidate = ImprovementCandidate("I1", 0.7, 0.8, False, True, True)
        admitted, blockers, _ = RecursiveImprovementGate().evaluate(candidate)
        self.assertTrue(admitted)
        self.assertEqual(blockers, ())
        weak = ImprovementCandidate("I2", 0.7, 0.7, False, False, True)
        admitted, blockers, _ = RecursiveImprovementGate().evaluate(weak)
        self.assertFalse(admitted)
        self.assertIn("NO_MEASURED_GAIN", blockers)
        self.assertIn("INDEPENDENT_REPRODUCTION_REQUIRED", blockers)

    def test_fractal_delegation_can_only_narrow_authority(self):
        guard = FractalDelegationGuard()
        ok, _ = guard.validate(Delegation("parent", "child", AuthorityCeiling.A2_BOUNDED_EFFECT, AuthorityCeiling.A1_INTERNAL, ("mission",)))
        self.assertTrue(ok)
        ok, reason = guard.validate(Delegation("parent", "child", AuthorityCeiling.A1_INTERNAL, AuthorityCeiling.A2_BOUNDED_EFFECT, ("mission",)))
        self.assertFalse(ok)
        self.assertEqual(reason, "CHILD_AUTHORITY_EXPANSION")

    def test_immune_system_isolates_local_failure_without_global_freeze(self):
        anomaly = Anomaly("A1", AnomalySeverity.CRITICAL, ("github",), 0.99, True)
        result = InstitutionalImmuneSystem().contain(anomaly, federation_domain_count=5)
        self.assertFalse(result.global_freeze)
        self.assertTrue(result.independent_work_may_continue)
        self.assertEqual(result.isolate_domains, ("github",))

    def test_immune_system_global_freeze_requires_federation_wide_critical_evidence(self):
        anomaly = Anomaly("A1", AnomalySeverity.CRITICAL, ("a", "b", "c"), 0.95, False)
        result = InstitutionalImmuneSystem().contain(anomaly, federation_domain_count=3)
        self.assertTrue(result.global_freeze)
        self.assertFalse(result.independent_work_may_continue)
        self.assertTrue(result.escalate_to_owner)

    def test_institutional_memory_is_hash_chained(self):
        memory = InstitutionalMemory()
        memory.append("ONE", {"x": 1})
        memory.append("TWO", {"x": 2})
        self.assertTrue(memory.verify())
        self.assertEqual(memory.events()[1].previous_hash, memory.events()[0].event_hash)

    def test_full_institutional_cycle_is_deterministic_and_no_effect(self):
        institution = FederatedCognitiveInstitution()
        proposal = InstitutionalProposal("P1", "Select next internal strategic work", AuthorityCeiling.A1_INTERNAL)
        objectives = (
            HorizonObjective("T", Horizon.TACTICAL, 0.7, 0.8, 0.2, 0.2),
            HorizonObjective("S", Horizon.STRATEGIC, 0.9, 0.4, 0.9, 0.8),
        )
        scenarios = (
            ScenarioOption("A", {"normal": 0.8, "stress": 0.7}, evidence_strength=0.9),
            ScenarioOption("B", {"normal": 0.9, "stress": 0.3}, irreversible_risk=0.4, evidence_strength=0.8),
        )
        receipt = institution.deliberate(
            proposal=proposal,
            council_members=self.members(),
            objectives=objectives,
            scenario_options=scenarios,
            slots=2,
        )
        self.assertTrue(receipt.cycle_sha256)
        self.assertTrue(institution.memory.verify())
        self.assertEqual(len(institution.memory.events()), 1)


if __name__ == "__main__":
    unittest.main()
