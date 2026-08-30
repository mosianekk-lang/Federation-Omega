from __future__ import annotations

from hashlib import sha256
import unittest

from federation.bubbles_cognitive_court import (
    CognitiveCourt,
    CompensationPlan,
    GuardrailVerdict,
    RouteCandidate,
)
from federation.bubbles_hyperperformance import (
    CurrentStateLease,
    IdempotencyEnvelope,
    IdempotencyLedger,
    TraceSpine,
)


NOW = "2026-08-30T22:00:00+00:00"


def lease(*, expiry: str = "2026-08-31T22:00:00+00:00", authority: str = "formation") -> CurrentStateLease:
    return CurrentStateLease(
        entity_id="mission-1",
        field_id="authority",
        value="A2",
        authority_source=authority,
        observed_at="2026-08-30T21:00:00+00:00",
        fresh_until=expiry,
        proof_refs=("proof:lease",),
        source_event_id="event-1",
    )


def envelope(operation_id: str = "op-1", command: str = "command-a") -> IdempotencyEnvelope:
    return IdempotencyEnvelope(
        operation_id=operation_id,
        command_sha256=sha256(command.encode()).hexdigest(),
        target_alias="provider-shadow",
        action_scope="shadow-only",
        effect_class="SHADOW_WRITE",
        expires_at="2026-08-31T22:00:00+00:00",
    )


def compensation(operation_id: str = "op-1") -> CompensationPlan:
    return CompensationPlan(
        compensation_id="comp-1",
        operation_id=operation_id,
        action_ref="rollback:shadow",
        idempotency_key="comp-key-1",
        registered_before_effect=True,
    )


def candidate(route_id: str, **changes: object) -> RouteCandidate:
    values: dict[str, object] = {
        "route_id": route_id,
        "objective_fit": 0.8,
        "evidence_strength": 0.8,
        "information_gain": 0.7,
        "proof_closure": 0.8,
        "risk": 0.1,
        "burden": 0.0,
        "latency_ms": 10,
        "proof_refs": (f"proof:{route_id}",),
    }
    values.update(changes)
    return RouteCandidate(**values)


