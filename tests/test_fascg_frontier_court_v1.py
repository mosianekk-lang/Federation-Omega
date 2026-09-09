from __future__ import annotations
import unittest
from benchmarking.cfbe_omega.autopilot_sentinel_frontier_court_v1 import CompositeFrontierCourt, ResilienceRun


def run(scale=1.0, *, detection=.9,safety=.96,reliability=.96,transfer=.9, cost=.1, wall=.1, interventions=.1, complexity=.1):
    return ResilienceRun(min(.99,.9*scale),detection,min(.99,.8*scale),min(.99,.9*scale),transfer,safety,reliability,min(.99,.85*scale),cost,wall,interventions,complexity)

class FrontierCourtTests(unittest.TestCase):
    def test_design_like_candidate_not_ten_x(self):
        c=[run() for _ in range(5)]; b=[run() for _ in range(5)]; r=CompositeFrontierCourt().evaluate(c,b,sustained_value_verified=False); self.assertFalse(r.ten_x_verified)
    def test_sustained_value_required(self):
        c=[run(cost=.001,wall=.001,interventions=.001,complexity=.001) for _ in range(5)]; b=[run(cost=10,wall=10,interventions=10,complexity=10) for _ in range(5)]; r=CompositeFrontierCourt().evaluate(c,b,sustained_value_verified=False); self.assertFalse(r.ten_x_verified)
    def test_five_replications_required(self):
        with self.assertRaises(ValueError): CompositeFrontierCourt().evaluate([run()]*4,[run()]*4,sustained_value_verified=True)
    def test_matched_lengths_required(self):
        with self.assertRaises(ValueError): CompositeFrontierCourt().evaluate([run()]*5,[run()]*6,sustained_value_verified=True)
    def test_quality_floor_required(self):
        c=[run(detection=.5,cost=.001,wall=.001,interventions=.001,complexity=.001) for _ in range(5)]; b=[run(detection=.9,cost=10,wall=10,interventions=10,complexity=10) for _ in range(5)]; r=CompositeFrontierCourt().evaluate(c,b,sustained_value_verified=True); self.assertFalse(r.quality_floor_pass); self.assertFalse(r.ten_x_verified)
    def test_safety_floor_required(self):
        c=[run(safety=.8,cost=.001,wall=.001,interventions=.001,complexity=.001) for _ in range(5)]; b=[run(safety=.95,cost=10,wall=10,interventions=10,complexity=10) for _ in range(5)]; r=CompositeFrontierCourt().evaluate(c,b,sustained_value_verified=True); self.assertFalse(r.safety_floor_pass)
    def test_reliability_floor_required(self):
        c=[run(reliability=.8,cost=.001,wall=.001,interventions=.001,complexity=.001) for _ in range(5)]; b=[run(reliability=.95,cost=10,wall=10,interventions=10,complexity=10) for _ in range(5)]; r=CompositeFrontierCourt().evaluate(c,b,sustained_value_verified=True); self.assertFalse(r.reliability_floor_pass)
    def test_transfer_floor_required(self):
        c=[run(transfer=.7,cost=.001,wall=.001,interventions=.001,complexity=.001) for _ in range(5)]; b=[run(transfer=.6,cost=10,wall=10,interventions=10,complexity=10) for _ in range(5)]; r=CompositeFrontierCourt().evaluate(c,b,sustained_value_verified=True); self.assertFalse(r.transfer_pass)
    def test_ary_positive(self): self.assertGreater(run().ary(),0)
    def test_zero_component_zero_ary(self):
        r=ResilienceRun(0,.9,.8,.9,.9,.96,.96,.85,.1,.1,.1,.1); self.assertEqual(0,r.ary())
    def test_invalid_unit_rejected(self):
        with self.assertRaises(ValueError): run(detection=1.2).validate()
    def test_receipt_hash(self):
        r=CompositeFrontierCourt().evaluate([run()]*5,[run()]*5,sustained_value_verified=False); self.assertEqual(64,len(r.receipt_sha256))
