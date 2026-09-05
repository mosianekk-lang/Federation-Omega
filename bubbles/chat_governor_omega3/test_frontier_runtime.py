from __future__ import annotations

import tempfile
import unittest

from bubbles.chat_governor_omega3.frontier_runtime import (
    ActivityRequest,
    AdaptiveParallelismController,
    CapabilityCatalogCache,
    ContextIsolationBroker,
    DurableActivityBoundary,
    HookContext,
    HookEvent,
    HookOutcome,
    LifecycleHookBus,
    OwnerAttentionGovernor,
    OwnerSignal,
    OwnerSignalKind,
    ParallelismObservation,
    StablePrefixCompiler,
)
from bubbles.chat_governor_omega3.state import DurableState


class LifecycleHookBusTests(unittest.TestCase):
    def test_priority_and_payload_transform_are_deterministic(self):
        bus = LifecycleHookBus()
        bus.register(name="b", event=HookEvent.PRE_TOOL_USE, priority=20, handler=lambda c: HookOutcome(payload={**c.payload, "b": 2}))
        bus.register(name="a", event=HookEvent.PRE_TOOL_USE, priority=10, handler=lambda c: HookOutcome(payload={**c.payload, "a": 1}))
        receipt = bus.dispatch(HookContext(HookEvent.PRE_TOOL_USE, "m1", action="READ", payload={"x": 0}))
        self.assertTrue(receipt.allowed)
        self.assertEqual(receipt.executed_hooks, ("a", "b"))
        self.assertEqual(receipt.transformed_payload, {"x": 0, "a": 1, "b": 2})
        self.assertEqual(receipt.receipt_sha256, bus.dispatch(HookContext(HookEvent.PRE_TOOL_USE, "m1", action="READ", payload={"x": 0})).receipt_sha256)

    def test_fail_closed_hook_blocks_before_tool(self):
        bus = LifecycleHookBus()
        bus.register(name="authority", event=HookEvent.PRE_TOOL_USE, handler=lambda c: HookOutcome(False, reasons=("AUTHORITY_MISSING",)))
        receipt = bus.dispatch(HookContext(HookEvent.PRE_TOOL_USE, "m1", action="WRITE"))
        self.assertFalse(receipt.allowed)
        self.assertIn("HOOK_BLOCK:authority", receipt.reasons)

    def test_hook_exception_fails_closed_when_configured(self):
        bus = LifecycleHookBus()
        def explode(_):
            raise RuntimeError("boom")
        bus.register(name="guard", event=HookEvent.PRE_TOOL_USE, handler=explode, fail_closed=True)
        receipt = bus.dispatch(HookContext(HookEvent.PRE_TOOL_USE, "m1", action="WRITE"))
        self.assertFalse(receipt.allowed)
        self.assertIn("HOOK_FAIL_CLOSED:guard", receipt.reasons)


class OwnerAttentionTests(unittest.TestCase):
    def setUp(self):
        self.governor = OwnerAttentionGovernor()

    def test_recoverable_progress_noise_is_hidden(self):
        decision = self.governor.decide(OwnerSignal(OwnerSignalKind.DIAGNOSTIC, "retrying", recoverable=True, unresolved=True))
        self.assertFalse(decision.owner_visible)
        self.assertEqual(decision.report_mode, "INTERNAL_ONLY")

    def test_verified_milestone_is_visible(self):
        decision = self.governor.decide(OwnerSignal(OwnerSignalKind.VERIFIED_MILESTONE, "PR merged", verified=True, proof_refs=("run:1",)))
        self.assertTrue(decision.owner_visible)
        self.assertEqual(decision.report_mode, "VERIFIED_MILESTONE")

    def test_material_risk_cannot_be_hidden(self):
        decision = self.governor.decide(OwnerSignal(OwnerSignalKind.MATERIAL_RISK, "proof failed", material=True, unresolved=True))
        self.assertTrue(decision.owner_visible)

    def test_owner_decision_cannot_be_suppressed(self):
        decision = self.governor.decide(OwnerSignal(OwnerSignalKind.PROGRESS, "approval required", owner_decision_required=True))
        self.assertTrue(decision.owner_visible)
        self.assertEqual(decision.report_mode, "PRECISE_OWNER_DECISION")


