import json
import unittest
from dataclasses import replace

from federation.fkcm_v1 import (
    Authority, ConvergenceCourt, ConvergenceError, DependencyEdge, Effect, EventEnvelope,
    ModisaKdvConvergenceKernel, Privacy, ProofDimensions, RelationFact, SourceLease,
    StateCompiler, StateFact, Subscription, TruthClass, WritePlan, compare_bmf_dual_run, from_bmf_row, from_cloudevent,
    kim_id, to_gen2_event_row,
)

NOW = "2026-09-04T21:40:00+02:00"
MAIN = "36616e18886bc7ebb0e6e1c4688254b0b4c1691e"
OLD_MAIN = "262a57f22916de53a17bab1c02287894c524558d"
ENTITY_MAIN = "ENTITY-FEDERATION-OMEGA-MAIN"


def source_event(event_id="evt-main", sha=MAIN, effect=Effect.NONE):
    return EventEnvelope(
        event_id=event_id,
        event_type="SOURCE_FRONTIER_OBSERVED",
        entity_id=ENTITY_MAIN,
        source_surface="GITHUB",
        source_key="refs/heads/main",
        event_time=NOW,
        observed_time=NOW,
        valid_from=NOW,
        payload={
            "current_sha": sha,
            "fields": {"current_sha": sha},
            "fresh_until": "LEASE_RENEW_ON_QUERY",
            "proof_epoch": "PE-FKCM-SHADOW-1",
            "proof_dimensions": {
                "source": "PROVEN", "runtime": "UNASSESSED", "provider": "PROVEN_READ",
                "behavior": "UNASSESSED", "value": "UNASSESSED", "authority": "READ_AUTHORITY", "effect": "NONE",
            },
        },
        proof_refs=(f"github:main:{sha}",),
        authority=Authority.A1,
        effect=effect,
        truth_class=TruthClass.SOURCE_TRUTH,
        privacy=Privacy.PUBLIC_SAFE,
        transaction_id=f"idem-{sha}",
        topic="sync.delta.v1",
    )


class IdentityTests(unittest.TestCase):
    def test_kim_id_deterministic(self):
        self.assertEqual(kim_id("document", "abc"), kim_id("document", "abc"))

    def test_kim_id_changes_by_namespace(self):
        self.assertNotEqual(kim_id("document", "abc", "legal"), kim_id("document", "abc", "estate"))


class AdapterTests(unittest.TestCase):
    def test_gen2_projection_shape(self):
        row = to_gen2_event_row(source_event())
        self.assertEqual(row["Entity_ID"], ENTITY_MAIN)
        self.assertTrue(str(row["Payload_Hash"]).startswith("sha256:"))

    def test_bmf_normalization(self):
        row = {
            "event_id": "bmf-1", "stream_id": "mission:ABC", "stream_version": "1", "event_type": "STATE_SET",
            "recorded_at": NOW, "valid_at": NOW, "idempotency_key": "id-1", "truth_class": "EVENT_TRUTH",
            "privacy_class": "PUBLIC_SAFE", "payload_json": json.dumps({"fields": {"mission_state": "SUCCESS"}}),
            "source_refs_json": json.dumps(["github:main/x"]), "directive_id": "D1", "mission_id": "ABC",
            "workstream_id": "WS", "supersedes_json": "[]", "proof_refs_json": "[]",
            "causal_parent_ids_json": "[]", "contradicts_json": "[]", "schema_version": "1",
            "provider_persisted_at_sast": NOW,
        }
        event = from_bmf_row(row)
        self.assertEqual(event.event_id, "bmf-1")
        self.assertIn("github:main/x", event.proof_refs)
        self.assertTrue(event.entity_id.startswith("kim://federation/bmf-stream/"))
        self.assertEqual(event.source_sequence, 1)
        self.assertEqual(event.lineage["mission_id"], "ABC")

    def test_cloudevent_normalization(self):
        ce = {"specversion": "1.0", "id": "ce-1", "source": "sovara://github", "type": "com.sovara.state",
              "time": NOW, "data": {"entity_id": ENTITY_MAIN, "source_key": "main", "fields": {"x": 1}}}
        event = from_cloudevent(ce, topic="sync.delta.v1")
        self.assertEqual(event.entity_id, ENTITY_MAIN)


