from __future__ import annotations

import unittest
from evidenceops.capital_intelligence_os.algorithms import AttentionCompressionEngine, CounterfactualCapitalRegret, DecisionReversalThreshold, FragilityCascade, TrustDecayClock
from evidenceops.capital_intelligence_os.authority import AuthorityGuard
from evidenceops.capital_intelligence_os.autopilot import Autopilot
from evidenceops.capital_intelligence_os.capital import GravityEngine, FinancingStressEngine
from evidenceops.capital_intelligence_os.learning import LearningLedger, LearningEvent
from evidenceops.capital_intelligence_os.maturity import MaturityEvidence, MaturityGovernor
from evidenceops.capital_intelligence_os.mna import DealLifecycle, MNA_STAGES
from evidenceops.capital_intelligence_os.models import ActionDisposition, ActionRequest, AuthorityLevel, CapitalCandidate, Claim, Domain, EvidenceRef, EvidenceStatus, Event, InformationClass, MaturityState
from evidenceops.capital_intelligence_os.proofgraph import ProofGraph
from evidenceops.capital_intelligence_os.verify_release import verify

class AuthorityTests(unittest.TestCase):
    def setUp(self): self.guard = AuthorityGuard()
    def test_public_to_private_analysis_allowed(self):
        d = self.guard.evaluate(ActionRequest("INGEST_PUBLIC_MARKET_DATA", Domain.PUBLIC_MARKETS, Domain.PRIVATE_MNA, InformationClass.PUBLIC)); self.assertIn(d.disposition, {ActionDisposition.ALLOW_INTERNAL, ActionDisposition.ALLOW_LOGGED})
    def test_private_to_market_denied(self):
        d = self.guard.evaluate(ActionRequest("EXPORT_SIGNAL", Domain.PRIVATE_MNA, Domain.PUBLIC_MARKETS, InformationClass.CONFIDENTIAL)); self.assertEqual(d.disposition, ActionDisposition.DENY); self.assertIn("PRIVATE_TO_TRADING_FIREWALL", d.reason_codes)
    def test_unknown_to_market_fail_closed(self):
        d = self.guard.evaluate(ActionRequest("EXPORT_SIGNAL", Domain.PRIVATE_MNA, Domain.PUBLIC_MARKETS, InformationClass.UNKNOWN)); self.assertEqual(d.disposition, ActionDisposition.DENY)
    def test_live_order_is_hard_denied(self):
        d = self.guard.evaluate(ActionRequest("LIVE_ORDER", Domain.PUBLIC_MARKETS, Domain.PUBLIC_MARKETS, InformationClass.PUBLIC, financial_effect=True, requested_authority=AuthorityLevel.A5_SOVEREIGN_AUTHORITY)); self.assertEqual(d.disposition, ActionDisposition.DENY)
    def test_payment_requires_human(self):
        d = self.guard.evaluate(ActionRequest("MAKE_PAYMENT", Domain.PRIVATE_MNA, Domain.PRIVATE_MNA, InformationClass.CONFIDENTIAL, financial_effect=True)); self.assertEqual(d.disposition, ActionDisposition.REQUIRE_HUMAN)

class ProofGraphTests(unittest.TestCase):
    def setUp(self): self.ref = EvidenceRef("src-1", "document", "p.1")
    def test_verified_requires_evidence(self):
        with self.assertRaises(ValueError): ProofGraph().add_claim(Claim("co", "revenue", 100, EvidenceStatus.VERIFIED, confidence=0.9))
    def test_contradiction_detected(self):
        g = ProofGraph(); g.add_claim(Claim("co", "revenue", 100, EvidenceStatus.VERIFIED, [self.ref], confidence=0.95)); c = g.add_claim(Claim("co", "revenue", 120, EvidenceStatus.CORROBORATED, [self.ref], confidence=0.9)); self.assertEqual(len(c), 1); self.assertGreater(c[0].severity, 0.8)
    def test_dependency_impact_propagates(self):
        g = ProofGraph(); g.add_dependency("rates", "wacc"); g.add_dependency("wacc", "valuation"); g.add_dependency("valuation", "irr"); self.assertEqual(g.impact_of("rates"), ["wacc", "valuation", "irr"])

