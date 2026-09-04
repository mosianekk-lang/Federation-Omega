import copy
import unittest

from deployment.cloud_run_traffic_rehearsal import allocation, rehearsal_plan, spec, traffic_state


def service(*rows):
    return {"status": {"traffic": list(rows)}}


class CloudRunTrafficRehearsalTests(unittest.TestCase):
    def test_moves_one_percent_and_preserves_input(self):
        current = service(
            {"revisionName": "seb-a", "percent": 80},
            {"revisionName": "seb-b", "percent": 20},
            {"revisionName": "seb-canary", "tag": "canary-1", "url": "https://example"},
        )
        original = copy.deepcopy(current)
        before, during = rehearsal_plan(current, "seb-canary")
        self.assertEqual({"seb-a": 80, "seb-b": 20}, before)
        self.assertEqual({"seb-a": 79, "seb-b": 20, "seb-canary": 1}, during)
        self.assertEqual(original, current)

    def test_aggregates_tagged_and_untagged_rows_for_same_revision(self):
        current = service(
            {"revisionName": "seb-a", "percent": 100},
            {"revisionName": "seb-a", "tag": "stable", "percent": 0},
        )
        self.assertEqual({"seb-a": 100}, allocation(current))

    def test_rejects_non_zero_traffic_canary(self):
        current = service(
            {"revisionName": "seb-a", "percent": 99},
            {"revisionName": "seb-canary", "percent": 1},
        )
        with self.assertRaisesRegex(ValueError, "already receives"):
            rehearsal_plan(current, "seb-canary")

    def test_rejects_incomplete_provider_readback(self):
        with self.assertRaisesRegex(ValueError, "total 100"):
            allocation(service({"revisionName": "seb-a", "percent": 99}))

    def test_spec_is_deterministic(self):
        self.assertEqual("seb-a=99,seb-z=1", spec({"seb-z": 1, "seb-a": 99}))

    def test_traffic_state_includes_tags_but_not_derived_urls(self):
        first = service({"revisionName": "seb-a", "percent": 100, "tag": "stable", "url": "old"})
        same = service({"url": "new", "tag": "stable", "percent": 100, "revisionName": "seb-a"})
        changed = service({"revisionName": "seb-a", "percent": 100, "tag": "other"})
        self.assertEqual(traffic_state(first), traffic_state(same))
        self.assertNotEqual(traffic_state(first), traffic_state(changed))


if __name__ == "__main__":
    unittest.main()
