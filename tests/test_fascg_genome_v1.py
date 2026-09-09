from __future__ import annotations
import unittest

from benchmarking.cfbe_omega.autopilot_sentinel_cognitive_genome_v1 import (
    GENOME_SIZE, GeneDisposition, GeneDomain, PlasticityClock, genome_receipt, load_genome, validate_genome,
)


class GenomeStructureTests(unittest.TestCase):
    def test_exact_144_genes(self):
        self.assertEqual(GENOME_SIZE, len(load_genome()))

    def test_twelve_domains(self):
        self.assertEqual(12, len(GeneDomain))

    def test_twelve_genes_per_domain(self):
        genes = load_genome()
        for domain in GeneDomain:
            self.assertEqual(12, sum(g.domain is domain for g in genes))

    def test_ids_are_sequential(self):
        self.assertEqual([f"FASCG-{i:03d}" for i in range(1, 145)], [g.gene_id for g in load_genome()])

    def test_no_duplicate_ids(self):
        ids = [g.gene_id for g in load_genome()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_genes_have_four_invariants(self):
        self.assertTrue(all(len(g.invariants) == 4 for g in load_genome()))

    def test_no_direct_production_mutation_invariant(self):
        self.assertTrue(all("NO_DIRECT_PRODUCTION_SELF_MUTATION" in g.invariants for g in load_genome()))

    def test_no_self_authority_invariant(self):
        self.assertTrue(all("NO_SELF_GRANTED_AUTHORITY" in g.invariants for g in load_genome()))

    def test_receipt_effect_false(self):
        r = genome_receipt(); self.assertFalse(r["provider_effect_authorized"])

    def test_receipt_training_false(self):
        r = genome_receipt(); self.assertFalse(r["model_training_authorized"])

    def test_receipt_ten_x_false(self):
        r = genome_receipt(); self.assertFalse(r["ten_x_verified"])

    def test_receipt_has_hash(self):
        self.assertEqual(64, len(genome_receipt()["sha256"]))

    def test_all_dispositions_represented(self):
        dispositions = {g.disposition for g in load_genome()}
        self.assertEqual(set(GeneDisposition), dispositions)

    def test_owner_gated_neural_options_exist(self):
        self.assertTrue(any(g.domain is GeneDomain.NEURAL_COGNITION and g.plasticity is PlasticityClock.OWNER_GATED for g in load_genome()))

    def test_build_residuals_are_minority(self):
        genes = load_genome()
        builds = sum(g.disposition is GeneDisposition.BUILD_RESIDUAL for g in genes)
        self.assertGreater(builds, 0)
        self.assertLess(builds, len(genes) // 2)


# One independent integrity court per gene. This makes the 144-gene genome itself
# a test denominator instead of treating list length as proof of semantic shape.
def _make_gene_test(index: int):
    def test(self):
        gene = load_genome()[index]
        self.assertEqual(f"FASCG-{index+1:03d}", gene.gene_id)
        self.assertTrue(gene.capability)
        self.assertTrue(gene.receiver)
        self.assertTrue(gene.frontier_gene.startswith("CLEAN_ROOM::"))
        self.assertIn(gene.disposition, set(GeneDisposition))
        self.assertIn(gene.plasticity, set(PlasticityClock))
        gene.validate()
    return test

for _i in range(GENOME_SIZE):
    setattr(GenomeStructureTests, f"test_gene_{_i+1:03d}_integrity", _make_gene_test(_i))
