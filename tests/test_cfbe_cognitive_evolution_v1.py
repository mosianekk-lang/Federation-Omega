import unittest

from benchmarking.cfbe_omega import cognitive_evolution_v1 as m
from benchmarking.cfbe_omega.omega_harvest_max_v2 import CapabilityMechanism


def env(*allowed):
    return m.OuterEnvelope(
        objective="build verified adaptive cognition",
        allowed_substrates=allowed or (m.EvolutionSubstrate.MEMORY, m.EvolutionSubstrate.SKILL, m.EvolutionSubstrate.CODE, m.EvolutionSubstrate.EVALUATOR),
        authority_ceiling="A1_INTERNAL",
        data_boundary="PUBLIC_AND_OWNER_APPROVED",
        owner_intent_hash="a" * 64,
        compute_budget=100,
        safety_floor=0.90,
        reliability_floor=0.90,
    )


def gene(gid="G1", substrate=m.EvolutionSubstrate.SKILL):
    return m.CognitiveGene(gid, substrate, "improve verified reasoning", ("falsify", "measure"), ("no self certification",), proof_refs=("proof:1",))


def genome():
    return m.compile_genome(env(), [gene()])


def cand(cid="C1", *, g=None, niche="reasoning", quality=.95, safety=.95, reliability=.96, transfer=.90, novelty=.80, hidden=True, benchmark=False, tamper=False, self_auth=False, prod_mut=False, rollback=True, provenance=True, proof_refs=("p1",), domains=("deterministic", "independent_model"), families=("code", "judge"), transfer_scores=None, replications=2, ancestors=()):
    return m.Candidate(
        cid, g or genome(), niche,
        m.FitnessVector(quality, safety, reliability, transfer, novelty, 1, 1, 0, 1),
        proof_refs, rollback, provenance, hidden, benchmark, tamper, self_auth, prod_mut,
        domains, families,
        transfer_scores or {"alternate_model": .9, "alternate_harness": .9, "adjacent_task": .9},
        replications, ancestors,
    )