class BmfDualRunTests(unittest.TestCase):
    def _row(self, version, event_type, payload, *, stream="workstream:test", event_id=None, directive="D1", mission="M1", supersedes=()):
        return {
            "event_id": event_id or f"bmf-{version}",
            "stream_id": stream,
            "stream_version": str(version),
            "event_type": event_type,
            "recorded_at": f"2026-09-04T20:00:0{version}Z",
            "valid_at": f"2026-09-04T20:00:0{version}Z",
            "idempotency_key": f"idem-{stream}-{version}",
            "truth_class": "EVENT_TRUTH",
            "privacy_class": "PUBLIC_SAFE",
            "payload_json": json.dumps(payload),
            "source_refs_json": json.dumps([f"source:{version}"]),
            "directive_id": directive,
            "mission_id": mission,
            "workstream_id": "WS",
            "supersedes_json": json.dumps(list(supersedes)),
            "proof_refs_json": "[]",
            "causal_parent_ids_json": "[]",
            "contradicts_json": "[]",
            "schema_version": "1",
            "provider_persisted_at_sast": NOW,
        }

    def test_all_bmf_projection_event_types_reproduce_state(self):
        rows = [
            self._row(1, "STATE_SET", {"a": 1, "remove": "x"}, directive="D1"),
            self._row(2, "DECISION_ACCEPTED", {"decision": "yes"}, directive="D2", supersedes=("old-event",)),
            self._row(3, "RESULT_VERIFIED", {"a": 2}, directive=""),
            self._row(4, "BLOCKER_SET", {"blocker": "held"}, directive=""),
            self._row(5, "NEXT_ACTION_SET", {"next": "go"}, directive=""),
            self._row(6, "STATE_UNSET", {"keys": ["remove", "blocker"]}, directive=""),
        ]
        events = [from_bmf_row(row) for row in rows]
        expected = {
            "workstream:test": {
                "event_count": 6,
                "current": {"a": 2, "decision": "yes", "next": "go"},
                "directive_ids": ("D1", "D2"),
                "mission_ids": ("M1",),
                "superseded_event_ids": ("old-event",),
            }
        }
        receipt = compare_bmf_dual_run(events, expected, compiled_at=NOW)
        self.assertEqual(receipt.state, "PASS", receipt.mismatches)
        self.assertFalse(receipt.provider_effect)
        self.assertFalse(receipt.cutover_authorized)

    def test_stream_identity_prevents_same_mission_state_collision(self):
        a = from_bmf_row(self._row(1, "STATE_SET", {"x": "A"}, stream="stream:A", mission="M-SHARED", event_id="bmf-A-1"))
        b = from_bmf_row(self._row(1, "STATE_SET", {"x": "B"}, stream="stream:B", mission="M-SHARED", event_id="bmf-B-1"))
        self.assertNotEqual(a.entity_id, b.entity_id)
        expected = {
            "stream:A": {"event_count": 1, "current": {"x": "A"}, "directive_ids": ("D1",), "mission_ids": ("M-SHARED",), "superseded_event_ids": ()},
            "stream:B": {"event_count": 1, "current": {"x": "B"}, "directive_ids": ("D1",), "mission_ids": ("M-SHARED",), "superseded_event_ids": ()},
        }
        receipt = compare_bmf_dual_run([a, b], expected, compiled_at=NOW)
        self.assertEqual(receipt.state, "PASS", receipt.mismatches)


