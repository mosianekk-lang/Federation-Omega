from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import tempfile
import unittest

from evidenceops.capital_intelligence_os.decision_algorithms import (
    AssumptionCriticalityRanker, AssumptionSignal, DealSunkCostBiasGuard,
    EvidenceFreshnessRisk, InformationQuestion, InformationValuePrioritizer,
    NoDealDominanceTest, OutcomeCalibrationScore, RegimeSensitivityVector,
    SynergyDoubleCountDetector, SynergyItem, ThesisDecayIndex,
)
from evidenceops.capital_intelligence_os.durable import DurableAutopilotRuntime
from evidenceops.capital_intelligence_os.failure_genome import FailureToRouteGeneCompiler
from evidenceops.capital_intelligence_os.models import (
    ActionDisposition, ActionRequest, Domain, EvidenceRef, EvidenceStatus,
    Event, InformationClass, Claim,
)
from evidenceops.capital_intelligence_os.outcomenet import DataUseConsent, OutcomeNet, OutcomeObservation
from evidenceops.capital_intelligence_os.passport import DealPassportIssuer
from evidenceops.capital_intelligence_os.restricted import RestrictedEntry, RestrictedListRegistry
from evidenceops.capital_intelligence_os.store import SqliteStateStore
from evidenceops.capital_intelligence_os.tenancy import TenantBoundaryGuard, TenantContext


class StoreTests(unittest.TestCase):
    def setUp(self): self.store = SqliteStateStore(":memory:")
    def tearDown(self): self.store.close()
    def test_quick_check(self): self.assertTrue(self.store.quick_check())
    def test_event_is_tenant_scoped(self):
        e = Event("X", "s", "subj", {"x":1}, Domain.PRIVATE_MNA, InformationClass.CONFIDENTIAL, 0.2)
        self.assertTrue(self.store.append_event("t1", e)); self.assertEqual(len(self.store.load_events("t1")), 1); self.assertEqual(len(self.store.load_events("t2")), 0)
    def test_duplicate_event_is_idempotent_at_store_boundary(self):
        e = Event("X", "s", "subj", {}, Domain.PRIVATE_MNA, InformationClass.CONFIDENTIAL, 0.2)
        self.assertTrue(self.store.append_event("t1", e)); self.assertFalse(self.store.append_event("t1", e))
    def test_claim_roundtrip_preserves_fingerprint(self):
        ref = EvidenceRef("src", "doc", "p1")
        c = Claim("co", "revenue", 10, EvidenceStatus.VERIFIED, [ref], InformationClass.CONFIDENTIAL, Domain.PRIVATE_MNA, 0.99)
        self.store.save_claim("t1", c); loaded = self.store.load_claims("t1")[0]; self.assertEqual(c.fingerprint(), loaded.fingerprint())
    def test_dependency_roundtrip(self):
        self.store.add_dependency("t1", "rates", "wacc"); self.assertEqual(self.store.load_dependencies("t1"), [("rates", "wacc")])
    def test_idempotent_result_is_tenant_scoped(self):
        self.store.save_idempotent_result("t1", "k", {"x": 1}); self.assertEqual(self.store.get_idempotent_result("t1", "k")["x"], 1); self.assertIsNone(self.store.get_idempotent_result("t2", "k"))
    def test_learning_chain_survives_multiple_events(self):
        self.store.append_learning("t1", "SUCCESS", "A", {"x":1}); self.store.append_learning("t1", "FAILURE", "B", {"x":2}); self.assertTrue(self.store.verify_learning_chain("t1"))
    def test_file_persistence_survives_reopen(self):
        fd, path = tempfile.mkstemp(suffix=".sqlite3"); os.close(fd)
        try:
            s1 = SqliteStateStore(path); e = Event("X", "s", "subj", {}, Domain.PRIVATE_MNA, InformationClass.CONFIDENTIAL, 0.2); s1.append_event("t1", e); s1.close()
            s2 = SqliteStateStore(path); self.assertEqual(len(s2.load_events("t1")), 1); self.assertTrue(s2.quick_check()); s2.close()
        finally: Path(path).unlink(missing_ok=True)


class TenantTests(unittest.TestCase):
    def test_cross_tenant_guard_fails(self):
        with self.assertRaises(PermissionError): TenantBoundaryGuard.assert_tenant(TenantContext("t1", "u"), "t2")
    def test_domain_guard_fails(self):
        with self.assertRaises(PermissionError): TenantBoundaryGuard.assert_domain(TenantContext("t1", "u", allowed_domains=(Domain.PRIVATE_MNA,)), Domain.PUBLIC_MARKETS)
    def test_duplicate_roles_rejected(self):
        with self.assertRaises(ValueError): TenantContext("t1", "u", roles=("a","a")).validate()


