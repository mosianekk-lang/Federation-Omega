from pathlib import Path
import tempfile
import unittest

from seb.effects import EffectBroker, EffectRejected
from seb.engine import SovereignEngine
from seb.ledger import JsonlLedger, LedgerIntegrityError
from seb.models import Budget, FailureClass, MissionIR, MissionState
from seb.policy import PolicyEngine
from seb.providers import MockProvider, ProviderFailure
from seb.router import ProviderRouter


def mission(mid="m1", authority="A0", data_class="private", tools=()):
    return MissionIR(mid, "produce verified output", ("r1",), ("accepted=true",),
                     authority, data_class, allowed_tools=tools, budget=Budget(max_tokens=100))


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def engine(self, providers, policy=None):
        ledger = JsonlLedger(Path(self.tmp.name) / "events.jsonl")
        return SovereignEngine(ledger, policy or PolicyEngine(), ProviderRouter(providers))

    def test_happy_path_and_replay_integrity(self):
        engine = self.engine([MockProvider("p1")])
        result = engine.execute(mission(), "hello", {"type": "object"},
                                lambda x: x.get("accepted") is True)
        self.assertEqual(result.state, MissionState.COMPLETED)
        self.assertTrue(engine.ledger.verify())
        self.assertEqual(len(result.proof), 2)

    def test_transient_retry_recovers(self):
        def behavior(req, calls):
            return ProviderFailure(FailureClass.TRANSIENT, "retry") if calls == 1 else {"accepted": True}
        provider = MockProvider("p1", behavior)
        engine = self.engine([provider])
        result = engine.execute(mission(), "hello", {}, lambda x: x["accepted"])
        self.assertEqual(result.state, MissionState.COMPLETED)
        self.assertEqual(result.attempts, 2)

    def test_provider_failover(self):
        first = MockProvider("outage", lambda req, calls: ProviderFailure(FailureClass.PROVIDER_OUTAGE, "down"))
        second = MockProvider("backup", lambda req, calls: {"accepted": True})
        engine = self.engine([first, second])
        result = engine.execute(mission(), "hello", {}, lambda x: x["accepted"])
        self.assertEqual(result.provider, "backup")
        self.assertEqual(result.attempts, 3)

    def test_policy_refusal_is_preserved_and_falls_back(self):
        refusing = MockProvider("refuse", lambda req, calls: ProviderFailure(FailureClass.POLICY_REFUSAL, "declined"))
        lawful = MockProvider("lawful", lambda req, calls: {"accepted": True})
        result = self.engine([refusing, lawful]).execute(mission(), "bounded", {}, lambda x: x["accepted"])
        self.assertEqual(result.state, MissionState.COMPLETED)
        self.assertEqual(result.provider, "lawful")

    def test_malformed_provider_quarantined(self):
        malformed = MockProvider("bad", lambda req, calls: "not-json")
        backup = MockProvider("good")
        engine = self.engine([malformed, backup])
        result = engine.execute(mission(), "hello", {}, lambda x: x["accepted"])
        self.assertEqual(result.provider, "good")
        self.assertIn("bad", engine.router.quarantined)

    def test_semantic_failure_quarantines_route(self):
        engine = self.engine([MockProvider("wrong", lambda req, calls: {"accepted": False})])
        result = engine.execute(mission(), "hello", {}, lambda x: x["accepted"])
        self.assertEqual(result.state, MissionState.QUARANTINED)
        self.assertEqual(result.failure_class, FailureClass.SEMANTIC_FAILURE)

    def test_cancellation_prevents_provider_call(self):
        provider = MockProvider("p")
        engine = self.engine([provider])
        engine.cancel("m1")
        result = engine.execute(mission(), "hello", {}, lambda x: True)
        self.assertEqual(result.state, MissionState.CANCELLED)
        self.assertEqual(provider.calls, 0)

    def test_invalid_authority_fails_before_provider(self):
        provider = MockProvider("p")
        result = self.engine([provider]).execute(mission(authority="A9"), "hello", {}, lambda x: True)
        self.assertEqual(result.state, MissionState.FAILED)
        self.assertEqual(provider.calls, 0)

    def test_secret_data_denied_for_openrouter_tool(self):
        policy = PolicyEngine()
        decision = policy.evaluate(mission(data_class="secret", tools=("openrouter",)), tool="openrouter")
        self.assertFalse(decision.allowed)

    def test_external_effects_default_denied(self):
        broker = EffectBroker()
        with self.assertRaises(EffectRejected):
            broker.execute(mission_id="m", action="send", payload={}, operation=lambda: "sent",
                           verify=lambda x: True, external=True)

    def test_idempotent_effect_executes_once(self):
        broker = EffectBroker(external_effects_enabled=True)
        calls = []
        operation = lambda: calls.append(1) or {"ok": True}
        kwargs = dict(mission_id="m", action="write", payload={"x": 1}, operation=operation,
                      verify=lambda x: x["ok"], external=True)
        one = broker.execute(**kwargs)
        two = broker.execute(**kwargs)
        self.assertEqual(one, two)
        self.assertEqual(len(calls), 1)

    def test_failed_readback_never_commits(self):
        broker = EffectBroker(external_effects_enabled=True)
        with self.assertRaises(EffectRejected):
            broker.execute(mission_id="m", action="write", payload={}, operation=lambda: {"ok": False},
                           verify=lambda x: x["ok"], external=True)

    def test_ledger_tampering_detected(self):
        ledger = JsonlLedger(Path(self.tmp.name) / "tamper.jsonl")
        ledger.append("m", "ONE", {})
        path = Path(self.tmp.name) / "tamper.jsonl"
        path.write_text(path.read_text().replace('"ONE"', '"TWO"'))
        with self.assertRaises(LedgerIntegrityError):
            ledger.verify()


if __name__ == "__main__":
    unittest.main()