class StateCompilerTests(unittest.TestCase):
    def test_latest_source_frontier_replaces_prior_state_projection(self):
        prior = StateFact(ENTITY_MAIN, "current_sha", OLD_MAIN, "git_sha", "old", "GITHUB",
                          ProofDimensions(source="PROVEN", provider="PROVEN_READ", authority="READ_AUTHORITY"),
                          "LEASE_RENEW_ON_QUERY", "PE-OLD", "2026-08-30")
        compiler = StateCompiler()
        facts, _ = compiler.compile([source_event()], compiled_at=NOW, prior_state=[prior])
        fact = next(f for f in facts if f.key == (ENTITY_MAIN, "current_sha"))
        self.assertEqual(fact.typed_value, MAIN)

    def test_identical_duplicate_event_coalesces(self):
        compiler = StateCompiler()
        events = compiler.deduplicate_events([source_event(), source_event()])
        self.assertEqual(len(events), 1)

    def test_conflicting_duplicate_event_fails(self):
        compiler = StateCompiler()
        a = source_event("same", MAIN)
        b = source_event("same", OLD_MAIN)
        with self.assertRaises(ConvergenceError):
            compiler.deduplicate_events([a, b])

    def test_idempotency_conflict_fails(self):
        compiler = StateCompiler()
        a = source_event("a", MAIN)
        b = replace(a, event_id="b", payload={"fields": {"current_sha": OLD_MAIN}, "current_sha": OLD_MAIN})
        with self.assertRaises(ConvergenceError):
            compiler.deduplicate_events([a, b])

    def test_source_fact_does_not_inherit_runtime_maturity(self):
        facts, _ = StateCompiler().compile([source_event()], compiled_at=NOW)
        fact = facts[0]
        self.assertIn(fact.claim_ceiling, {"SOURCE_ONLY", "RUNTIME_ONLY"})
        self.assertNotEqual(fact.claim_ceiling, "VALUE_PROVEN")

    def test_query_lease_required(self):
        facts, _ = StateCompiler().compile([source_event()], compiled_at=NOW)
        served, holds = StateCompiler.serve_current(facts)
        self.assertEqual(len(served), 0)
        self.assertTrue(holds)

    def test_query_lease_accepts_exact_value(self):
        facts, _ = StateCompiler().compile([source_event()], compiled_at=NOW)
        lease = SourceLease(ENTITY_MAIN, "current_sha", MAIN, NOW, "GITHUB", f"github:main:{MAIN}")
        served, holds = StateCompiler.serve_current(facts, [lease])
        self.assertEqual(len(served), 1)
        self.assertFalse(holds)

    def test_wrong_lease_value_rejected(self):
        facts, _ = StateCompiler().compile([source_event()], compiled_at=NOW)
        lease = SourceLease(ENTITY_MAIN, "current_sha", OLD_MAIN, NOW, "GITHUB", "stale")
        served, holds = StateCompiler.serve_current(facts, [lease])
        self.assertEqual(len(served), 0)
        self.assertTrue(holds)

    def test_relation_assertion_compiles(self):
        rel_evt = EventEnvelope(
            event_id="rel-1", event_type="RELATION_ASSERTED", entity_id="ENTITY-A", source_surface="KDV",
            source_key="fixture", event_time=NOW, observed_time=NOW, valid_from=NOW,
            payload={"subject_entity_id": "ENTITY-A", "predicate": "DEPENDS_ON", "object_entity_id": "ENTITY-B",
                     "relation_id": "REL-AB"}, authority=Authority.A1, effect=Effect.NONE,
            truth_class=TruthClass.DERIVED_VERIFIED, privacy=Privacy.INTERNAL,
        )
        _, rels = StateCompiler().compile([rel_evt], compiled_at=NOW)
        self.assertEqual(rels[0].relation_id, "REL-AB")


