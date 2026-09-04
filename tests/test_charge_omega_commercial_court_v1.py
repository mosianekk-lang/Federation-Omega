import unittest
from benchmarking.cfbe_omega.charge_omega_commercial_court_v1 import *


class CommercialCourtTests(unittest.TestCase):
    def c(self, **kw):
        d = dict(
            capability_id="CAP1",
            canonical_name="Persistent browser identity",
            outcome="authenticated browser continuity",
            official_sources=("official://provider-doc",),
            commercial_or_gated=True,
            provider_native_edge=True,
            estimated_monthly_cost=100.0,
            lock_in=0.2,
            privacy_risk=0.2,
            regulatory_risk=0.1,
        )
        d.update(kw)
        return CommercialCapability(**d)

    def a(self, **kw):
        d = dict(
            capability_id="FED1",
            existing_fit=0.5,
            open_fit=0.4,
            compose_fit=0.4,
            build_feasibility=0.5,
            proof_strength=0.7,
            operational_strength=0.5,
            provider_native_strength=0.8,
            exit_path_strength=0.8,
        )
        d.update(kw)
        return FederationAlternative(**d)

    def h(self, **kw):
        d = dict(
            candidate_id="CAP1",
            state="GENE_FORMED",
            blockers=(),
            completed_stage_count=14,
            independent_source_groups=3,
            source_family_count=6,
            receiver_adoption_authorized=False,
            provider_effect_authorized=False,
        )
        d.update(kw)
        return HarvestQualification(**d)

    def trial(self, **kw):
        d = dict(
            capability_id="CAP1",
            open_and_internal_alternatives_exhausted=True,
            provider_native_readback=True,
            exit_path_proven=True,
            cost_observed=True,
            evidence_refs=("proof://1",),
        )
        d.update(kw)
        return CommercialTrialReceipt(**d)

    def test_harvest_open_holds(self):
        h = self.h(state="HARVEST_OPEN", blockers=("NEGATIVE_EVIDENCE_REQUIRED",))
        self.assertEqual(CommercialRoute.HOLD, CommercialCourt().decide(self.c(), self.a(), h).route)

    def test_provider_authority_cannot_inherit(self):
        self.assertEqual(
            CommercialRoute.HOLD,
            CommercialCourt().decide(self.c(), self.a(), self.h(provider_effect_authorized=True)).route,
        )

    def test_identity_mismatch_holds(self):
        self.assertEqual(
            CommercialRoute.HOLD,
            CommercialCourt().decide(self.c(), self.a(), self.h(candidate_id="OTHER")).route,
        )

    def test_noncommercial_exits_commercial_lane(self):
        d = CommercialCourt().decide(self.c(commercial_or_gated=False), self.a(), self.h())
        self.assertEqual(CommercialRoute.REUSE, d.route)
        self.assertFalse(d.purchase_authorized)

    def test_reuse_first(self):
        self.assertEqual(CommercialRoute.REUSE, CommercialCourt().decide(self.c(), self.a(existing_fit=0.9), self.h()).route)

    def test_open_before_build(self):
        self.assertEqual(
            CommercialRoute.OPEN_SUBSTITUTE,
            CommercialCourt().decide(self.c(provider_native_edge=False), self.a(open_fit=0.85), self.h()).route,
        )

    def test_compose_before_build(self):
        self.assertEqual(
            CommercialRoute.COMPOSE,
            CommercialCourt().decide(self.c(provider_native_edge=False), self.a(compose_fit=0.8), self.h()).route,
        )

    def test_extend_before_new_build(self):
        self.assertEqual(
            CommercialRoute.EXTEND,
            CommercialCourt().decide(self.c(provider_native_edge=False), self.a(existing_fit=0.7), self.h()).route,
        )

    def test_build_provider_neutral(self):
        alt = self.a(existing_fit=0.2, open_fit=0.2, compose_fit=0.2, build_feasibility=0.8)
        self.assertEqual(CommercialRoute.BUILD, CommercialCourt().decide(self.c(provider_native_edge=False), alt, self.h()).route)

    def test_provider_native_edge_is_trial_not_buy(self):
        d = CommercialCourt().decide(self.c(), self.a(), self.h())
        self.assertEqual(CommercialRoute.TRIAL, d.route)
        self.assertFalse(d.purchase_candidate)
        self.assertFalse(d.purchase_authorized)

    def test_high_risk_rejects(self):
        c = self.c(lock_in=0.95, privacy_risk=0.95, regulatory_risk=0.95)
        self.assertEqual(CommercialRoute.REJECT, CommercialCourt().decide(c, self.a(), self.h()).route)

    def test_post_trial_requires_omega_harvest_h9(self):
        d = CommercialCourt().after_trial(self.c(), self.a(), self.h(state="CANDIDATE_EXECUTABLE"), self.trial())
        self.assertEqual(CommercialRoute.HOLD, d.route)
        self.assertIn("omega_harvest_h9_or_h10_required", d.reasons)

    def test_post_trial_requires_commercial_exit_cost_readback(self):
        h = self.h(state="EMPIRICAL_ADVANTAGE_PROVEN")
        d = CommercialCourt().after_trial(self.c(), self.a(), h, self.trial(exit_path_proven=False, cost_observed=False))
        self.assertEqual(CommercialRoute.HOLD, d.route)
        self.assertIn("exit_path_missing", d.reasons)
        self.assertIn("cost_not_observed", d.reasons)

    def test_post_trial_candidate_never_authorizes(self):
        h = self.h(state="EMPIRICAL_ADVANTAGE_PROVEN")
        d = CommercialCourt().after_trial(self.c(), self.a(), h, self.trial())
        self.assertTrue(d.purchase_candidate)
        self.assertFalse(d.purchase_authorized)

    def test_receipt_overwrites_purchase_authority_false(self):
        d = CommercialCourt().after_trial(self.c(), self.a(), self.h(state="VALUE_PROVEN"), self.trial())
        r = decision_receipt(d)
        self.assertFalse(r["purchase_authorized"])
        self.assertEqual(64, len(r["sha256"]))


if __name__ == "__main__":
    unittest.main()