class DurableAutopilotTests(unittest.TestCase):
    def setUp(self):
        self.store = SqliteStateStore(":memory:"); self.runtime = DurableAutopilotRuntime(self.store); self.ctx = TenantContext("tenant-a", "user-a")
    def tearDown(self): self.store.close()
    def _event(self): return Event("RATE_CHANGE", "public", "rates", {"bps":200}, Domain.PUBLIC_MARKETS, InformationClass.PUBLIC, 0.9)
    def test_idempotent_replay_creates_no_duplicate_event_or_learning(self):
        event = self._event(); first = self.runtime.process(self.ctx, event); events = self.store.count_rows("events", self.ctx.tenant_id); learning = self.store.count_rows("learning_events", self.ctx.tenant_id); second = self.runtime.process(self.ctx, event)
        self.assertFalse(first["replayed"]); self.assertTrue(second["replayed"]); self.assertEqual(self.store.count_rows("events", self.ctx.tenant_id), events); self.assertEqual(self.store.count_rows("learning_events", self.ctx.tenant_id), learning)
    def test_idempotency_key_reuse_with_different_request_is_rejected(self):
        self.runtime.process(self.ctx, self._event(), idempotency_key="stable-key")
        second = Event("RATE_CHANGE", "public", "rates", {"bps":500}, Domain.PUBLIC_MARKETS, InformationClass.PUBLIC, 0.9)
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_REUSE_MISMATCH"): self.runtime.process(self.ctx, second, idempotency_key="stable-key")
    def test_failed_claim_rolls_back_event(self):
        invalid = Claim("rates", "policy_rate", 9, EvidenceStatus.VERIFIED, [], InformationClass.PUBLIC, Domain.PUBLIC_MARKETS, 0.9)
        with self.assertRaises(ValueError): self.runtime.process(self.ctx, self._event(), [invalid])
        self.assertEqual(self.store.count_rows("events", self.ctx.tenant_id), 0); self.assertEqual(self.store.count_rows("learning_events", self.ctx.tenant_id), 0)
    def test_dependency_survives_restart(self):
        self.runtime.register_dependency(self.ctx, "rates", "wacc"); self.runtime.register_dependency(self.ctx, "wacc", "valuation"); self.runtime.restart(self.ctx.tenant_id); r = self.runtime.process(self.ctx, self._event()); self.assertIn("valuation", r["result"]["impacted_subjects"])
    def test_claim_survives_restart(self):
        c = Claim("rates", "policy_rate", 9.0, EvidenceStatus.VERIFIED, [EvidenceRef("cb", "release", "rate")], InformationClass.PUBLIC, Domain.PUBLIC_MARKETS, 0.99)
        self.runtime.process(self.ctx, self._event(), [c]); self.runtime.restart(self.ctx.tenant_id); claims = self.runtime.autopilot(self.ctx.tenant_id).graph.current_claims("rates", "policy_rate"); self.assertEqual(len(claims), 1); self.assertEqual(claims[0].value, 9.0)
    def test_health_reports_durable_integrity(self):
        self.runtime.process(self.ctx, self._event()); h = self.runtime.health(self.ctx.tenant_id); self.assertTrue(h["database_quick_check"]); self.assertTrue(h["learning_chain_valid"]); self.assertEqual(h["event_count"], 1)
    def test_second_tenant_cannot_see_first_tenant_state(self):
        self.runtime.process(self.ctx, self._event()); self.assertEqual(self.runtime.health("tenant-b")["event_count"], 0)
    def test_restricted_security_denied_even_for_public_data(self):
        self.runtime.restrictions.add(RestrictedEntry("tenant-a", "deal involvement", issuer_id="ISSUER1"))
        action = ActionRequest("PAPER_SIGNAL", Domain.PUBLIC_MARKETS, Domain.PUBLIC_MARKETS, InformationClass.PUBLIC, context={"issuer_id":"ISSUER1"})
        d = self.runtime.process(self.ctx, self._event(), actions=[action])["result"]["action_decisions"][0]
        self.assertEqual(d["disposition"], ActionDisposition.DENY.value); self.assertIn("RESTRICTED_LIST_MATCH", d["reason_codes"])