class PolicyTests(unittest.TestCase):
    def test_effect_requires_a2(self):
        with self.assertRaises(ValueError):
            EventEnvelope(event_id="e", event_type="X", entity_id="x", source_surface="x", source_key="x",
                          event_time=NOW, observed_time=NOW, valid_from=NOW, payload={}, authority=Authority.A1,
                          effect=Effect.BOUNDED)

    def test_shadow_write_plan_cannot_mutate(self):
        plan = WritePlan("KDV", "rev1", (("A1", "x"),), mode="SHADOW_READ_ONLY")
        with self.assertRaises(ValueError):
            plan.validate()

    def test_cas_required(self):
        plan = WritePlan("KDV", "", (), mode="SHADOW_READ_ONLY")
        with self.assertRaises(ValueError):
            plan.validate()


class CourtTests(unittest.TestCase):
    def test_shadow_court_rejects_effect(self):
        event = EventEnvelope(event_id="eff", event_type="X", entity_id="ENTITY-A", source_surface="X", source_key="X",
                              event_time=NOW, observed_time=NOW, valid_from=NOW, payload={}, authority=Authority.A2,
                              effect=Effect.BOUNDED)
        receipt = ConvergenceCourt().evaluate(events=[event], facts=[], relations=[], entity_ids=["ENTITY-A"], shadow_mode=True)
        self.assertEqual(receipt.state, "FAIL")

    def test_court_holds_missing_fresh_lease(self):
        event = source_event()
        facts, _ = StateCompiler().compile([event], compiled_at=NOW)
        receipt = ConvergenceCourt().evaluate(events=[event], facts=facts, relations=[], entity_ids=[ENTITY_MAIN])
        self.assertEqual(receipt.state, "PASS_WITH_HOLDS")

    def test_court_passes_with_exact_lease(self):
        event = source_event()
        facts, _ = StateCompiler().compile([event], compiled_at=NOW)
        lease = SourceLease(ENTITY_MAIN, "current_sha", MAIN, NOW, "GITHUB", "proof")
        receipt = ConvergenceCourt().evaluate(events=[event], facts=facts, relations=[], entity_ids=[ENTITY_MAIN], leases=[lease])
        self.assertEqual(receipt.state, "PASS")

    def test_dangling_relation_fails(self):
        event = EventEnvelope(event_id="rel", event_type="RELATION_ASSERTED", entity_id="ENTITY-A", source_surface="KDV",
                              source_key="x", event_time=NOW, observed_time=NOW, valid_from=NOW,
                              payload={"subject_entity_id":"ENTITY-A","predicate":"LINKS","object_entity_id":"ENTITY-B"})
        _, relations = StateCompiler().compile([event], compiled_at=NOW)
        receipt = ConvergenceCourt().evaluate(events=[event], facts=[], relations=relations, entity_ids=["ENTITY-A"])
        self.assertEqual(receipt.state, "FAIL")

    def test_unpinned_proof_epoch_holds_promotion(self):
        event = source_event()
        fact = StateFact(ENTITY_MAIN, "x", "v", "str", event.event_id, "GITHUB", ProofDimensions(source="PROVEN"),
                         "CURRENT", "PE-BOOTSTRAP-UNPINNED", NOW)
        receipt = ConvergenceCourt().evaluate(events=[event], facts=[fact], relations=[], entity_ids=[ENTITY_MAIN],
                                              promotion_requested=True)
        self.assertEqual(receipt.state, "PASS_WITH_HOLDS")
        self.assertFalse(receipt.promotion_eligible)


