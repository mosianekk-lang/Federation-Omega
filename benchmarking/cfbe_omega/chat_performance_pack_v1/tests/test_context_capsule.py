import unittest

from cfbe_chatperf.context_capsule import CapsuleError, build_capsule


def source():
    return {"objective":"audit","requirements":["proof"],"constraints":["no deploy"],"source_epochs":{"chat":"e1"},"routes":["local"],"open_gates":[],"recent_failures":["payload"],"notes":"x"*200,"unrelated":"omit"}


class CapsuleTests(unittest.TestCase):
    def test_deterministic(self): self.assertEqual(build_capsule(source()),build_capsule(source()))
    def test_required_preserved(self): self.assertEqual(build_capsule(source())["objective"],"audit")
    def test_unknown_omitted(self): self.assertIn("unrelated",build_capsule(source())["omitted"])
    def test_budget_observed(self):
        cap=build_capsule(source(),max_bytes=512); self.assertLessEqual(cap["bytes"],512)
    def test_small_budget_rejected(self):
        with self.assertRaises(CapsuleError): build_capsule(source(),max_bytes=100)
    def test_missing_required_rejected(self):
        value=source(); value.pop("objective")
        with self.assertRaises(CapsuleError): build_capsule(value)
    def test_required_too_large_rejected(self):
        value=source(); value["objective"]="z"*500
        with self.assertRaises(CapsuleError): build_capsule(value,max_bytes=256)


if __name__ == "__main__": unittest.main()
