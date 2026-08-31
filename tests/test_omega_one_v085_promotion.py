import hashlib
import unittest

from omega_one.promotion import (
    AdmissionState,
    CourtResult,
    CourtStatus,
    DeterministicAdmissionCompiler,
    EvidenceDAG,
    EvidenceNode,
    ParallelPromotionMesh,
)


HEAD = "b" * 40
BASE = "a" * 40


def node(name, *dependencies):
    return EvidenceNode(
        node_id=name,
        kind="receipt",
        source_ref=f"urn:test:{name}",
        source_sha256=hashlib.sha256(name.encode()).hexdigest(),
        depends_on=tuple(dependencies),
    )


def passing_results():
    return tuple(
        CourtResult(spec.court_id, CourtStatus.PASS, HEAD, (f"urn:{spec.court_id}",), f"verifier:{spec.independent_lane}")
        for spec in ParallelPromotionMesh.REQUIRED_COURTS
    )


def compile_verdict(**overrides):
    values = dict(
        candidate_sha=HEAD,
        base_sha=BASE,
        reconciled_to_base=True,
        capability_count=100,
        results=passing_results(),
        evidence_dag=EvidenceDAG((node("source"), node("tests", "source"))),
        provenance_ref="urn:slsa:provenance",
        external_effect_requested=False,
    )
    values.update(overrides)
    return DeterministicAdmissionCompiler.compile(**values)


class PromotionMeshTests(unittest.TestCase):
    def test_courts_are_parallel_and_compiler_waits_for_all(self):
        plan = ParallelPromotionMesh.plan()
        self.assertEqual(plan["execution_mode"], "PARALLEL_NON_EFFECT")
        self.assertTrue(all(not court["depends_on"] for court in plan["courts"]))
        self.assertEqual(len(plan["compiler_depends_on"]), 4)
        self.assertFalse(plan["external_effect"])

    def test_healthy_packet_is_only_shadow_eligible(self):
        verdict = compile_verdict()
        self.assertEqual(verdict.state, AdmissionState.ELIGIBLE_FOR_SHADOW)
        self.assertEqual(verdict.next_stage, "SHADOW_NON_EFFECT")
        self.assertFalse(verdict.external_effect_authorized)

    def test_unreconciled_candidate_blocks(self):
        self.assertIn("NOT_RECONCILED_TO_CURRENT_BASE", compile_verdict(reconciled_to_base=False).reasons)

    def test_capability_dilution_blocks(self):
        self.assertIn("CAPABILITY_BASELINE_NOT_EXACTLY_100", compile_verdict(capability_count=99).reasons)

    def test_external_effect_request_blocks(self):
        verdict = compile_verdict(external_effect_requested=True)
        self.assertIn("EXTERNAL_EFFECT_PROHIBITED", verdict.reasons)
        self.assertFalse(verdict.external_effect_authorized)

    def test_missing_provenance_blocks(self):
        self.assertIn("BUILD_PROVENANCE_MISSING", compile_verdict(provenance_ref=None).reasons)

    def test_missing_court_blocks(self):
        verdict = compile_verdict(results=passing_results()[:-1])
        self.assertIn("REQUIRED_COURT_MISSING:CAPABILITY_VALUE", verdict.reasons)

    def test_failed_court_blocks(self):
        results = list(passing_results())
        results[0] = CourtResult("SOURCE_REGRESSION", CourtStatus.FAIL, HEAD, ("urn:fail",), "independent")
        self.assertIn("COURT_NOT_PASS:SOURCE_REGRESSION:FAIL", compile_verdict(results=results).reasons)

    def test_stale_court_sha_blocks(self):
        results = list(passing_results())
        first = results[0]
        results[0] = CourtResult(first.court_id, first.status, "c" * 40, first.evidence_refs, first.verifier)
        self.assertIn("COURT_SHA_MISMATCH:SOURCE_REGRESSION", compile_verdict(results=results).reasons)

    def test_missing_independent_verifier_blocks(self):
        results = list(passing_results())
        first = results[0]
        results[0] = CourtResult(first.court_id, first.status, HEAD, first.evidence_refs, first.court_id)
        self.assertIn("INDEPENDENT_VERIFIER_MISSING:SOURCE_REGRESSION", compile_verdict(results=results).reasons)

    def test_duplicate_court_blocks(self):
        results = passing_results()
        verdict = compile_verdict(results=results + (results[0],))
        self.assertIn("DUPLICATE_COURT:SOURCE_REGRESSION", verdict.reasons)

    def test_unknown_evidence_dependency_blocks(self):
        dag = EvidenceDAG((node("tests", "missing"),))
        self.assertTrue(any(reason.startswith("EVIDENCE_DAG_INVALID:") for reason in compile_verdict(evidence_dag=dag).reasons))

    def test_cyclic_evidence_blocks(self):
        dag = EvidenceDAG((node("a", "b"), node("b", "a")))
        self.assertTrue(any("cycle" in reason for reason in compile_verdict(evidence_dag=dag).reasons))

    def test_dag_and_verdict_are_deterministic(self):
        first = compile_verdict()
        second = compile_verdict()
        self.assertEqual(first.evidence_dag_sha256, second.evidence_dag_sha256)
        self.assertEqual(first.verdict_sha256, second.verdict_sha256)


if __name__ == "__main__":
    unittest.main()