class KernelTests(unittest.TestCase):
    def _kernel(self):
        edges = [
            DependencyEdge("E1", "GITHUB", "HOSTS_SOURCE_FOR", "FEDERATION"),
            DependencyEdge("E2", "FEDERATION", "CANONICAL_STATE_STORED_IN", "KDV"),
            DependencyEdge("E3", "SENTINEL", "WRITES_SURFACE_STATE_TO", "KDV"),
            DependencyEdge("E4", "CFBE", "MIRRORS_BENCHMARK_TO", "KDV"),
        ]
        subs = [
            Subscription("FEDERATION", frozenset({"sync.delta.v1"})),
            Subscription("KDV", frozenset({"sync.delta.v1"})),
            Subscription("SENTINEL", frozenset({"sync.delta.v1"})),
            Subscription("CFBE", frozenset({"learning.event.v1"})),
        ]
        return ModisaKdvConvergenceKernel(edges=edges, subscriptions=subs, max_capsule_chars=4000)

    def test_end_to_end_shadow_convergence(self):
        lease = SourceLease(ENTITY_MAIN, "current_sha", MAIN, NOW, "GITHUB", "proof")
        result = self._kernel().run_shadow(
            events=[source_event()], compiled_at=NOW, mission_id="MISSION-FKCM-001",
            objective="Converge Federation and KDV", source_frontier=f"main@{MAIN}",
            entity_ids=[ENTITY_MAIN], roots=["GITHUB"], capabilities=["MODISA_V3", "KDV-GEN2"], leases=[lease],
        )
        self.assertEqual(result.court.state, "PASS")
        self.assertEqual(result.capsule.completeness, "CURRENT_BOUNDED")
        self.assertTrue(result.receipt_sha256.startswith("sha256:"))
        self.assertGreaterEqual(len(result.dispatches), 2)

    def test_no_lease_keeps_capsule_honest(self):
        result = self._kernel().run_shadow(
            events=[source_event()], compiled_at=NOW, mission_id="MISSION-FKCM-001",
            objective="Converge Federation and KDV", source_frontier=f"main@{MAIN}",
            entity_ids=[ENTITY_MAIN], roots=["GITHUB"], capabilities=["MODISA_V3"],
        )
        self.assertEqual(result.capsule.completeness, "CURRENT_WITH_HOLDS")
        self.assertEqual(len(result.capsule.facts), 0)
        self.assertTrue(result.capsule.stale_holds)

    def test_context_budget_hard_caps(self):
        kernel = ModisaKdvConvergenceKernel(max_capsule_chars=700)
        events = []
        for i in range(20):
            events.append(EventEnvelope(event_id=f"e{i}", event_type="STATE_SET", entity_id=f"ENTITY-{i}", source_surface="KDV",
                                        source_key="x", event_time=NOW, observed_time=NOW, valid_from=NOW,
                                        payload={"fields": {"note": "x" * 120}, "fresh_until": "CURRENT"}))
        result = kernel.run_shadow(events=events, compiled_at=NOW, mission_id="M", objective="O", source_frontier="S",
                                   entity_ids=[f"ENTITY-{i}" for i in range(20)], roots=[])
        self.assertLessEqual(result.capsule.char_count, 700)

    def test_no_provider_effect_claim(self):
        lease = SourceLease(ENTITY_MAIN, "current_sha", MAIN, NOW, "GITHUB", "proof")
        result = self._kernel().run_shadow(events=[source_event()], compiled_at=NOW, mission_id="M", objective="O",
                                           source_frontier=MAIN, entity_ids=[ENTITY_MAIN], roots=["GITHUB"], leases=[lease])
        for dispatch in result.dispatches:
            self.assertEqual(dispatch["effect"], "NONE")


if __name__ == "__main__":
    unittest.main()

class RepositoryAdmissionTests(unittest.TestCase):
    def test_governance_declares_no_new_master(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        governance = json.loads((root / "governance/fkcm_v1_admission.json").read_text())
        self.assertFalse(governance["truth_boundary"]["new_master_created"])
        self.assertFalse(governance["truth_boundary"]["provider_effect"])

    def test_proofos_extension_maps_candidate_to_r4_core(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        extension = json.loads((root / "governance/proofos_omega_policy_extension_fkcm_v1.json").read_text())
        self.assertEqual(extension["schema"], "FEDERATION-PROOFOS-OMEGA-ADDITIVE-EXTENSION-V1")
        self.assertEqual(extension["risk_rules"][0]["risk"], "R4_CORE")
        self.assertIn("FKCM_V1", [x["subsystem"] for x in extension["subsystem_rules"]])
