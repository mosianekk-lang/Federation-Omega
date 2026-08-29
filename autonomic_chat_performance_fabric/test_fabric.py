import unittest

from autonomic_chat_performance_fabric import (
    AdaptiveRouter, ContentAddressedEventLog, ContextCompiler, Event, Health, Route
)


class FabricTests(unittest.TestCase):
    def test_append_deduplicates_and_verifies_chain(self):
        log = ContentAddressedEventLog()
        first = Event("kim", "c1", 1, "MESSAGE", "hello")
        self.assertEqual(log.append(first)["state"], "APPENDED")
        self.assertEqual(log.append(first)["state"], "IDEMPOTENT")
        second = Event("kim", "c1", 2, "MESSAGE", "world", first.event_hash)
        log.append(second)
        self.assertTrue(log.verify("kim", "c1"))

    def test_stale_head_fails_closed(self):
        log = ContentAddressedEventLog()
        with self.assertRaisesRegex(ValueError, "STALE_OR_CONFLICTED_HEAD"):
            log.append(Event("kim", "c1", 1, "MESSAGE", "x", "wrong"))

    def test_router_chooses_healthiest_authorized_route(self):
        routes = [
            Route("kdv", frozenset({"STATE"}), True, frozenset({"PRIVATE"})),
            Route("worker", frozenset({"STATE"}), True, frozenset({"PRIVATE"})),
        ]
        health = {
            "kdv": Health(True, 100, 0.01, 0.5),
            "worker": Health(True, 50, 0, 1),
        }
        self.assertEqual(AdaptiveRouter().select("STATE", "PRIVATE", routes, health).name, "worker")

    def test_router_rejects_cost_and_authority(self):
        routes = [Route("paid", frozenset({"X"}), False, frozenset({"PRIVATE"}), 1)]
        with self.assertRaisesRegex(RuntimeError, "NO_AUTHORIZED_HEALTHY_ROUTE"):
            AdaptiveRouter().select("X", "PRIVATE", routes, {"paid": Health(True, 1, 0, 1)})

    def test_context_is_bounded(self):
        compiler = ContextCompiler(1000)
        events = [Event("n", "c", i, "MESSAGE", "x" * 300) for i in range(10)]
        result = compiler.compile("do", ["r"], ["f"], ["u"], events)
        self.assertLessEqual(len(result), 1000)
        self.assertIn("CURRENT INSTRUCTION", result)


if __name__ == "__main__":
    unittest.main()
