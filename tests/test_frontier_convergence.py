import unittest
from datetime import datetime, timedelta, timezone

from frontier_convergence.core import (
    ActionMode, AgentIdentityContract, AIAssetRecord, AIControlTower, AssetKind,
    AuthorizationRequest, BudgetLease, CapabilityLease, ConnectorIntentGuard,
    ConvergenceStage, EffectContract, ExperimentIdentityCompiler, FinOpsParetoRouter,
    FrontierConvergenceEngine, FrontierSignal, PrivacyEnvelope, ProofLevel,
    ProvenanceAttestation, RobustnessCourt, RobustnessObservation, ScenarioBranch,
    SchemaCompatibilityHandshake, SQLiteConvergenceStore, ValueReceipt, PolicyDecisionPoint,
)
from frontier_convergence.gemini_adapter import GeminiAdapter


def t(hours=0):
    return (datetime(2026, 8, 27, 12, tzinfo=timezone.utc) + timedelta(hours=hours)).isoformat()


class FrontierConvergenceTests(unittest.TestCase):
    def test_signal_is_deterministic_and_evidence_bound(self):
        a = FrontierSignal.create(source_organization="Google", capability_class="agent identity",
                                  mechanism="short lived workload identity", evidence_refs=["official-doc"], observed_at=t())
        b = FrontierSignal.create(source_organization="Google", capability_class="agent identity",
                                  mechanism="short lived workload identity", evidence_refs=["official-doc"], observed_at=t())
        self.assertEqual(a.signal_id, b.signal_id)
        with self.assertRaises(ValueError):
            FrontierSignal.create(source_organization="Google", capability_class="x", mechanism="y", evidence_refs=[])

    def test_candidate_requires_one_capability_class(self):
        a = FrontierSignal.create(source_organization="A", capability_class="identity", mechanism="m1", evidence_refs=["e"], observed_at=t())
        b = FrontierSignal.create(source_organization="B", capability_class="identity", mechanism="m2", evidence_refs=["e"], observed_at=t())
        c = FrontierConvergenceEngine().form_candidate(signals=[a,b], incumbent_capability_id="INC-1",
                                                        architecture="provider-neutral identity facade",
                                                        provider_dependencies=["google"], expected_metric_names=["auth_latency"])
        self.assertTrue(c.provider_neutral_core)
        bad = FrontierSignal.create(source_organization="C", capability_class="gateway", mechanism="m3", evidence_refs=["e"], observed_at=t())
        with self.assertRaises(ValueError):
            FrontierConvergenceEngine().form_candidate(signals=[a,bad], incumbent_capability_id="INC", architecture="x")

    def test_experiment_identity_changes_on_environment(self):
        base = dict(implementation_sha256="a"*64, source_sha256="b"*64, inputs={"x":1},
                    observation_window="2026-08-27", parameters={"p":1},
                    cost_latency_context={"cost":0}, controls={"holdout":True}, authority={"ceiling":"A1"})
        x = ExperimentIdentityCompiler.compile(environment={"runtime":"r1"}, **base)
        y = ExperimentIdentityCompiler.compile(environment={"runtime":"r2"}, **base)
        self.assertNotEqual(x.fingerprint, y.fingerprint)

    def test_capability_lease_is_receiver_local_and_expires(self):
        lease = CapabilityLease.issue(capability_id="C1", receiver_id="R1", proof_level=ProofLevel.CANARY,
                                      proven_at=t(), expires_at=t(2), evidence_refs=["p"])
        self.assertFalse(lease.cross_receiver_inheritance)
        self.assertTrue(lease.valid_at(t(1)))
        self.assertFalse(lease.valid_at(t(3)))

    def test_identity_is_scoped_and_expiring(self):
        identity = AgentIdentityContract.issue(agent_id="gemini-critic", trust_domain="fed.local", provider="google",
                                               subject_ref="provider-subject-ref", authority_ceiling="A1_INTERNAL",
                                               allowed_actions=["read"], allowed_resource_prefixes=["drive://safe/"],
                                               issued_at=t(), expires_at=t(1), evidence_refs=["identity-proof"])
        self.assertTrue(identity.authorizes(action="read", resource="drive://safe/x", at=t(.5)))
        self.assertFalse(identity.authorizes(action="write", resource="drive://safe/x", at=t(.5)))
        self.assertFalse(identity.authorizes(action="read", resource="drive://safe/x", at=t(2)))

    def test_policy_decision_point_default_denies_mutation_above_a1(self):
        identity = AgentIdentityContract.issue(agent_id="a", trust_domain="fed", provider="google", subject_ref="sub",
                                               authority_ceiling="A1_INTERNAL", allowed_actions=["write"],
                                               allowed_resource_prefixes=["drive://"], issued_at=t(), expires_at=t(2),
                                               evidence_refs=["p"])
        req = AuthorizationRequest(principal_id=identity.identity_id, action="write", resource="drive://x")
        dec = PolicyDecisionPoint().decide(request=req, identity=identity, at=t(1), effect_mode=ActionMode.MUTATE)
        self.assertFalse(dec.allowed)
        dec2 = PolicyDecisionPoint().decide(request=req, identity=identity, at=t(1), effect_mode=ActionMode.MUTATE,
                                            owner_gate_satisfied=True)
        self.assertTrue(dec2.allowed)

    def test_privacy_envelope_minimizes_payload(self):
        env = PrivacyEnvelope.create(data_classification="internal", permitted_fields=["title","summary"],
                                     prohibited_fields=["summary"])
        self.assertEqual(env.filter_payload({"title":"x","summary":"y","secretish":"z"}), {"title":"x"})

    def test_secret_field_is_rejected(self):
        with self.assertRaises(ValueError):
            EffectContract.create(mission_id="M", target="x", action="read", parameters={"api_key":"nope"},
                                  mode=ActionMode.READ, authority_class="A0", expected_semantic_result="readback",
                                  readback_plan=["get"], rollback_plan=[])

    def test_mutation_effect_requires_rollback(self):
        with self.assertRaises(ValueError):
            EffectContract.create(mission_id="M", target="x", action="write", parameters={"v":1},
                                  mode=ActionMode.MUTATE, authority_class="A2", expected_semantic_result="changed",
                                  readback_plan=["get"], rollback_plan=[])
        eff = EffectContract.create(mission_id="M", target="x", action="write", parameters={"v":1},
                                    mode=ActionMode.MUTATE, authority_class="A2", expected_semantic_result="changed",
                                    readback_plan=["get"], rollback_plan=["restore"])
        self.assertTrue(eff.idempotency_key.startswith("FC-IDEMP-"))

    def test_scenario_is_branch_only_and_diffable(self):
        s = ScenarioBranch.create(mission_id="M", base_state={"a":1,"b":2}, delta={"b":3,"c":4})
        self.assertEqual(s.materialized(), {"a":1,"b":3,"c":4})
        self.assertEqual(s.base_state, {"a":1,"b":2})
        self.assertIn("b", s.diff())

    def test_schema_handshake(self):
        hs = SchemaCompatibilityHandshake.create(contract_name="MIC", producer_version="1.0",
                                                 consumer_versions=["1.0","1.1"], required_fields=["mission_id"])
        self.assertTrue(hs.compatible("1.1", {"mission_id":"M"}))
        self.assertFalse(hs.compatible("2.0", {"mission_id":"M"}))

    def test_budget_lease_fails_closed_for_positive_unapproved_spend(self):
        b = BudgetLease.create(currency="ZAR", max_cost=5, expires_at=t(2), provider_allowlist=["google"], owner_approved=False)
        self.assertFalse(b.can_spend(amount=1, provider="google", at=t(1)))
        z = BudgetLease.create(currency="ZAR", max_cost=0, expires_at=t(2), provider_allowlist=["google"])
        self.assertTrue(z.can_spend(amount=0, provider="google", at=t(1)))

    def test_store_event_chain_and_idempotency(self):
        store = SQLiteConvergenceStore()
        a = store.append_event(object_id="O", event_type="E", payload={"x":1}, idempotency_key="k")
        b = store.append_event(object_id="O", event_type="E", payload={"x":1}, idempotency_key="k")
        self.assertEqual(a["event_id"], b["event_id"])
        self.assertTrue(store.verify_event_chain())
        self.assertEqual(store.reserve_idempotency(key="K", payload={"x":1}), "RESERVED")
        self.assertEqual(store.reserve_idempotency(key="K", payload={"x":1}), "EXISTS")
        with self.assertRaises(ValueError):
            store.reserve_idempotency(key="K", payload={"x":2})

    def test_connector_intent_guard_blocks_read_mutation_confusion(self):
        guard = ConnectorIntentGuard(SQLiteConvergenceStore())
        with self.assertRaises(ValueError):
            guard.preflight(declared_mode=ActionMode.READ, callable_mode=ActionMode.MUTATE,
                            idempotency_key="k", payload={"op":"read"})
        self.assertEqual(guard.preflight(declared_mode=ActionMode.READ, callable_mode=ActionMode.READ,
                                         idempotency_key="k2", payload={"op":"read"}), "RESERVED")

    def test_control_tower_marks_expired_assets(self):
        store = SQLiteConvergenceStore()
        tower = AIControlTower(store)
        a = AIAssetRecord.create(kind=AssetKind.MODEL, name="Gemini", provider="google", owner_ref="owner",
                                 purpose="reasoning", lifecycle_state="ACTIVE", authority_ceiling="A1",
                                 proof_level=ProofLevel.DETERMINISTIC, proof_refs=["p"], observed_at=t(), expires_at=t(1))
        tower.register(a)
        inv = tower.inventory(at=t(2))
        self.assertFalse(inv[0]["fresh"])

    def test_pareto_router_keeps_non_dominated(self):
        a = ValueReceipt.create(candidate_id="A", quality=.9, reliability=.9, latency_ms=100, cost=1,
                                owner_burden=.2, outcome_value=.8, evidence_refs=["p"])
        b = ValueReceipt.create(candidate_id="B", quality=.9, reliability=.9, latency_ms=200, cost=2,
                                owner_burden=.3, outcome_value=.7, evidence_refs=["p"])
        front = FinOpsParetoRouter.pareto_front([a,b], minimum_quality=.8, minimum_reliability=.8)
        self.assertEqual([x.candidate_id for x in front], ["A"])

    def test_provenance_attestation_binds_materials_and_environment(self):
        p = ProvenanceAttestation.create(subject_name="pkg", subject_sha256="a"*64, source_uri="git://repo",
                                         source_revision="abc", builder_id="github-actions",
                                         materials={"src":"b"*64}, build_parameters={"opt":1},
                                         environment={"python":"3.12"}, generated_at=t())
        self.assertTrue(p.attestation_id.startswith("FC-PROV-"))

    def test_robustness_court_requires_all_gates_and_evidence(self):
        obs = [RobustnessObservation(gate=g, passed=True, evidence_refs=("p",))
               for g in RobustnessCourt.MANDATORY_GATES]
        self.assertTrue(RobustnessCourt.evaluate(obs).passed)
        self.assertFalse(RobustnessCourt.evaluate(obs[:-1]).passed)
        with self.assertRaises(ValueError):
            RobustnessCourt.evaluate([RobustnessObservation(gate="HOLDOUT", passed=True, evidence_refs=())])

    def test_adoption_fails_closed_without_provider_readback(self):
        sig = FrontierSignal.create(source_organization="Google", capability_class="identity", mechanism="workload identity",
                                    evidence_refs=["doc"], observed_at=t())
        engine = FrontierConvergenceEngine()
        cand = engine.form_candidate(signals=[sig], incumbent_capability_id="INC", architecture="identity facade",
                                     provider_dependencies=["google"], expected_metric_names=["quality"])
        robust = RobustnessCourt.evaluate([RobustnessObservation(gate=g, passed=True, evidence_refs=("p",))
                                           for g in RobustnessCourt.MANDATORY_GATES])
        value = ValueReceipt.create(candidate_id=cand.candidate_id, quality=.9, reliability=.9, latency_ms=100,
                                    cost=0, owner_burden=.1, outcome_value=.9, evidence_refs=["value"])
        exp = ExperimentIdentityCompiler.compile(implementation_sha256="a"*64, source_sha256="b"*64,
                                                 inputs={"x":1}, environment={"r":"1"}, observation_window="w",
                                                 parameters={}, cost_latency_context={}, controls={}, authority={"c":"A1"})
        r = engine.admission(candidate=cand, stage=ConvergenceStage.ADOPTED, robustness=robust,
                             independent_quorum_outcome="ADMIT", value_receipt=value, rollback_proof_ref="rb",
                             provider_readback_refs=[], experiment_identity=exp)
        self.assertEqual(r.decision, "HOLD")
        self.assertIn("PROVIDER_READBACK_REQUIRED", r.blockers)
        r2 = engine.admission(candidate=cand, stage=ConvergenceStage.ADOPTED, robustness=robust,
                              independent_quorum_outcome="ADMIT", value_receipt=value, rollback_proof_ref="rb",
                              provider_readback_refs=["google-readback"], experiment_identity=exp)
        self.assertEqual(r2.decision, "ADMIT")

    def test_stage_canary_does_not_inherit_adoption_requirements(self):
        sig = FrontierSignal.create(source_organization="A", capability_class="x", mechanism="m", evidence_refs=["e"], observed_at=t())
        eng = FrontierConvergenceEngine()
        cand = eng.form_candidate(signals=[sig], incumbent_capability_id="i", architecture="a")
        robust = RobustnessCourt.evaluate([RobustnessObservation(gate=g, passed=True, evidence_refs=("p",))
                                           for g in RobustnessCourt.MANDATORY_GATES])
        r = eng.admission(candidate=cand, stage=ConvergenceStage.CANARY, robustness=robust,
                          independent_quorum_outcome="HELD", value_receipt=None, rollback_proof_ref=None)
        self.assertEqual(r.decision, "ADMIT")

    def test_observe_is_deduplicated(self):
        sig = FrontierSignal.create(source_organization="A", capability_class="x", mechanism="m", evidence_refs=["e"], observed_at=t())
        eng = FrontierConvergenceEngine()
        first = eng.observe(sig)
        second = eng.observe(sig)
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertTrue(eng.store.verify_event_chain())


