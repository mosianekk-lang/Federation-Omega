import unittest

from cfbe_chatperf.benchmark import score_benchmark


class BenchmarkTests(unittest.TestCase):
    def test_verified_achieved(self):
        result=score_benchmark({"dimensions":[{"id":"x","weight":1,"score":8,"state":"VERIFIED"}]})
        self.assertEqual(result["verified_score"],80); self.assertEqual(result["decision"],"ACHIEVED")
    def test_design_not_achieved(self):
        result=score_benchmark({"dimensions":[{"id":"x","weight":1,"score":9,"state":"DESIGN"}]})
        self.assertEqual(result["verified_score"],0); self.assertEqual(result["readiness_score"],90)
    def test_mixed_state(self):
        result=score_benchmark({"dimensions":[{"id":"a","weight":.5,"score":8,"state":"VERIFIED"},{"id":"b","weight":.5,"score":10,"state":"UNKNOWN"}]})
        self.assertEqual(result["verified_score"],40); self.assertEqual(result["readiness_score"],90)
    def test_weights_rejected(self):
        with self.assertRaises(ValueError): score_benchmark({"dimensions":[{"id":"x","weight":.2,"score":1,"state":"VERIFIED"}]})
    def test_score_rejected(self):
        with self.assertRaises(ValueError): score_benchmark({"dimensions":[{"id":"x","weight":1,"score":11,"state":"VERIFIED"}]})
    def test_state_rejected(self):
        with self.assertRaises(ValueError): score_benchmark({"dimensions":[{"id":"x","weight":1,"score":8,"state":"DEPLOYED"}]})


if __name__ == "__main__": unittest.main()
