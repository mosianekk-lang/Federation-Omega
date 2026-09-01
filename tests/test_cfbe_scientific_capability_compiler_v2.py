from __future__ import annotations

import unittest
from benchmarking.cfbe_omega import scientific_capability_compiler_v2 as m

SHA = "a" * 40
DIGEST = "b" * 64


def dna(capability_id: str, objective: str, primitives: list[str]) -> m.CapabilityDNA:
    return m.compile_capability_dna({
        "capability_id": capability_id,
        "objective": objective,
        "triggers": ["mission"],
        "inputs": ["input"],
        "outputs": ["receipt"],
        "primitives": primitives,
        "invariants": ["fail closed", "no effect"],
        "failure_modes": ["drift"],
        "recovery_controls": ["rollback"],
        "authority_requirements": ["none"],
        "proof_requirements": ["independent readback"],
        "value_hypothesis": "reduce burden",
        "provenance_refs": ["public:spec"],
        "license_class": "STANDARD",
    })


class Wave2Tests(unittest.TestCase):
    def test_genome_is_exact_100(self):
        genes = m.load_wave2_genome()
        self.assertEqual(100, len(genes))
        self.assertEqual("CF2-001", genes[0].gene_id)
        self.assertEqual("CF2-100", genes[-1].gene_id)
        self.assertEqual(100, len({x.gene_id for x in genes}))

    def test_deep_tranche_exact_22(self):
        r = m.compile_wave2_receipt()
        self.assertEqual(22, r.deep_control_count)
        self.assertEqual(100, r.routed_count)
        self.assertEqual(100, r.source_contract_count)
        self.assertFalse(r.provider_effect_authorized)

    def test_generic_admission_requires_real_gap(self):
        r = m.evaluate_gene_admission(m.GeneAdmissionInput(
            "CF2-001", False, 0.0, 0, True, True, True
        ))
        self.assertEqual(m.AdmissionDecision.HOLD, r.decision)
        self.assertIn("MEASURED_GAP_REQUIRED", r.blockers)

    def test_generic_admission_reuse_first(self):
        r = m.evaluate_gene_admission(m.GeneAdmissionInput(
            "CF2-001", True, 0.9, 0, True, True, True
        ))
        self.assertEqual(m.AdmissionDecision.REUSE, r.decision)

    def test_generic_admission_effect_requires_authority(self):
        r = m.evaluate_gene_admission(m.GeneAdmissionInput(
            "CF2-093", True, 0.0, 0, True, True, True,
            exact_authority_available=False, provider_effect_required=True
        ))
        self.assertEqual(m.AdmissionDecision.HOLD, r.decision)
        self.assertIn("EXACT_PROVIDER_AUTHORITY_REQUIRED", r.blockers)

    def test_capability_dna_is_deterministic(self):
        one = dna("CAP-A", "portable sandbox execution", ["manifest", "sandbox"])
        two = dna("CAP-A", "portable sandbox execution", ["sandbox", "manifest"])
        self.assertEqual(one.dna_sha256, two.dna_sha256)

    def test_capability_dna_requires_proof(self):
        data = {
            "capability_id": "X", "objective": "x", "value_hypothesis": "v",
            "primitives": ["p"], "invariants": ["i"], "provenance_refs": ["r"],
            "license_class": "standard",
        }
        with self.assertRaisesRegex(ValueError, "PROOF"):
            m.compile_capability_dna(data)

    def test_primitive_decomposition_reuse(self):
        r = m.decompose_primitives(
            capability_id="X", required_primitives=["a", "b"], estate_primitives=["a", "b", "c"]
        )
        self.assertEqual(m.AdmissionDecision.REUSE, r.recommended_route)
        self.assertEqual(1.0, r.overlap_ratio)

    def test_primitive_decomposition_extend(self):
        r = m.decompose_primitives(
            capability_id="X", required_primitives=["a", "b", "c"], estate_primitives=["a", "b"]
        )
        self.assertEqual(m.AdmissionDecision.EXTEND, r.recommended_route)

    def test_semantic_novelty_duplicate_reuse(self):
        incumbent = dna("A", "portable sandbox execution", ["manifest", "sandbox"])
        candidate = dna("B", "portable sandbox execution", ["manifest", "sandbox"])
        r = m.detect_semantic_novelty(candidate, [incumbent])
        self.assertEqual(m.AdmissionDecision.REUSE, r.decision)
        self.assertGreaterEqual(r.maximum_similarity, 0.88)

    def test_semantic_novelty_new(self):
        incumbent = dna("A", "portable sandbox execution", ["manifest", "sandbox"])
        candidate = dna("B", "causal ecology prediction", ["graph", "bayesian"])
        r = m.detect_semantic_novelty(candidate, [incumbent])
        self.assertEqual(m.AdmissionDecision.ADMIT, r.decision)

    def test_incident_harvest_requires_proof(self):
        with self.assertRaisesRegex(ValueError, "PROOF"):
            m.harvest_incident(m.IncidentRecord("I", "symptom", "cause", "retry", "fencing", ()))

    def test_incident_harvest_generates_negative_rule(self):
        r = m.harvest_incident(m.IncidentRecord(
            "I1", "duplicate", "missing idempotency", "blind retry", "idempotency fence", ("run:1",)
        ))
        self.assertIn("DO_NOT_REPEAT", r.negative_design_rule)

    def test_clean_room_blocks_proprietary_source(self):
        r = m.compile_clean_room_plan(
            capability_id="X", public_spec_refs=["public:spec"],
            behavioral_requirements=["behavior"], independent_primitives=["primitive"],
            license_class="standard", proprietary_source_used=True
        )
        self.assertFalse(r.clean_room_admissible)

    def test_clean_room_admits_public_spec(self):
        r = m.compile_clean_room_plan(
            capability_id="X", public_spec_refs=["public:spec"],
            behavioral_requirements=["behavior"], independent_primitives=["primitive"],
            license_class="standard", acceptance_tests=["test"]
        )
        self.assertTrue(r.clean_room_admissible)

    def test_hypothesis_is_preregistered(self):
        h = m.generate_hypothesis(
            capability_id="X", outcome_metric="latency", expected_direction="decrease",
            minimum_effect=0.1, guardrail_metrics=["quality"], disqualifiers=["regression"]
        )
        self.assertTrue(h.preregistered)
        self.assertEqual("DECREASE", h.expected_direction)

    def test_information_gain_selects_best_utility(self):
        selected = m.select_information_gain_experiment([
            m.ExperimentCandidate("a", 1.0, 0.5, 10, 0.1, 1.0),
            m.ExperimentCandidate("b", 1.0, 0.2, 5, 0.1, 1.0),
        ])
        self.assertEqual("b", selected.experiment_id)

    def test_causal_graph_acyclic(self):
        r = m.compile_causal_graph([
            m.CausalEdge("A", "B", 0.9, ("proof:1",)),
            m.CausalEdge("B", "C", 0.8, ("proof:2",)),
        ])
        self.assertTrue(r.acyclic)

    def test_causal_graph_detects_cycle(self):
        r = m.compile_causal_graph([
            m.CausalEdge("A", "B", 0.9, ("proof:1",)),
            m.CausalEdge("B", "A", 0.9, ("proof:2",)),
        ])
        self.assertFalse(r.acyclic)

    def test_counterfactual_effect(self):
        self.assertEqual(2.0, m.matched_counterfactual_effect([5, 7], [3, 5]))

    def test_conformal_gate_bounded(self):
        r = m.conformal_interval(
            prediction=10, calibration_residuals=[1, 1, 1, 2, 2], alpha=0.2, maximum_width=4
        )
        self.assertTrue(r.sufficiently_bounded)
        self.assertLessEqual(r.lower, r.prediction)
        self.assertGreaterEqual(r.upper, r.prediction)

    def test_sandbox_manifest_provider_neutral(self):
        r = m.compile_sandbox_manifest(
            manifest_id="M", source_head_sha=SHA,
            filesystem_mounts=["/workspace"], tools=["python"], dependencies=["stdlib"],
            network_allowlist=[], secret_handles=["secret://handle"],
            resource_limits={"cpu": 1, "memory_mb": 512},
        )
        self.assertTrue(r.provider_neutral)

    def test_workspace_snapshot_rejects_bad_digest(self):
        with self.assertRaisesRegex(ValueError, "DIGEST"):
            m.compile_workspace_snapshot(
                snapshot_id="S", source_head_sha=SHA, manifest_sha256=DIGEST,
                files={"a.txt": "bad"}
            )

    def test_workspace_snapshot_portable(self):
        r = m.compile_workspace_snapshot(
            snapshot_id="S", source_head_sha=SHA, manifest_sha256=DIGEST,
            files={"a.txt": DIGEST}
        )
        self.assertTrue(r.portable)

    def test_fiber_generation_fence(self):
        with self.assertRaisesRegex(ValueError, "FENCE"):
            m.create_fiber_checkpoint(
                fiber_id="F", generation=1, previous_generation=1, state="WAITING",
                idempotency_key="k", payload={"x": 1}
            )

    def test_fiber_checkpoint(self):
        r = m.create_fiber_checkpoint(
            fiber_id="F", generation=2, previous_generation=1, state="WAITING",
            idempotency_key="k", payload={"x": 1}
        )
        self.assertEqual("WAITING", r.state)

    def test_memory_remember_update_forget(self):
        item = m.reconcile_memory(
            None, operation="remember", memory_id="M", memory_class="FACT",
            value="v", source_refs=["proof:1"], confidence=0.8
        )
        self.assertEqual(1, item.version)
        updated = m.reconcile_memory(
            item, operation="update", memory_id="M", memory_class="FACT",
            value="v2", source_refs=["proof:2"], confidence=0.9
        )
        self.assertEqual(2, updated.version)
        forgotten = m.reconcile_memory(updated, operation="forget", memory_id="M")
        self.assertEqual("FORGOTTEN", forgotten.state)

    def test_memory_influence(self):
        r = m.attribute_memory_influence(
            decision_id="D", memory_id="M", with_memory_score=0.9, without_memory_score=0.5
        )
        self.assertTrue(r.materially_influential)

    def test_authority_lattice_exact(self):
        req = m.CapabilityGrant("read", "repo", "audit", ("readonly",))
        grant = m.CapabilityGrant("read", "repo", "audit", ("readonly", "logged"))
        self.assertTrue(m.authorize_capability(req, [grant]).allowed)

    def test_authority_lattice_no_broad_inference(self):
        req = m.CapabilityGrant("write", "repo", "audit", ())
        grant = m.CapabilityGrant("read", "repo", "audit", ())
        self.assertFalse(m.authorize_capability(req, [grant]).allowed)

    def test_taint_blocks_untrusted_effect(self):
        value = m.taint_value("x", [m.Taint.UNTRUSTED], ["web:1"])
        self.assertFalse(m.taint_flow_allowed(value.labels, sink="EXTERNAL_EFFECT"))

    def test_taint_blocks_private_public_output(self):
        value = m.taint_value("x", [m.Taint.PRIVATE], ["private:1"])
        self.assertFalse(m.taint_flow_allowed(value.labels, sink="PUBLIC_OUTPUT"))

    def test_transcript_hash_chain(self):
        t = m.ExecutionTranscript()
        t.append(event_type="PLAN", subject="m", payload={"a": 1})
        t.append(event_type="VERIFY", subject="m", payload={"ok": True})
        self.assertTrue(t.verify())
        self.assertEqual("GENESIS", t.events[0].previous_hash)

    def test_flight_recorder_narrative(self):
        r = m.AgentFlightRecorder("M")
        r.record(kind=m.TraceKind.PLAN, subject="plan", correlation_id="c", duration_ms=1, payload={})
        r.record(kind=m.TraceKind.VERIFY, subject="verify", correlation_id="c", duration_ms=2, payload={})
        self.assertEqual(2, len(r.execution_narrative()))

    def test_cognitive_load_index(self):
        r = m.cognitive_load_index(m.CognitiveLoadObservation(0, 0, 0, 0, 2, 0))
        self.assertTrue(r.low_burden)
        high = m.cognitive_load_index(m.CognitiveLoadObservation(5, 2, 1, 1, 10, 2))
        self.assertFalse(high.low_burden)

    def test_protocol_gateway_readonly_no_authority(self):
        r = m.compile_protocol_envelope(
            protocol="MCP", protocol_version="1", mission_id="M", capability="read",
            operation="get", arguments={"x": 1}, trace_id="T", read_only=True
        )
        self.assertTrue(r.read_only)

    def test_protocol_gateway_effect_needs_authority(self):
        with self.assertRaisesRegex(ValueError, "AUTHORITY"):
            m.compile_protocol_envelope(
                protocol="A2A", protocol_version="1", mission_id="M", capability="write",
                operation="set", arguments={"x": 1}, trace_id="T", read_only=False
            )

    def test_openapi_compiler(self):
        tools = m.compile_openapi_capabilities({
            "paths": {
                "/items": {
                    "get": {"operationId": "list_items"},
                    "post": {"operationId": "create_item", "parameters": [{"name": "name", "required": True}]},
                }
            }
        })
        self.assertEqual(2, len(tools))
        self.assertFalse(tools[0].authority_required)
        self.assertTrue(tools[1].authority_required)

    def test_ecology_governor(self):
        r = m.evaluate_capability_ecology([
            m.EcologyCapability("a", 1, 1, 0, ("core",), "same"),
            m.EcologyCapability("b", 2, 1, 1, ("core",), "same"),
            m.EcologyCapability("c", 2, 1, 1, ("core",), "same", superseded_by="b"),
        ])
        self.assertIn("a", r.dormant_ids)
        self.assertIn("c", r.superseded_ids)
        self.assertIn("same", r.high_overlap_clusters)
        self.assertIn("REDUCE_DEPENDENCY_CONCENTRATION", r.actions)

    def test_summary_truth_boundary(self):
        s = m.benchmark_summary()
        self.assertEqual(100, s["wave2_gene_count"])
        self.assertFalse(s["truth_boundary"]["provider_effect_authorized"])
        self.assertFalse(s["truth_boundary"]["stable_promotion_authorized"])


if __name__ == "__main__":
    unittest.main()
