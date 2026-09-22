from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import patch

from federation.durable_scheduler_bus_v1 import (
    DurableMission, ScheduleKind, default_handlers, due, next_route_family
)
from scheduler.github_issue_bus import GitHubIssueDurableWorker


class DurableSchedulerBusV1Tests(unittest.TestCase):
    def mission(self, **kwargs):
        values = dict(
            mission_id="m1",
            idempotency_key="idem1",
            task_type="NO_EFFECT_CANARY",
            objective="prove no-effect durable scheduling",
        )
        values.update(kwargs)
        return DurableMission(**values)

    def test_immediate_due(self):
        self.assertTrue(due(self.mission(), now=datetime.now(timezone.utc)))

    def test_once_future_not_due(self):
        timestamp = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        self.assertFalse(due(
            self.mission(schedule_kind=ScheduleKind.ONCE, not_before=timestamp),
            now=datetime.now(timezone.utc),
        ))

    def test_once_past_due(self):
        timestamp = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        self.assertTrue(due(
            self.mission(schedule_kind=ScheduleKind.ONCE, not_before=timestamp),
            now=datetime.now(timezone.utc),
        ))

    def test_interval_floor(self):
        with self.assertRaisesRegex(ValueError, "MINIMUM_ONE_HOUR"):
            self.mission(
                schedule_kind=ScheduleKind.INTERVAL,
                not_before=datetime.now(timezone.utc).isoformat(),
                interval_seconds=60,
            ).validate()

    def test_handler_canary_no_effect(self):
        result = default_handlers().run(self.mission())
        self.assertEqual("PASS", result["status"])
        self.assertEqual("NONE", result["effects"])

    def test_unknown_handler_rejected(self):
        with self.assertRaises(KeyError):
            default_handlers().run(self.mission(task_type="NOPE"))

    def test_changed_route_after_second_failure(self):
        self.assertEqual("B", next_route_family("A", 2, ("A", "B")))

    def test_first_failure_may_use_first_route(self):
        self.assertEqual("A", next_route_family("A", 1, ("A", "B")))

    def test_no_routes_durable_queue(self):
        self.assertEqual("DURABLE_QUEUE", next_route_family("A", 2, ()))

    def test_digest_stable(self):
        self.assertEqual(self.mission().digest, self.mission().digest)

    def test_issue_discovery_uses_search_api_not_first_issue_page(self):
        worker = GitHubIssueDurableWorker("owner/repo", "token")
        observed = {}

        def fake_request(url, token, **kwargs):
            observed["url"] = url
            observed["token"] = token
            return {
                "items": [
                    {"number": 1648, "title": "[FUSE-MISSION] Durable Scheduler Canary 001"},
                    {"number": 99, "title": "ordinary issue"},
                ]
            }

        with patch("scheduler.github_issue_bus._request", side_effect=fake_request):
            rows = worker.list_open()

        self.assertIn("/search/issues?", observed["url"])
        self.assertIn("repo%3Aowner%2Frepo", observed["url"])
        self.assertIn("is%3Aissue", observed["url"])
        self.assertEqual("token", observed["token"])
        self.assertEqual([1648], [row["number"] for row in rows])

    def test_required_identity(self):
        with self.assertRaises(ValueError):
            self.mission(mission_id="").validate()


if __name__ == "__main__":
    unittest.main()