class ContextIsolationTests(unittest.TestCase):
    def test_optional_context_is_omitted_before_required_context(self):
        broker = ContextIsolationBroker(max_packet_bytes=900, max_merge_bytes=600)
        packet = broker.compile(
            task_id="t1",
            objective="find exact state",
            requirements=("proof",),
            constraints=("read only",),
            source_refs=("src:1",),
            evidence_summaries=("e" * 1000,),
            recent_failures=("f" * 1000,),
            notes=("n" * 1000,),
        )
        self.assertLessEqual(packet.byte_count, 900)
        self.assertIn("evidence_summaries", packet.omitted_sections)
        self.assertEqual(packet.body["requirements"], ["proof"])

    def test_raw_side_task_payload_cannot_reenter_parent_context(self):
        broker = ContextIsolationBroker()
        with self.assertRaisesRegex(ValueError, "RAW_SIDE_TASK_CONTEXT_PROHIBITED"):
            broker.merge_result({"summary": "ok", "raw_tool_output": "huge"})
        merged = broker.merge_result({"summary": "ok", "proof_refs": ["p1"], "artifact_refs": ["a1"], "ignored": "x"})
        self.assertNotIn("ignored", merged)


class CapabilityCatalogCacheTests(unittest.TestCase):
    def test_catalog_is_sorted_freshness_bound_and_non_authoritative(self):
        cache = CapabilityCatalogCache()
        entry = cache.put(provider="p", capabilities=("write", "read", "read"), source_fingerprint="abc", now=10.0, ttl_ms=1000, authority_ceiling="A0_READ_ONLY")
        self.assertEqual(entry.capabilities, ("read", "write"))
        hit = cache.get(provider="p", now=10.5, required=("read",))
        self.assertEqual(hit.state, "HIT")
        self.assertEqual(hit.authority_ceiling, "A0_READ_ONLY")
        self.assertEqual(cache.get(provider="p", now=11.0).state, "STALE")


class DurableActivityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.tmp.close()
        self.state = DurableState(self.tmp.name)
        self.boundary = DurableActivityBoundary(self.state)

    def test_verified_result_replays_without_provider_reexecution(self):
        request = ActivityRequest("a1", "m1", "drive", "READ", "digest")
        self.assertEqual(self.boundary.admit(request).state, "EXECUTE_ACTIVITY")
        self.boundary.record_result(request, success=True, semantic_ok=True, result_ref="proof:drive:1")
        replay = self.boundary.admit(request)
        self.assertFalse(replay.execute)
        self.assertEqual(replay.state, "REPLAY_RECORDED_RESULT")
        self.assertEqual(replay.result_ref, "proof:drive:1")

    def test_divergent_replay_is_rejected(self):
        first = ActivityRequest("a1", "m1", "drive", "READ", "digest")
        self.boundary.record_result(first, success=True, semantic_ok=True, result_ref="p")
        second = ActivityRequest("a1", "m1", "drive", "READ", "other")
        self.assertEqual(self.boundary.admit(second).state, "REJECT_DIVERGENT_REPLAY")

    def test_effectful_activity_needs_explicit_authority_and_readback(self):
        no_auth = ActivityRequest("a2", "m1", "github", "WRITE", "d", effectful=True)
        self.assertEqual(self.boundary.admit(no_auth).state, "HOLD_AUTHORIZATION_REQUIRED")
        no_readback = ActivityRequest("a3", "m1", "github", "WRITE", "d", effectful=True, authorization_ref="HMC:x", readback_required=False)
        self.assertEqual(self.boundary.admit(no_readback).state, "HOLD_READBACK_REQUIRED")


class ParallelismTests(unittest.TestCase):
    def test_effectful_lanes_are_single_flight(self):
        controller = AdaptiveParallelismController()
        decision = controller.decide(ParallelismObservation(8, 3, 0.2, 0.01))
        self.assertEqual(decision.effectful_max_workers, 1)
        self.assertGreater(decision.read_only_max_workers, 1)

    def test_context_pressure_sheds_read_fanout(self):
        controller = AdaptiveParallelismController()
        decision = controller.decide(ParallelismObservation(8, 0, 0.9, 0.1))
        self.assertEqual(decision.read_only_max_workers, 1)


class StablePrefixTests(unittest.TestCase):
    def test_volatile_changes_do_not_break_stable_prefix_digest(self):
        compiler = StablePrefixCompiler()
        p1 = compiler.compile({"doctrine": "same", "schema": "v1"}, {"evidence": "a"})
        p2 = compiler.compile({"schema": "v1", "doctrine": "same"}, {"evidence": "b"})
        self.assertEqual(p1.stable_digest, p2.stable_digest)
        self.assertNotEqual(p1.volatile_suffix, p2.volatile_suffix)


if __name__ == "__main__":
    unittest.main()
