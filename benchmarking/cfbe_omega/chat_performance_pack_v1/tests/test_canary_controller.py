import copy
import unittest

from cfbe_chatperf.canary_controller import PHASES, evaluate_canary


def observations():
    values=[]
    for i,phase in enumerate(PHASES):
        candidate=phase.startswith("C")
        values.append({"phase":phase,"slot":f"s{i}","generation":3,"directly_observed":True,"duration_ms":40 if candidate else 100,"external_attempts":2 if candidate else 4,"proof_success":True,"invariant_failures":0,"harm_signals":0})
    return values


class CanaryTests(unittest.TestCase):
    def test_promotes_strict_pass(self): self.assertEqual(evaluate_canary(observations(),generation=3)["decision"],"PROMOTE")
    def test_wrong_sequence_holds(self):
        value=observations(); value.reverse(); self.assertIn("PHASE_SEQUENCE_INVALID",evaluate_canary(value,generation=3)["issues"])
    def test_duplicate_slot_holds(self):
        value=observations(); value[1]["slot"]=value[0]["slot"]; self.assertIn("SLOT_NOT_UNIQUE",evaluate_canary(value,generation=3)["issues"])
    def test_generation_mismatch_holds(self):
        value=observations(); value[0]["generation"]=2; self.assertIn("GENERATION_MISMATCH:0",evaluate_canary(value,generation=3)["issues"])
    def test_inferred_metric_holds(self):
        value=observations(); value[0]["directly_observed"]=False; self.assertIn("METRIC_NOT_DIRECT:0",evaluate_canary(value,generation=3)["issues"])
    def test_proof_loss_holds(self):
        value=observations(); value[2]["proof_success"]=False; self.assertIn("PROOF_PARITY_LOST",evaluate_canary(value,generation=3)["issues"])
    def test_harm_holds(self):
        value=observations(); value[4]["harm_signals"]=1; self.assertIn("HARM_SIGNAL",evaluate_canary(value,generation=3)["issues"])
    def test_slow_candidate_holds(self):
        value=observations();
        for item in value:
            if item["phase"].startswith("C"): item["duration_ms"]=90
        self.assertIn("DURATION_TARGET_MISSED",evaluate_canary(value,generation=3)["issues"])
    def test_always_deinstruments_terminal(self): self.assertTrue(evaluate_canary(observations(),generation=3)["deinstrument"])


if __name__ == "__main__": unittest.main()