class RestrictedListTests(unittest.TestCase):
    def setUp(self): self.store = SqliteStateStore(":memory:"); self.reg = RestrictedListRegistry(self.store)
    def tearDown(self): self.store.close()
    def test_restriction_and_clear(self):
        e = self.reg.add(RestrictedEntry("t", "reason", security_id="SEC")); self.assertTrue(self.reg.is_restricted("t", security_id="SEC")); self.reg.clear("t", e.restriction_id); self.assertFalse(self.reg.is_restricted("t", security_id="SEC"))
    def test_restriction_is_tenant_scoped(self):
        self.reg.add(RestrictedEntry("t1", "reason", issuer_id="I")); self.assertTrue(self.reg.is_restricted("t1", issuer_id="I")); self.assertFalse(self.reg.is_restricted("t2", issuer_id="I"))
    def test_entry_requires_identifier(self):
        with self.assertRaises(ValueError): self.reg.add(RestrictedEntry("t", "reason"))


class PassportTests(unittest.TestCase):
    def setUp(self): self.issuer = DealPassportIssuer(); self.ctx=TenantContext("t1","u1")
    def test_passport_integrity_and_missing(self):
        c = Claim("co", "revenue", 10, EvidenceStatus.VERIFIED, [EvidenceRef("s","doc","p")], InformationClass.CONFIDENTIAL, Domain.PRIVATE_MNA, 0.95)
        p = self.issuer.issue(self.ctx, "co", [c], ["revenue","ownership"]); self.assertTrue(p.validate_integrity()); self.assertEqual(p.missing_predicates, ("ownership",)); self.assertLess(p.readiness_score, 1)
    def test_passport_detects_stale_evidence(self):
        old=(datetime.now(timezone.utc)-timedelta(days=400)).isoformat(); c=Claim("co","revenue",10,EvidenceStatus.VERIFIED,[EvidenceRef("s","doc","p",observed_at=old)],InformationClass.CONFIDENTIAL,Domain.PRIVATE_MNA,0.95)
        self.assertTrue(self.issuer.issue(self.ctx,"co",[c],["revenue"],{"revenue":90}).facts[0].stale)
    def test_passport_detects_conflict(self):
        ref=EvidenceRef("s","doc","p"); a=Claim("co","employees",10,EvidenceStatus.VERIFIED,[ref],InformationClass.CONFIDENTIAL,Domain.PRIVATE_MNA,0.9); b=Claim("co","employees",12,EvidenceStatus.CORROBORATED,[ref],InformationClass.CONFIDENTIAL,Domain.PRIVATE_MNA,0.9)
        p=self.issuer.issue(self.ctx,"co",[a,b],["employees"]); self.assertIn("employees",p.conflicting_predicates); self.assertLess(p.readiness_score,1)
    def test_tampered_passport_fails_integrity(self):
        c=Claim("co","revenue",10,EvidenceStatus.VERIFIED,[EvidenceRef("s","doc","p")],InformationClass.CONFIDENTIAL,Domain.PRIVATE_MNA,0.95); p=self.issuer.issue(self.ctx,"co",[c],["revenue"]); self.assertFalse(replace(p,readiness_score=0.01).validate_integrity())


class OutcomeNetTests(unittest.TestCase):
    def setUp(self): self.store=SqliteStateStore(":memory:"); self.net=OutcomeNet(self.store)
    def tearDown(self): self.store.close()
    def test_no_consent_blocks_recording(self):
        with self.assertRaises(PermissionError): self.net.record(OutcomeObservation("t","logistics","irr",0.2,0.1))
    def test_minimum_cohort_prevents_small_group_release(self):
        for i in range(4):
            t=f"t{i}"; self.net.set_consent(DataUseConsent(t,True,5)); self.net.record(OutcomeObservation(t,"logistics","irr",0.2,0.1))
        self.assertIsNone(self.net.aggregate("logistics","irr"))
    def test_aggregate_releases_after_unique_tenant_threshold(self):
        for i in range(5):
            t=f"t{i}"; self.net.set_consent(DataUseConsent(t,True,5)); self.net.record(OutcomeObservation(t,"logistics","irr",0.2+i*.01,0.1+i*.02))
        a=self.net.aggregate("logistics","irr"); self.assertIsNotNone(a); self.assertEqual(a.tenant_count,5); self.assertGreaterEqual(a.mean_absolute_error,0)
    def test_opt_out_is_respected(self):
        for i in range(5):
            t=f"t{i}"; self.net.set_consent(DataUseConsent(t,True,5)); self.net.record(OutcomeObservation(t,"x","m",1,1))
        self.net.set_consent(DataUseConsent("optout",False,5))
        with self.assertRaises(PermissionError): self.net.record(OutcomeObservation("optout","x","m",1,0))
        self.assertEqual(self.net.aggregate("x","m").tenant_count,5)
    def test_aggregate_bounds_each_tenant_contribution(self):
        for i in range(5):
            t=f"w{i}"; self.net.set_consent(DataUseConsent(t,True,5)); self.net.record(OutcomeObservation(t,"weighted","m",0,0))
        for _ in range(20): self.net.record(OutcomeObservation("w0","weighted","m",1,1))
        a=self.net.aggregate("weighted","m"); self.assertEqual(a.tenant_count,5); self.assertEqual(a.observation_count,25); self.assertLess(a.mean_actual,0.25)
    def test_tenant_observation_view_is_scoped(self):
        for t in ("a","b"):
            self.net.set_consent(DataUseConsent(t,True,5)); self.net.record(OutcomeObservation(t,"c","m",1,1))
        self.assertEqual(len(self.net.tenant_observations("a")),1); self.assertEqual(self.net.tenant_observations("a")[0].tenant_id,"a")


