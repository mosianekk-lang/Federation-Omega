from __future__ import annotations
import unittest
from benchmarking.cfbe_omega.autopilot_sentinel_neural_portfolio_v1 import (
    NeuralMaturity, NeuralRequirement, NeuralSubstrate, default_portfolio, select_portfolio,
)

class NeuralPortfolioTests(unittest.TestCase):
    def test_nine_substrates(self): self.assertEqual(9,len(default_portfolio().genes))
    def test_hash(self): self.assertEqual(64,len(default_portfolio().portfolio_sha256))
    def test_attention_runtime(self):
        g=next(x for x in default_portfolio().genes if x.substrate is NeuralSubstrate.ATTENTION); self.assertEqual(NeuralMaturity.REUSE_RUNTIME,g.maturity)
    def test_external_memory_runtime(self):
        g=next(x for x in default_portfolio().genes if x.substrate is NeuralSubstrate.EXTERNAL_MEMORY); self.assertFalse(g.weight_change_required)
    def test_test_time_memory_research(self):
        g=next(x for x in default_portfolio().genes if x.substrate is NeuralSubstrate.TEST_TIME_NEURAL_MEMORY); self.assertTrue(g.weight_change_required)
    def test_jepa_research(self):
        g=next(x for x in default_portfolio().genes if x.substrate is NeuralSubstrate.JEPA_WORLD_MODEL); self.assertEqual(NeuralMaturity.RESEARCH_OPTION,g.maturity)
    def test_ctm_research(self):
        g=next(x for x in default_portfolio().genes if x.substrate is NeuralSubstrate.TEMPORAL_SYNCHRONY); self.assertEqual(NeuralMaturity.RESEARCH_OPTION,g.maturity)
    def test_distillation_training_gated(self):
        g=next(x for x in default_portfolio().genes if x.substrate is NeuralSubstrate.DISTILLATION); self.assertEqual(NeuralMaturity.TRAINING_GATED,g.maturity)
    def test_no_training_selects_attention(self):
        s=select_portfolio(NeuralRequirement(("working context",),False)); self.assertIn("ATTENTION",s.selected_substrates)
    def test_no_training_blocks_neural_memory(self):
        s=select_portfolio(NeuralRequirement(("surprise-gated learned memory",),False)); self.assertIn("surprise-gated learned memory",s.blocked_roles)
    def test_training_can_select_neural_memory(self):
        s=select_portfolio(NeuralRequirement(("surprise-gated learned memory",),True)); self.assertIn("TEST_TIME_NEURAL_MEMORY",s.selected_substrates)
    def test_unknown_role_blocked(self):
        s=select_portfolio(NeuralRequirement(("nonexistent role",),False)); self.assertEqual(("nonexistent role",),s.blocked_roles)