class AlgorithmTests(unittest.TestCase):
    def test_trust_decay_is_monotonic_and_bounded(self):
        a = TrustDecayClock(); fresh = a.adjusted_confidence(0.9, 10, 30); stale = a.adjusted_confidence(0.9, 120, 30); self.assertEqual(fresh, 0.9); self.assertTrue(0 <= stale < fresh)
    def test_attention_compression_suppresses_low_value_noise(self):
        a = AttentionCompressionEngine(); low = a.make_alert("x", "noise", materiality=0.1, uncertainty=0.1, irreversibility=0.0, deadline_pressure=0.0, auto_resolvability=1.0); high = a.make_alert("x", "material", materiality=1.0, uncertainty=0.8, irreversibility=0.9, deadline_pressure=0.8, auto_resolvability=0.0); self.assertIsNone(low); self.assertIsNotNone(high); self.assertTrue(high.requires_human)
    def test_decision_reversal_threshold(self):
        t = DecisionReversalThreshold().find(lambda x: x - 5.0, baseline=8.0, lower=0.0, upper=10.0); self.assertIsNotNone(t); self.assertAlmostEqual(t, 5.0, places=4)
    def test_counterfactual_regret(self):
        r = CounterfactualCapitalRegret().evaluate(80.0, [70.0, 120.0, 100.0]); self.assertEqual(r.regret, 40.0); self.assertGreater(r.normalized_regret, 0.3)
    def test_fragility_cascade_attenuates(self):
        g = ProofGraph(); g.add_dependency("customer", "revenue"); g.add_dependency("revenue", "ebitda"); p = FragilityCascade().propagate(g, "customer", 1.0, attenuation=0.5); self.assertEqual(p["customer"], 1.0); self.assertEqual(p["revenue"], 0.5); self.assertEqual(p["ebitda"], 0.25)

class CapitalAndDealTests(unittest.TestCase):
    def test_gravity_is_deterministic(self):
        e = GravityEngine(); a = CapitalCandidate("acq-a", 100, 0.9, 0.9, 0.8, 0.4, 0.8, 0.7, 0.6, 0.5); b = CapitalCandidate("debt-paydown", 55, 0.99, 0.7, 0.3, 0.1, 0.3, 0.2, 0.1, 0.2); one = e.rank([a,b]); two = e.rank([b,a]); self.assertEqual([(x.candidate_id,x.score) for x in one], [(x.candidate_id,x.score) for x in two])
    def test_financing_stress(self): self.assertEqual(FinancingStressEngine().annual_interest_delta(100_000_000, 200), 2_000_000)
    def test_mna_has_60_stages(self): self.assertEqual(len(MNA_STAGES), 60)
    def test_mna_prerequisite_gate(self):
        d = DealLifecycle("deal-1");
        with self.assertRaises(ValueError): d.complete("SIGNING")
        d.complete("INITIAL_SCREENING"); d.complete("NDA"); self.assertIn("NDA", d.completed)

class LearningAndMaturityTests(unittest.TestCase):
    def test_learning_chain_and_tamper_detection(self):
        l = LearningLedger(); l.append("SUCCESS", "A", {"x":1}); l.append("FAILURE", "B", {"x":2}); self.assertTrue(l.verify()); o = l._events[1]; l._events[1] = LearningEvent(o.event_type,o.category,{"x":999},o.previous_hash,o.created_at,o.event_hash); self.assertFalse(l.verify())
    def test_maturity_blocks_deployed_without_runtime_proof(self):
        g = MaturityGovernor(); e = MaturityEvidence(True,True,True,True); self.assertEqual(g.highest_proven(e), MaturityState.VERIFIED);
        with self.assertRaises(ValueError): g.assert_promotion(MaturityState.DEPLOYED,e)
    def test_maturity_deployed_requires_health_persistence_rollback(self):
        g = MaturityGovernor(); e = MaturityEvidence(True,True,True,True,True,True,True,True,False); self.assertEqual(g.highest_proven(e), MaturityState.DEPLOYED)

class AutopilotTests(unittest.TestCase):
    def test_material_event_updates_graph_and_preserves_authority(self):
        a = Autopilot(); a.graph.add_dependency("rates","wacc"); a.graph.add_dependency("wacc","valuation"); event = Event("RATE_CHANGE","public-central-bank","rates",{"bps":200},Domain.PUBLIC_MARKETS,InformationClass.PUBLIC,0.9); claim = Claim("rates","policy_rate",10.0,EvidenceStatus.VERIFIED,[EvidenceRef("cb","public_release","rate")],InformationClass.PUBLIC,Domain.PUBLIC_MARKETS,0.99); live = ActionRequest("LIVE_ORDER",Domain.PUBLIC_MARKETS,Domain.PUBLIC_MARKETS,InformationClass.PUBLIC,financial_effect=True); r = a.process(event,[claim],[live]); self.assertIn("valuation",r.impacted_subjects); self.assertEqual(r.action_decisions[0].disposition,ActionDisposition.DENY); self.assertTrue(a.ledger.verify())
    def test_release_verifier(self): self.assertTrue(verify()["passed"])

if __name__ == "__main__": unittest.main()
