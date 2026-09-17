import copy
import unittest

from cfbe_chatperf.recovery_snapshot import SnapshotError, sign_snapshot, verify_snapshot


def payload():
    return {"snapshot_id":"s1","producer_id":"p1","mission_id":"m1","generation":2,"created_at":100,"expires_at":200,"source_epochs":{"drive":"e1"},"coverage":{"drive":True,"ledger":True},"state":"VERIFIED"}


class SnapshotTests(unittest.TestCase):
    def test_round_trip(self):
        signed=sign_snapshot(payload(),b"secret","k1")
        self.assertEqual(verify_snapshot(signed,b"secret",now=150)["decision"],"ACCEPT")
    def test_tamper_rejected(self):
        signed=sign_snapshot(payload(),b"secret","k1"); signed["generation"]=3
        self.assertIn("SIGNATURE_INVALID",verify_snapshot(signed,b"secret",now=150)["issues"])
    def test_stale_rejected(self):
        signed=sign_snapshot(payload(),b"secret","k1")
        self.assertIn("SNAPSHOT_STALE",verify_snapshot(signed,b"secret",now=201)["issues"])
    def test_coverage_rejected(self):
        signed=sign_snapshot(payload(),b"secret","k1")
        self.assertIn("COVERAGE_MISSING:github",verify_snapshot(signed,b"secret",now=150,required_coverage={"github"})["issues"])
    def test_generation_rejected(self):
        signed=sign_snapshot(payload(),b"secret","k1")
        self.assertIn("GENERATION_MISMATCH",verify_snapshot(signed,b"secret",now=150,expected_generation=3)["issues"])
    def test_empty_key_rejected(self):
        with self.assertRaises(SnapshotError): sign_snapshot(payload(),b"","k1")
    def test_missing_field_rejected(self):
        value=payload(); value.pop("coverage")
        with self.assertRaises(SnapshotError): sign_snapshot(value,b"x","k1")
    def test_input_not_mutated(self):
        value=payload(); original=copy.deepcopy(value); sign_snapshot(value,b"x","k1")
        self.assertEqual(value,original)


if __name__ == "__main__": unittest.main()
