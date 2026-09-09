from __future__ import annotations
import unittest

from benchmarking.cfbe_omega.autopilot_sentinel_cognitive_genome_v1 import (
    ActiveSensingPlanner, AutonomyContext, AutonomyLevel, CausalInterventionCourt,
    ColdSlateAutopilotSentinelCompiler, ColdSlateMissionSpec, GeneDomain,
    HomeostasisAction, InterventionCandidate, MissionHomeostasisController,
    MissionHomeostasisState, RiskAdaptiveAutonomyGate, SensingCandidate,
    SentinelCellEcology, SentinelDomain,
)


def base_state(**overrides):
    body = dict(quality=.95, safety=.97, reliability=.96, evidence_coverage=.90, uncertainty=.15,
                cost_pressure=.20, latency_pressure=.20, owner_burden=.10, blast_radius_risk=.20,
                adversarial_risk=.10, progress=.75, autonomy_trust=.90, repeated_failures=0,
                owner_only_decision=False)
    body.update(overrides)
    return MissionHomeostasisState(**body)


class HomeostasisTests(unittest.TestCase):
    def setUp(self): self.c = MissionHomeostasisController()
    def test_continue_when_healthy(self): self.assertEqual(HomeostasisAction.CONTINUE, self.c.decide(base_state()).action)
    def test_owner_hold(self): self.assertEqual(HomeostasisAction.HOLD_OWNER, self.c.decide(base_state(owner_only_decision=True)).action)
    def test_quarantine_adversarial(self): self.assertEqual(HomeostasisAction.QUARANTINE, self.c.decide(base_state(adversarial_risk=.9)).action)
    def test_rollback_repeated_failures(self): self.assertEqual(HomeostasisAction.ROLLBACK, self.c.decide(base_state(repeated_failures=3)).action)
    def test_degrade_low_safety(self): self.assertEqual(HomeostasisAction.DEGRADE_AUTONOMY, self.c.decide(base_state(safety=.8)).action)
    def test_degrade_low_reliability(self): self.assertEqual(HomeostasisAction.DEGRADE_AUTONOMY, self.c.decide(base_state(reliability=.8)).action)
    def test_active_sense_low_evidence(self): self.assertEqual(HomeostasisAction.ACTIVE_SENSE, self.c.decide(base_state(evidence_coverage=.4)).action)
    def test_active_sense_high_uncertainty(self): self.assertEqual(HomeostasisAction.ACTIVE_SENSE, self.c.decide(base_state(uncertainty=.8)).action)
    def test_simulate_high_blast(self): self.assertEqual(HomeostasisAction.SIMULATE_INTERVENTION, self.c.decide(base_state(blast_radius_risk=.75)).action)
    def test_replan_resource_pressure(self): self.assertEqual(HomeostasisAction.REPLAN, self.c.decide(base_state(progress=.1, cost_pressure=.8)).action)
    def test_form_cells_moderate_adversarial(self): self.assertEqual(HomeostasisAction.FORM_SENTINEL_CELLS, self.c.decide(base_state(adversarial_risk=.6)).action)
    def test_challenge_low_trust(self): self.assertEqual(HomeostasisAction.CHALLENGE, self.c.decide(base_state(autonomy_trust=.4)).action)
    def test_external_effect_never_authorized(self): self.assertFalse(self.c.decide(base_state()).external_effect_authorized)
    def test_invalid_unit_rejected(self):
        with self.assertRaises(ValueError): base_state(quality=1.5).validate()
    def test_autonomy_multiplier_bounded(self): self.assertTrue(0 <= self.c.decide(base_state()).autonomy_multiplier <= 1)