class DecisionAlgorithmTests(unittest.TestCase):
    def test_freshness_risk_zero_before_sla(self): self.assertEqual(EvidenceFreshnessRisk().score(10,30,1),0)
    def test_freshness_risk_rises_after_sla(self): self.assertGreater(EvidenceFreshnessRisk().score(120,30,1),0.5)
    def test_assumption_criticality_ranks_high_sensitivity_uncertainty_first(self): self.assertEqual(AssumptionCriticalityRanker().rank([AssumptionSignal("a",1,1,0.1),AssumptionSignal("b",0.2,0.2,0.9)])[0][0],"a")
    def test_thesis_decay_weights_broken_assumptions(self): self.assertGreater(ThesisDecayIndex().score(stale_evidence=0,adverse_signals=0,broken_assumptions=1,unresolved_critical=0),0.3)
    def test_sunk_cost_does_not_rescue_negative_forward_margin(self): self.assertEqual(DealSunkCostBiasGuard().evaluate(sunk_cost=1000,future_expected_value=10,future_required_cost=20)["decision"],"STOP_OR_RESTRUCTURE")
    def test_information_value_prioritizes_high_impact_low_cost(self): self.assertEqual(InformationValuePrioritizer().rank([InformationQuestion("q2",0.4,0.4,0.5,0.8,0.8),InformationQuestion("q1",1,1,1,0.1,0.1)])[0][0],"q1")
    def test_synergy_double_count_detects_overlapping_same_pool(self): self.assertEqual(len(SynergyDoubleCountDetector().detect([SynergyItem("a",10,frozenset({"headcount","shared-service"}),"opex"),SynergyItem("b",8,frozenset({"headcount","shared-service"}),"opex")])),1)
    def test_synergy_different_pool_not_flagged(self): self.assertEqual(SynergyDoubleCountDetector().detect([SynergyItem("a",10,frozenset({"x"}),"opex"),SynergyItem("b",8,frozenset({"x"}),"revenue")]),[])
    def test_regime_vector_sums_driver_impacts(self): self.assertAlmostEqual(RegimeSensitivityVector().impact({"rates":-2,"fx":3},{"rates":0.1,"fx":0.2})["TOTAL"],0.4)
    def test_no_deal_can_dominate(self): self.assertEqual(NoDealDominanceTest().evaluate(90,100)["decision"],"NO_DEAL_OR_ALTERNATIVE_DOMINATES")
    def test_brier_score_perfect_is_zero(self): self.assertEqual(OutcomeCalibrationScore().brier_score([0,1],[0,1]),0)


class FailureGenomeTests(unittest.TestCase):
    def setUp(self): self.c=FailureToRouteGeneCompiler()
    def test_sheet_grid_failure_gene(self): self.assertEqual(self.c.compile("range exceeds grid limits").classification,"PROVIDER_GRID_BOUNDARY")
    def test_dns_failure_gene(self): self.assertEqual(self.c.compile("Could not resolve host github.com").smallest_safe_repair,"USE_AUTHENTICATED_CONNECTOR_ROUTE")
    def test_workflow_default_deny_gene(self): self.assertEqual(self.c.compile("default-deny admission blocked workflow").classification,"WORKFLOW_DEFAULT_DENY")
    def test_same_repo_pr_metadata_gene(self): self.assertEqual(self.c.compile("Fork collab can only be enabled on cross-repo pull requests").classification,"SAME_REPO_PR_METADATA_CONTRACT")
    def test_unknown_failure_does_not_repeat_route(self): self.assertEqual(self.c.compile("strange failure").classification,"UNCLASSIFIED")

if __name__ == "__main__": unittest.main()