class GenomeCourt(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(m.compile_genome(env(), [gene()]).fingerprint_sha256, m.compile_genome(env(), [gene()]).fingerprint_sha256)

    def test_order_invariant(self):
        a, b = gene("A"), gene("B", m.EvolutionSubstrate.MEMORY)
        self.assertEqual(m.compile_genome(env(), [a, b]).fingerprint_sha256, m.compile_genome(env(), [b, a]).fingerprint_sha256)

    def test_duplicate_gene_rejected(self):
        with self.assertRaisesRegex(ValueError, "GENOME_GENES_INVALID"):
            m.compile_genome(env(), [gene(), gene()])

    def test_unauthorized_weight_rejected(self):
        with self.assertRaisesRegex(ValueError, "SUBSTRATE_OUTSIDE_ENVELOPE"):
            m.compile_genome(env(m.EvolutionSubstrate.SKILL), [gene("W", m.EvolutionSubstrate.WEIGHT)])

    def test_production_self_mutation_envelope_rejected(self):
        bad = m.OuterEnvelope("x", (m.EvolutionSubstrate.SKILL,), "A1", "PUBLIC", "b"*64, 1, no_production_self_mutation=False)
        with self.assertRaisesRegex(ValueError, "PRODUCTION_SELF_MUTATION_FORBIDDEN"):
            bad.validate()

    def test_parent_sets_generation_one(self):
        self.assertEqual(m.compile_genome(env(), [gene()], parent_genomes=("PARENT",)).generation, 1)


class VerifierCourt(unittest.TestCase):
    def test_good_candidate_passes(self):
        self.assertTrue(m.verify_candidate(cand(), env()).passed)

    def test_hidden_holdout_required(self):
        self.assertIn("HIDDEN_HELD_OUT_REQUIRED", m.verify_candidate(cand(hidden=False), env()).blockers)

    def test_benchmark_and_tampering_rejected(self):
        r = m.verify_candidate(cand(benchmark=True, tamper=True), env())
        self.assertIn("BENCHMARK_ACCESS_FORBIDDEN", r.blockers); self.assertIn("SCORE_TAMPERING_DETECTED", r.blockers)

    def test_self_authority_and_direct_prod_mutation_rejected(self):
        r = m.verify_candidate(cand(self_auth=True, prod_mut=True), env())
        self.assertIn("SELF_GRANTED_AUTHORITY_FORBIDDEN", r.blockers); self.assertIn("DIRECT_PRODUCTION_SELF_MUTATION_FORBIDDEN", r.blockers)

    def test_safety_reliability_floors(self):
        r = m.verify_candidate(cand(safety=.5, reliability=.5), env())
        self.assertIn("SAFETY_REGRESSION", r.blockers); self.assertIn("RELIABILITY_REGRESSION", r.blockers)

    def test_rollback_provenance_proof_required(self):
        r = m.verify_candidate(cand(rollback=False, provenance=False, proof_refs=()), env())
        self.assertIn("ROLLBACK_REQUIRED", r.blockers); self.assertIn("PROVENANCE_REQUIRED", r.blockers); self.assertIn("INDEPENDENT_PROOF_REQUIRED", r.blockers)

    def test_quorum_replication_required(self):
        r = m.verify_candidate(cand(domains=("one",), families=("one",), replications=1), env())
        self.assertIn("INDEPENDENT_VERIFIER_DOMAIN_QUORUM_REQUIRED", r.blockers); self.assertIn("EVALUATOR_FAMILY_DIVERSITY_REQUIRED", r.blockers); self.assertIn("REPLICATION_FLOOR_REQUIRED", r.blockers)

    def test_transfer_missing_and_floor(self):
        r = m.verify_candidate(cand(transfer_scores={"alternate_model": .9, "alternate_harness": .3}), env())
        self.assertIn("TRANSFER_FLOOR_FAILED:alternate_harness", r.blockers); self.assertIn("TRANSFER_AXIS_MISSING:adjacent_task", r.blockers)

    def test_envelope_drift_rejected(self):
        g = genome(); other = m.OuterEnvelope("different", env().allowed_substrates, "A1_INTERNAL", "PUBLIC_AND_OWNER_APPROVED", "a"*64, 100, .90, .90)
        self.assertIn("OUTER_ENVELOPE_DRIFT", m.verify_candidate(cand(g=g), other).blockers)


class ArchiveCourt(unittest.TestCase):
    def test_first_niche_elite(self):
        c = cand(); action, archive = m.update_quality_diversity_archive(m.QualityDiversityArchive(), c, m.verify_candidate(c, env()))
        self.assertEqual(action, "FIRST_NICHE_ELITE"); self.assertEqual(archive.elite_for("reasoning").candidate_id, "C1")

    def test_better_replaces_and_preserves_ancestor(self):
        c1 = cand("C1", quality=.91, novelty=.5); _, a1 = m.update_quality_diversity_archive(m.QualityDiversityArchive(), c1, m.verify_candidate(c1, env()))
        c2 = cand("C2", quality=.99, novelty=.6, ancestors=("C1",)); action, a2 = m.update_quality_diversity_archive(a1, c2, m.verify_candidate(c2, env()))
        self.assertEqual(action, "ELITE_REPLACED_ANCESTOR_PRESERVED"); self.assertEqual(a2.elite_for("reasoning").candidate_id, "C2"); self.assertIn("C1", [x.candidate_id for x in a2.by_class(m.ArchiveClass.STEPPING_STONE)])

    def test_high_novelty_lower_scorer_is_stepping_stone(self):
        c1 = cand("C1", quality=.99, novelty=.5); _, a1 = m.update_quality_diversity_archive(m.QualityDiversityArchive(), c1, m.verify_candidate(c1, env()))
        c2 = cand("C2", quality=.70, novelty=.95); action, a2 = m.update_quality_diversity_archive(a1, c2, m.verify_candidate(c2, env()))
        self.assertEqual(action, "NOVEL_STEPPING_STONE_RETAINED"); self.assertIn("C2", [x.candidate_id for x in a2.by_class(m.ArchiveClass.STEPPING_STONE)])

    def test_failure_and_antipattern_retained(self):
        c = cand("BAD", tamper=True); action, a = m.update_quality_diversity_archive(m.QualityDiversityArchive(), c, m.verify_candidate(c, env()), severe_failure=True, failure_fingerprint="f"*64)
        self.assertEqual(action, "FAILURE_AND_ANTI_PATTERN_RETAINED"); self.assertEqual(len(a.by_class(m.ArchiveClass.FAILURE)), 1); self.assertEqual(len(a.by_class(m.ArchiveClass.ANTI_PATTERN)), 1)

    def test_low_novelty_loser_not_retained(self):
        c1 = cand("C1", quality=.99, novelty=.5); _, a1 = m.update_quality_diversity_archive(m.QualityDiversityArchive(), c1, m.verify_candidate(c1, env()))
        c2 = cand("C2", quality=.70, novelty=.1); action, a2 = m.update_quality_diversity_archive(a1, c2, m.verify_candidate(c2, env()))
        self.assertEqual(action, "NO_ARCHIVE_CHANGE"); self.assertFalse(any(x.candidate_id == "C2" for x in a2.entries))


class ColdSlateCourt(unittest.TestCase):
    @staticmethod
    def mech(cid, primitives):
        return CapabilityMechanism(cid, "verified adaptive reasoning", tuple(primitives), ("safe",), ("receipt",), ("proof",), ("drift",))

    def test_reuse_equivalent(self):
        p = m.compile_cold_slate_plan(env(), [gene()], [self.mech("H", ("a", "b"))], [self.mech("I", ("a", "b"))])
        self.assertEqual(p.routes[0].disposition, m.ColdSlateDisposition.REUSE)

    def test_build_without_incumbent(self):
        p = m.compile_cold_slate_plan(env(), [gene()], [self.mech("H", ("a", "b"))], [])
        self.assertEqual(p.routes[0].disposition, m.ColdSlateDisposition.BUILD); self.assertIsNone(p.routes[0].incumbent_id)

    def test_extend_partial(self):
        p = m.compile_cold_slate_plan(env(), [gene()], [self.mech("H", ("a", "b", "c"))], [self.mech("I", ("a", "b"))], reuse_threshold=.95, extend_threshold=.50)
        self.assertEqual(p.routes[0].disposition, m.ColdSlateDisposition.EXTEND)

    def test_bad_thresholds_fail(self):
        with self.assertRaisesRegex(ValueError, "THRESHOLDS_INVALID"):
            m.compile_cold_slate_plan(env(), [gene()], [], [], reuse_threshold=.5, extend_threshold=.8)


class TenXCourt(unittest.TestCase):
    def test_design_only_never_tenx(self):
        c = cand(); r = m.ten_x_composite_frontier_court(candidate=c, verification=m.verify_candidate(c, env()), candidate_cey=20, frontier_cey=1, evidence_maturity="SOURCE_DESIGN_ONLY", independent_replications=3)
        self.assertFalse(r.ten_x_proven); self.assertIn("OPERATIONAL_EVIDENCE_REQUIRED", r.blockers)

    def test_ratio_below_ten_rejected(self):
        c = cand(); r = m.ten_x_composite_frontier_court(candidate=c, verification=m.verify_candidate(c, env()), candidate_cey=9.9, frontier_cey=1, evidence_maturity="SUSTAINED_VALUE_VERIFIED", independent_replications=2)
        self.assertIn("TEN_X_CEY_RATIO_NOT_MET", r.blockers)

    def test_mechanical_tenx_requires_sustained_verified_input(self):
        c = cand(); r = m.ten_x_composite_frontier_court(candidate=c, verification=m.verify_candidate(c, env()), candidate_cey=10, frontier_cey=1, evidence_maturity="SUSTAINED_VALUE_VERIFIED", independent_replications=2)
        self.assertTrue(r.ten_x_proven); self.assertEqual(r.state, "TEN_X_COMPOSITE_FRONTIER")

    def test_unverified_candidate_cannot_tenx(self):
        c = cand(tamper=True); r = m.ten_x_composite_frontier_court(candidate=c, verification=m.verify_candidate(c, env()), candidate_cey=100, frontier_cey=1, evidence_maturity="SUSTAINED_VALUE_VERIFIED", independent_replications=10)
        self.assertIn("VERIFICATION_REQUIRED", r.blockers)


class TruthBoundaryCourt(unittest.TestCase):
    def test_phase1_grants_no_effect_or_promotion(self):
        r = m.phase1_receipt()
        self.assertFalse(r["provider_effect_authorized"]); self.assertFalse(r["model_training_authorized"]); self.assertFalse(r["production_self_mutation_authorized"]); self.assertFalse(r["stable_promotion_authorized"])
        self.assertEqual(r["genome_ir"], "RESIDUAL_MINIMUM_BUILD")


if __name__ == "__main__":
    unittest.main()