class SentinelCellTests(unittest.TestCase):
    def test_security_identity_cloud_parallel_cells(self):
        p = SentinelCellEcology.form(["threat exploit identity oauth cloud network"], evidence_refs=["p1"])
        domains = {c.domain for c in p.cells}
        self.assertIn(SentinelDomain.SECURITY, domains); self.assertIn(SentinelDomain.IDENTITY, domains); self.assertIn(SentinelDomain.CLOUD_NETWORK, domains)
    def test_agent_prompt_runtime_cell(self):
        p = SentinelCellEcology.form(["agent prompt tool runtime"], evidence_refs=["p1"])
        self.assertIn(SentinelDomain.AGENT_RUNTIME, {c.domain for c in p.cells})
    def test_privacy_cell(self):
        p = SentinelCellEcology.form(["pii privacy exfiltration"], evidence_refs=["p1"])
        self.assertIn(SentinelDomain.DATA_PRIVACY, {c.domain for c in p.cells})
    def test_mobile_cell(self):
        p = SentinelCellEcology.form(["android mobile device app"], evidence_refs=["p1"])
        self.assertIn(SentinelDomain.MOBILE_CLIENT, {c.domain for c in p.cells})
    def test_integrity_cell(self):
        p = SentinelCellEcology.form(["telemetry poison spoof sentinel integrity"], evidence_refs=["p1"])
        self.assertIn(SentinelDomain.INTEGRITY, {c.domain for c in p.cells})
    def test_default_cells(self):
        p = SentinelCellEcology.form(["unknown thing"], evidence_refs=["p1"])
        self.assertEqual({SentinelDomain.RELIABILITY, SentinelDomain.EVIDENCE}, {c.domain for c in p.cells})
    def test_max_parallel(self):
        p = SentinelCellEcology.form(["threat identity cloud privacy agent evidence android cost owner sentinel"], evidence_refs=["p1"], max_parallel=3)
        self.assertLessEqual(len(p.cells), 3)
    def test_evidence_required(self):
        with self.assertRaises(ValueError): SentinelCellEcology.form(["threat"], evidence_refs=[])
    def test_cells_no_effect(self):
        p = SentinelCellEcology.form(["threat"], evidence_refs=["p1"]); self.assertTrue(all(not c.external_effect for c in p.cells))
    def test_plan_hash(self): self.assertEqual(64, len(SentinelCellEcology.form(["threat"], evidence_refs=["p1"]).plan_sha256))


class ActiveSensingTests(unittest.TestCase):
    def setUp(self): self.p = ActiveSensingPlanner()
    def c(self, id, ig, cost, latency, privacy=0, corrupt=0): return SensingCandidate(id,"h",ig,cost,latency,privacy,corrupt)
    def test_information_gain_ranks(self):
        rows = [self.c("a",.8,.2,.2), self.c("b",.4,.2,.2)]
        self.assertEqual("a", self.p.rank(rows)[0].sensing_id)
    def test_privacy_penalty(self):
        rows=[self.c("private",.8,.1,.1,.8), self.c("safe",.6,.1,.1,.0)]
        self.assertEqual("safe", self.p.rank(rows)[0].sensing_id)
    def test_corruption_penalty(self):
        rows=[self.c("bad",.9,.1,.1,0,.9), self.c("good",.5,.1,.1,0,.0)]
        self.assertEqual("good", self.p.rank(rows)[0].sensing_id)
    def test_best_minimum_gain(self): self.assertIsNone(self.p.best([self.c("x",.01,.1,.1)], minimum_information_gain=.05))
    def test_best_returns_candidate(self): self.assertEqual("x", self.p.best([self.c("x",.6,.1,.1)]).sensing_id)
    def test_effectful_sensing_rejected(self):
        with self.assertRaises(ValueError): SensingCandidate("x","h",.5,.1,.1,.1,.1,False).validate()
    def test_negative_cost_rejected(self):
        with self.assertRaises(ValueError): self.c("x",.5,-1,.1).validate()
    def test_gain_range_rejected(self):
        with self.assertRaises(ValueError): self.c("x",1.5,.1,.1).validate()


class InterventionTests(unittest.TestCase):
    def candidate(self, id, risk=.7, quality=.1, cost=.1, blast=.2):
        return InterventionCandidate(id,"svc",risk,quality,cost,blast,True,True,("p",))
    def test_selects_high_utility(self):
        p=CausalInterventionCourt().plan([self.candidate("a",.8,.2,.1,.1), self.candidate("b",.2,0,.5,.8)])
        self.assertEqual("a",p.selected_id)
    def test_no_external_effect(self): self.assertFalse(CausalInterventionCourt().plan([self.candidate("a")]).external_effect_authorized)
    def test_nonreversible_rejected(self):
        with self.assertRaises(ValueError): InterventionCandidate("x","svc",.5,0,0,.1,False,True,("p",)).validate()
    def test_non_simulation_rejected(self):
        with self.assertRaises(ValueError): InterventionCandidate("x","svc",.5,0,0,.1,True,False,("p",)).validate()
    def test_evidence_required(self):
        with self.assertRaises(ValueError): InterventionCandidate("x","svc",.5,0,0,.1,True,True,()).validate()
    def test_plan_hash(self): self.assertEqual(64,len(CausalInterventionCourt().plan([self.candidate("a")]).plan_sha256))