class GeminiAdapterTests(unittest.TestCase):
    def test_call_plan_uses_reference_not_secret(self):
        env = PrivacyEnvelope.create(data_classification="internal", permitted_fields=["prompt"])
        plan = GeminiAdapter.compile_call(mission_id="M", model_ref="gemini-current",
                                          contents={"prompt":"hello","private":"drop"},
                                          credential_reference="GEMINI_API_KEY",
                                          privacy_envelope=env, tool_allowlist=["search"])
        self.assertEqual(plan.credential_reference, "GEMINI_API_KEY")
        self.assertEqual(plan.request_body["contents"], {"prompt":"hello"})
        self.assertTrue(plan.provider_authority_required)

    def test_gemini_readback_is_fail_closed(self):
        plan = GeminiAdapter.compile_call(mission_id="M", model_ref="gemini-current", contents="hello")
        ok, missing = GeminiAdapter.validate_readback(plan, {"provider_request_id":"r"})
        self.assertFalse(ok)
        self.assertIn("model_identity", missing)
        complete = {field: "x" for field in plan.required_readback_fields}
        ok2, missing2 = GeminiAdapter.validate_readback(plan, complete)
        self.assertTrue(ok2)
        self.assertEqual(missing2, ())


if __name__ == "__main__":
    unittest.main()