class CognitiveCourtTests(unittest.TestCase):
    def test_selects_highest_proof_adjusted_route(self) -> None:
        receipt = CognitiveCourt().evaluate(
            mission_id="mission-1",
            trace_id="trace-1",
            now=NOW,
            candidates=(candidate("weak", evidence_strength=0.2), candidate("strong", evidence_strength=0.95)),
        )
        self.assertEqual("strong", receipt.selected_route_id)
        self.assertEqual("SELECTED_NO_EFFECT", receipt.state)
        self.assertFalse(receipt.effect_authorized)

    def test_tie_break_is_deterministic(self) -> None:
        receipt = CognitiveCourt().evaluate(
            mission_id="mission-1", trace_id="trace-2", now=NOW, candidates=(candidate("b"), candidate("a"))
        )
        self.assertEqual("a", receipt.selected_route_id)

    def test_missing_lease_holds_route(self) -> None:
        receipt = CognitiveCourt().evaluate(
            mission_id="mission-1",
            trace_id="trace-3",
            now=NOW,
            candidates=(candidate("needs-proof", required_lease_ids=("authority",)),),
        )
        self.assertEqual("HOLD", receipt.state)
        self.assertIn("LEASE_MISSING:authority", receipt.counterfactuals[0].reasons)

    def test_stale_lease_holds_route(self) -> None:
        receipt = CognitiveCourt().evaluate(
            mission_id="mission-1",
            trace_id="trace-4",
            now=NOW,
            candidates=(candidate("stale", required_lease_ids=("authority",), expected_authority="formation"),),
            leases={"authority": lease(expiry="2026-08-30T21:30:00+00:00")},
        )
        self.assertEqual("HOLD", receipt.state)
        self.assertTrue(receipt.counterfactuals[0].reasons[0].startswith("LEASE_INVALID"))

    def test_authority_mismatch_holds_route(self) -> None:
        receipt = CognitiveCourt().evaluate(
            mission_id="mission-1",
            trace_id="trace-5",
            now=NOW,
            candidates=(candidate("wrong-authority", required_lease_ids=("authority",), expected_authority="formation"),),
            leases={"authority": lease(authority="untrusted")},
        )
        self.assertEqual("HOLD", receipt.state)

    def test_effect_requires_compensation(self) -> None:
        receipt = CognitiveCourt().evaluate(
            mission_id="mission-1",
            trace_id="trace-6",
            now=NOW,
            candidates=(candidate("effect", effect_class="SHADOW_WRITE", idempotency=envelope()),),
        )
        self.assertEqual("HOLD", receipt.state)
        self.assertIn("COMPENSATION_REQUIRED_BEFORE_EFFECT", receipt.counterfactuals[0].reasons)

    def test_effect_is_only_ready_for_formation(self) -> None:
        receipt = CognitiveCourt().evaluate(
            mission_id="mission-1",
            trace_id="trace-7",
            now=NOW,
            candidates=(
                candidate(
                    "effect",
                    effect_class="SHADOW_WRITE",
                    idempotency=envelope(),
                    compensation=compensation(),
                ),
            ),
        )
        self.assertEqual("READY_FOR_FORMATION", receipt.state)
        self.assertFalse(receipt.effect_authorized)

    def test_input_tripwire_blocks(self) -> None:
        receipt = CognitiveCourt().evaluate(
            mission_id="mission-1",
            trace_id="trace-8",
            now=NOW,
            candidates=(candidate("blocked", guardrails=(GuardrailVerdict("payload", "INPUT", False, True),)),),
        )
        self.assertEqual("HOLD", receipt.state)
        self.assertIn("GUARDRAIL_INPUT_payload", receipt.counterfactuals[0].reasons)

    def test_idempotency_conflict_holds_second_command(self) -> None:
        ledger = IdempotencyLedger()
        first_court = CognitiveCourt(idempotency_ledger=ledger)
        first = candidate("first", effect_class="SHADOW_WRITE", idempotency=envelope(), compensation=compensation())
        first_court.evaluate(mission_id="mission-1", trace_id="trace-9a", now=NOW, candidates=(first,))
        conflict = candidate(
            "second",
            effect_class="SHADOW_WRITE",
            idempotency=envelope(command="changed-command"),
            compensation=compensation(),
        )
        second_court = CognitiveCourt(idempotency_ledger=ledger)
        receipt = second_court.evaluate(mission_id="mission-2", trace_id="trace-9b", now=NOW, candidates=(conflict,))
        self.assertEqual("HOLD", receipt.state)
        self.assertIn("IDEMPOTENCY_REJECT_CONFLICT", receipt.counterfactuals[0].reasons)

    def test_idempotency_conflict_advances_to_safe_fallback(self) -> None:
        ledger = IdempotencyLedger()
        CognitiveCourt(idempotency_ledger=ledger).evaluate(
            mission_id="mission-1",
            trace_id="trace-9c",
            now=NOW,
            candidates=(candidate("seed", effect_class="SHADOW_WRITE", idempotency=envelope(), compensation=compensation()),),
        )
        conflicted = candidate(
            "conflicted",
            objective_fit=1.0,
            effect_class="SHADOW_WRITE",
            idempotency=envelope(command="changed-command"),
            compensation=compensation(),
        )
        fallback = candidate("safe-fallback", objective_fit=0.2)
        receipt = CognitiveCourt(idempotency_ledger=ledger).evaluate(
            mission_id="mission-2",
            trace_id="trace-9d",
            now=NOW,
            candidates=(conflicted, fallback),
        )
        self.assertEqual("safe-fallback", receipt.selected_route_id)
        self.assertEqual("SELECTED_NO_EFFECT", receipt.state)

    def test_trace_contains_metadata_not_sensitive_payload(self) -> None:
        spine = TraceSpine()
        CognitiveCourt(trace_spine=spine).evaluate(
            mission_id="mission-1", trace_id="trace-10", now=NOW, candidates=(candidate("safe"),)
        )
        self.assertEqual(2, len(spine.snapshot()))
        self.assertTrue(all(not event.sensitive_payload_present for event in spine.snapshot()))

    def test_receipt_and_trace_are_deterministic(self) -> None:
        first = CognitiveCourt().evaluate(
            mission_id="mission-1", trace_id="trace-11", now=NOW, candidates=(candidate("a"), candidate("b"))
        )
        second = CognitiveCourt().evaluate(
            mission_id="mission-1", trace_id="trace-11", now=NOW, candidates=(candidate("a"), candidate("b"))
        )
        self.assertEqual(first.trace_digest, second.trace_digest)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)

    def test_counterfactual_delta_is_preserved(self) -> None:
        receipt = CognitiveCourt().evaluate(
            mission_id="mission-1",
            trace_id="trace-12",
            now=NOW,
            candidates=(candidate("high", objective_fit=1.0), candidate("low", objective_fit=0.1)),
        )
        low = next(value for value in receipt.counterfactuals if value.route_id == "low")
        self.assertGreater(low.delta_from_selected or 0, 0)

    def test_permanent_failure_never_retries(self) -> None:
        policy = CognitiveCourt.classify_failure("PERMANENT")
        self.assertFalse(policy.retry_allowed)
        self.assertEqual(0, policy.max_attempts)

    def test_intermittent_failure_has_bounded_retry(self) -> None:
        policy = CognitiveCourt.classify_failure("INTERMITTENT")
        self.assertTrue(policy.retry_allowed)
        self.assertEqual(2, policy.max_attempts)
        self.assertEqual((5,), policy.backoff_seconds)

    def test_outcome_deviation_is_not_auto_promoted(self) -> None:
        learning = CognitiveCourt.evaluate_outcome(
            route_id="route-a",
            expected_fruit=0.9,
            observed_fruit=0.2,
            failure_class="CONTRADICTION",
            proof_refs=("proof:outcome",),
        )
        self.assertEqual(-0.7, learning.claim_fruit_delta)
        self.assertFalse(learning.auto_promoted)
        self.assertTrue(learning.failure_policy.compensation_required)

    def test_empty_candidates_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "COURT_CANDIDATE_REQUIRED"):
            CognitiveCourt().evaluate(mission_id="mission-1", trace_id="trace-13", now=NOW, candidates=())


if __name__ == "__main__":
    unittest.main()