class AutonomyTests(unittest.TestCase):
    def gate(self, **kw):
        body=dict(effect_class="NO_EFFECT",reversible=True,exact_authority=True,evidence_coverage=.9,uncertainty=.1,blast_radius_risk=.1,adversarial_risk=.1,provider_runtime_available=True,owner_approval_required=False); body.update(kw)
        return RiskAdaptiveAutonomyGate().decide(AutonomyContext(**body))
    def test_no_effect_bounded(self): self.assertEqual(AutonomyLevel.BOUNDED_INTERNAL,self.gate().level)
    def test_owner_approval_hold(self): self.assertEqual(AutonomyLevel.HOLD_OWNER,self.gate(owner_approval_required=True).level)
    def test_high_adversarial_observe(self): self.assertEqual(AutonomyLevel.OBSERVE_ONLY,self.gate(adversarial_risk=.8).level)
    def test_high_blast_observe(self): self.assertEqual(AutonomyLevel.OBSERVE_ONLY,self.gate(blast_radius_risk=.9).level)
    def test_low_evidence_observe(self): self.assertEqual(AutonomyLevel.OBSERVE_ONLY,self.gate(evidence_coverage=.4).level)
    def test_high_uncertainty_observe(self): self.assertEqual(AutonomyLevel.OBSERVE_ONLY,self.gate(uncertainty=.7).level)
    def test_a1_internal(self): self.assertEqual(AutonomyLevel.BOUNDED_INTERNAL,self.gate(effect_class="A1").level)
    def test_a2_held(self): self.assertEqual(AutonomyLevel.HOLD_EXTERNAL_GATE,self.gate(effect_class="A2").level)
    def test_provider_unavailable_held(self): self.assertEqual(AutonomyLevel.HOLD_EXTERNAL_GATE,self.gate(effect_class="A2",provider_runtime_available=False).level)
    def test_external_effect_never_true(self): self.assertFalse(self.gate().external_effect_authorized)


class ColdSlateTests(unittest.TestCase):
    def test_compiles_requested_domains(self):
        p=ColdSlateAutopilotSentinelCompiler().compile(ColdSlateMissionSpec("m","o",(GeneDomain.HOMEOSTASIS,GeneDomain.ACTIVE_SENSING),"A1","PRIVATE"))
        self.assertEqual((GeneDomain.ACTIVE_SENSING.value,GeneDomain.HOMEOSTASIS.value),p.domains)
    def test_two_domains_24_genes(self):
        p=ColdSlateAutopilotSentinelCompiler().compile(ColdSlateMissionSpec("m","o",(GeneDomain.HOMEOSTASIS,GeneDomain.ACTIVE_SENSING),"A1","PRIVATE")); self.assertEqual(24,len(p.gene_ids))
    def test_max_genes_caps(self):
        p=ColdSlateAutopilotSentinelCompiler().compile(ColdSlateMissionSpec("m","o",tuple(GeneDomain),"A1","PRIVATE",maximum_genes=10)); self.assertEqual(10,len(p.gene_ids))
    def test_effect_false(self):
        p=ColdSlateAutopilotSentinelCompiler().compile(ColdSlateMissionSpec("m","o",(GeneDomain.HOMEOSTASIS,),"A1","PRIVATE")); self.assertFalse(p.external_effect_authorized)
    def test_hashes_present(self):
        p=ColdSlateAutopilotSentinelCompiler().compile(ColdSlateMissionSpec("m","o",(GeneDomain.HOMEOSTASIS,),"A1","PRIVATE")); self.assertEqual(64,len(p.profile_sha256)); self.assertEqual(64,len(p.source_genome_sha256))
    def test_empty_domains_rejected(self):
        with self.assertRaises(ValueError): ColdSlateMissionSpec("m","o",(),"A1","PRIVATE").validate()
