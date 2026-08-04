from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from authority_snapshot import parse_utc
from provider_reconciliation_challenge import (
    ChallengeBoundMockProviderAdapter,
    ChallengeBoundProviderDispatchCommercialControlPlane,
)
from provider_dispatch_outcome_reconciliation import OUTCOME_COMPLETED, OUTCOME_NO_EFFECT
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def shift(seconds: int) -> str:
    return (parse_utc(NOW) + timedelta(seconds=seconds)).isoformat().replace(
        "+00:00", "Z"
    )


class ProviderReconciliationChallengeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def plane_with_dispatch(self, object_id: str):
        bootstrap = ChallengeBoundProviderDispatchCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        lead_id = object_id.replace("QUOTE", "LEAD")
        bootstrap.create_lead(lead_id, "org", "inbound", "delay")
        bootstrap.create_quote_draft(
            object_id, lead_id, "AO-PILOT", "ZAR", 560000.0, 12
        )
        subject = bootstrap.quote_authority_subject(object_id)
        owner = owner_receipt(
            "OWNER-" + object_id,
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = ChallengeBoundProviderDispatchCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        plane.approve_quote(
            object_id, owner_decision_receipt_id=owner.receipt_id, now=NOW
        )
        prepared = plane.prepare_provider_dispatch(
            action="quote_approval",
            object_id=object_id,
            provider_domain="reference_provider",
            operation="dry_run_provider_reconciliation_challenge_contract",
            payload={"object_id": object_id, "mode": "challenge-only"},
            now=NOW,
        )
        return plane, owner, prepared

    def quarantine(self, plane, prepared):
        claim = plane.claim_provider_dispatch(
            prepared["dispatch_id"],
            worker_id="worker-a",
            lease_seconds=5,
            now=NOW,
        )
        plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"],
            claim_token=claim["claim_token"],
            now=shift(1),
        )
        envelope = plane.provider_dispatch_attempt_envelope(
            prepared["dispatch_id"],
            claim_token=claim["claim_token"],
            now=shift(1),
        )
        plane.record_provider_dispatch_submission(
            prepared["dispatch_id"],
            claim_token=claim["claim_token"],
            now=shift(2),
        )
        with self.assertRaisesRegex(RuntimeError, "reconciliation required"):
            plane.claim_provider_dispatch(
                prepared["dispatch_id"],
                worker_id="worker-b",
                lease_seconds=60,
                now=shift(6),
            )
        return claim, envelope

    def test_challenge_is_durable_idempotent_and_attempt_bound(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-CHALLENGE-BIND")
        _, envelope = self.quarantine(plane, prepared)
        first = plane.issue_provider_reconciliation_challenge(
            prepared["dispatch_id"], ttl_seconds=60, now=shift(6)
        )
        second = plane.issue_provider_reconciliation_challenge(
            prepared["dispatch_id"], ttl_seconds=60, now=shift(7)
        )
        self.assertEqual(first, second)
        self.assertEqual(first["attempt_envelope_sha256"], envelope["record_sha256"])
        self.assertEqual(first["claim_reference"], envelope["claim_reference"])
        self.assertEqual(first["fencing_epoch"], envelope["fencing_epoch"])

    def test_unchallenged_v14_evidence_fails_closed(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-CHALLENGE-REQUIRED")
        _, envelope = self.quarantine(plane, prepared)
        adapter = ChallengeBoundMockProviderAdapter("reference_provider")
        raw = adapter.reconcile(envelope, outcome=OUTCOME_NO_EFFECT)
        with self.assertRaisesRegex(RuntimeError, "challenge required"):
            plane.resolve_provider_dispatch_outcome(
                prepared["dispatch_id"], raw, now=shift(7)
            )

    def test_expired_challenge_is_superseded_and_old_evidence_rejected(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-CHALLENGE-EXPIRE")
        _, envelope = self.quarantine(plane, prepared)
        adapter = ChallengeBoundMockProviderAdapter("reference_provider")
        first = plane.issue_provider_reconciliation_challenge(
            prepared["dispatch_id"], ttl_seconds=5, now=shift(6)
        )
        old = adapter.reconcile_with_challenge(
            envelope, first, outcome=OUTCOME_NO_EFFECT, observed_at=shift(7)
        )
        second = plane.issue_provider_reconciliation_challenge(
            prepared["dispatch_id"], ttl_seconds=60, now=shift(12)
        )
        self.assertNotEqual(first["challenge_reference"], second["challenge_reference"])
        with self.assertRaisesRegex(RuntimeError, "challenge binding invalid"):
            plane.resolve_provider_dispatch_outcome(
                prepared["dispatch_id"], old, now=shift(13)
            )

    def test_no_effect_resolution_consumes_challenge_and_releases_retry(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-CHALLENGE-NONE")
        _, envelope = self.quarantine(plane, prepared)
        adapter = ChallengeBoundMockProviderAdapter("reference_provider")
        challenge = plane.issue_provider_reconciliation_challenge(
            prepared["dispatch_id"], ttl_seconds=60, now=shift(6)
        )
        evidence = adapter.reconcile_with_challenge(
            envelope, challenge, outcome=OUTCOME_NO_EFFECT, observed_at=shift(7)
        )
        resolved = plane.resolve_provider_dispatch_outcome(
            prepared["dispatch_id"], evidence, now=shift(8)
        )
        self.assertEqual(resolved["outcome"], OUTCOME_NO_EFFECT)
        self.assertEqual(
            resolved["challenge_consumption_event"]["event_type"],
            "CHALLENGE_CONSUMED",
        )
        next_claim = plane.claim_provider_dispatch(
            prepared["dispatch_id"],
            worker_id="worker-b",
            lease_seconds=60,
            now=shift(9),
        )
        started = plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"],
            claim_token=next_claim["claim_token"],
            now=shift(10),
        )
        self.assertEqual(started["fencing_epoch"], 2)

    def test_completed_resolution_is_single_use_and_restart_safe(self) -> None:
        plane, owner, prepared = self.plane_with_dispatch("QUOTE-CHALLENGE-DONE")
        _, envelope = self.quarantine(plane, prepared)
        adapter = ChallengeBoundMockProviderAdapter("reference_provider")
        adapter.execute(envelope)
        challenge = plane.issue_provider_reconciliation_challenge(
            prepared["dispatch_id"], ttl_seconds=60, now=shift(6)
        )
        evidence = adapter.reconcile_with_challenge(
            envelope, challenge, outcome=OUTCOME_COMPLETED, observed_at=shift(7)
        )
        resolved = plane.resolve_provider_dispatch_outcome(
            prepared["dispatch_id"], evidence, now=shift(8)
        )
        self.assertEqual(resolved["outcome"], OUTCOME_COMPLETED)
        restarted = ChallengeBoundProviderDispatchCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        readback = restarted.provider_reconciliation_challenge_readback()
        self.assertEqual(readback["challenges_issued"], 1)
        self.assertEqual(readback["challenges_consumed"], 1)
        self.assertEqual(readback["resolved_completed"], 1)
        self.assertFalse(readback["provider_native_reconciliation_proven"])
        with self.assertRaisesRegex(RuntimeError, "no unresolved outcome"):
            restarted.resolve_provider_dispatch_outcome(
                prepared["dispatch_id"], evidence, now=shift(9)
            )

    def test_challenge_history_tamper_fails_closed(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-CHALLENGE-TAMPER")
        self.quarantine(plane, prepared)
        plane.issue_provider_reconciliation_challenge(
            prepared["dispatch_id"], ttl_seconds=60, now=shift(6)
        )
        state = plane._read_state()
        history = state["provider_reconciliation_challenge_history"][
            prepared["dispatch_id"]
        ]
        history[0]["expires_at"] = shift(600)
        plane._write_state(state)
        with self.assertRaisesRegex(RuntimeError, "history hash invalid"):
            plane.provider_reconciliation_challenge_readback()


if __name__ == "__main__":
    unittest.main()
