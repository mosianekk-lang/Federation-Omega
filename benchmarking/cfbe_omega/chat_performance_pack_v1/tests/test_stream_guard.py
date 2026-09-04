import unittest

from cfbe_chatperf.stream_guard import assess_stream


class StreamTests(unittest.TestCase):
    def test_healthy_admitted(self): self.assertEqual(assess_stream({"payload_tokens":100})["decision"],"ADMIT")
    def test_payload_quarantined(self): self.assertIn("PAYLOAD_OVERFLOW",assess_stream({"payload_tokens":4001})["issues"])
    def test_retry_storm(self): self.assertIn("RETRY_STORM",assess_stream({"retry_count":2,"retry_budget":1})["issues"])
    def test_concurrency_overflow(self): self.assertIn("CONCURRENCY_OVERFLOW",assess_stream({"concurrency":5})["issues"])
    def test_timebox(self): self.assertIn("TIMEBOX_EXCEEDED",assess_stream({"elapsed_minutes":19})["issues"])
    def test_raw_payload(self): self.assertIn("RAW_PAYLOAD_SERIALIZED",assess_stream({"raw_payload_serialized":True})["issues"])
    def test_secret(self): self.assertIn("SECRET_EXPOSURE",assess_stream({"contains_secret":True})["issues"])
    def test_unchanged_retry(self): self.assertIn("UNCHANGED_ROUTE_RETRY",assess_stream({"unchanged_failed_route_retried":True})["issues"])
    def test_cap_is_never_above_4000(self): self.assertEqual(assess_stream({"max_payload_tokens":9000})["maximum_segment_tokens"],4000)


if __name__ == "__main__": unittest.main()
