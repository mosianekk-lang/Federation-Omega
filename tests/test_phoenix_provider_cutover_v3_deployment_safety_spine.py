from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "realityguard_v0.4.0" / "src"))

from federation.orchestration import (
    CapabilityRoute,
    CapabilitySelector,
    ConcurrencyGuard,
    ExecutionEnvelope,
    FailureMemoryRecord,
    MissionLease,
    PreWriteFence,
    WorkstreamObservation,
)
from realityguard import ExecutionGuard, GuardDecision

SPEC = importlib.util.spec_from_file_location(
    "provider_airlock_activate_spine", ROOT / "phoenix" / "provider_airlock_activate.py"
)
assert SPEC and SPEC.loader
AIRLOCK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AIRLOCK
SPEC.loader.exec_module(AIRLOCK)

MAIN = "a" * 40
NEXT = "b" * 40
ISSUED = "2026-08-29T18:00:00+00:00"
EXPIRES = "2026-08-29T19:00:00+00:00"
NOW = "2026-08-29T18:30:00+00:00"


def lease() -> MissionLease:
    return MissionLease.create(
        mission_id="SOVARA-DEPLOYMENT-20260829",
        lane_id="safety-spine",
        holder_id="federation",
        base_main_sha=MAIN,
        lease_epoch=1,
        path_scope=["sovara", "federation/orchestration", "governance", "realityguard_v0.4.0"],
        issued_at=ISSUED,
        expires_at=EXPIRES,
    )


def effect_request() -> dict:
    return {
        "schema_version": "realityguard.execution-guard.v1",
        "request": {
            "request_id": "DEPLOY-1",
            "tool_name": "provider.deploy",
            "operation": "deploy",
            "effect_class": "DEPLOYMENT",
            "target": {"service": "synthetic"},
            "payload": {"artifact_ref": "sha256:" + "a" * 64},
            "expected_fruit": {"provider_state": "CANARY_READY"},
            "idempotency_key": "deploy-synthetic-1",
        },
        "authority": {
            "formation_permit_consumed": True,
            "permit_single_use": True,
            "action_binding_matches": True,
            "proof_ref": "formation:synthetic",
        },
        "route": {
            "readback_supported": True,
            "semantic_canary_verified": True,
            "canary_proof_ref": "canary:synthetic",
            "inline_binary_supported": False,
            "inline_binary_canary_verified": False,
        },
        "retry": {"attempt": 1, "previous_attempts": [], "exact_repair": ""},
    }


class DeploymentSafetySpineTests(unittest.TestCase):
    def test_clean_current_main_allows_fenced_internal_write(self):
        item = lease()
        decision = ConcurrencyGuard().evaluate(
            lease=item, current_main_sha=MAIN, now=NOW
        )
        self.assertTrue(decision.write_allowed)
        receipt = PreWriteFence().authorise(
            lease=item,
            decision=decision,
            current_main_sha=MAIN,
            intended_paths=["sovara/creative/router.py"],
        )
        self.assertTrue(receipt.allowed)
        self.assertEqual("PREWRITE_FENCE_VERIFIED", receipt.reason)

    def test_moving_main_never_inherits_old_write_authority(self):
        decision = ConcurrencyGuard().evaluate(
            lease=lease(),
            current_main_sha=NEXT,
            now=NOW,
            main_changed_paths=["docs/unrelated.md"],
        )
        self.assertFalse(decision.write_allowed)
        self.assertEqual("MAIN_DRIFT_FAST_RECONVERGE", decision.state)

    def test_overlapping_workstream_is_serialized(self):
        other = WorkstreamObservation.create(
            workstream_id="other",
            base_sha=MAIN,
            head_sha=NEXT,
            paths=["sovara/creative"],
        )
        decision = ConcurrencyGuard().evaluate(
            lease=lease(), current_main_sha=MAIN, now=NOW, active_workstreams=[other]
        )
        self.assertEqual("ACTIVE_WORKSTREAM_OVERLAP_HOLD", decision.state)
        self.assertFalse(decision.write_allowed)

    def test_dynamic_failure_memory_blocks_unchanged_retry_without_stale_global_constant(self):
        failed = FailureMemoryRecord(
            fingerprint="CURRENT_PROVIDER_FAILURE",
            route_id="GITHUB_TO_PROVIDER",
            status="OPEN",
            failure_proof_ref="run:1",
            retry_condition="require newer provider receipt",
        )
        route = CapabilityRoute(
            route_id="GITHUB_TO_PROVIDER",
            capability_id="PROVIDER_CANARY",
            reality_state="C4",
            required_reality_state="C3",
            readiness="READY",
            authority_required="A1_INTERNAL",
            proof_ref="source:current",
        )
        selection = CapabilitySelector().select(routes=[route], memories=[failed])
        self.assertEqual("", selection.selected_route_id)
        self.assertIn("GITHUB_TO_PROVIDER", selection.blocked_routes)

    def test_closed_failure_requires_current_recovery_proof_binding(self):
        recovered = FailureMemoryRecord(
            fingerprint="OLD_FAILURE",
            route_id="ROUTE-A",
            status="CLOSED",
            failure_proof_ref="old",
            retry_condition="new proof",
            recovery_proof_ref="provider:recovered",
        )
        blocked = CapabilityRoute(
            route_id="ROUTE-A", capability_id="A", reality_state="C4",
            required_reality_state="C3", readiness="READY",
            authority_required="A1_INTERNAL", proof_ref="source"
        )
        self.assertEqual(
            "",
            CapabilitySelector().select(routes=[blocked], memories=[recovered]).selected_route_id,
        )
        admitted = CapabilityRoute(
            route_id="ROUTE-A", capability_id="A", reality_state="C4",
            required_reality_state="C3", readiness="READY",
            authority_required="A1_INTERNAL", proof_ref="source",
            retry_evidence_refs=("provider:recovered",),
        )
        self.assertEqual(
            "ROUTE-A",
            CapabilitySelector().select(routes=[admitted], memories=[recovered]).selected_route_id,
        )

    def test_completion_claim_requires_authorization_execution_readback_and_receipt(self):
        partial = ExecutionEnvelope(
            mission_id="M", operation_id="O", authorization_ref="auth", execution_ref="exec"
        )
        self.assertFalse(partial.completion_claim_allowed)
        complete = ExecutionEnvelope(
            mission_id="M", operation_id="O", authorization_ref="auth", execution_ref="exec",
            target_readback_ref="readback", expected_target_digest="x",
            observed_target_digest="x", receipt_ref="receipt",
        )
        self.assertTrue(complete.completion_claim_allowed)

    def test_provider_airlock_requires_full_three_check_release_court(self):
        ruleset = json.loads(
            (ROOT / "governance" / "federation_omega_main_airlock.ruleset.json").read_text()
        )
        AIRLOCK.validate_ruleset(ruleset)
        status = next(x for x in ruleset["rules"] if x["type"] == "required_status_checks")
        contexts = [x["context"] for x in status["parameters"]["required_status_checks"]]
        self.assertEqual(["admission", "contract", "scan"], contexts)

    def test_realityguard_blocks_missing_effect_authority(self):
        payload = effect_request()
        payload["authority"]["formation_permit_consumed"] = False
        self.assertEqual(
            GuardDecision.BLOCK_INVALID_AUTHORITY,
            ExecutionGuard().preflight_tool_call(payload).decision,
        )

    def test_realityguard_transport_or_receipt_alone_cannot_release_deployment_claim(self):
        guard = ExecutionGuard()
        preflight = guard.preflight_tool_call(effect_request())
        record = guard.observe_dispatch(preflight, {"transport_succeeded": True})
        self.assertFalse(guard.guard_claim_release(record, "CANARY_READY")["claim_authorized"])
        record = guard.observe_dispatch(preflight, {
            "transport_succeeded": True,
            "provider_receipt": {
                "provider_id": "provider-1",
                "request_fingerprint": preflight.request_fingerprint,
                "current": True,
            },
        })
        self.assertFalse(guard.guard_claim_release(record, "CANARY_READY")["claim_authorized"])

    def test_realityguard_releases_only_independently_readback_state(self):
        guard = ExecutionGuard()
        preflight = guard.preflight_tool_call(effect_request())
        record = guard.observe_dispatch(preflight, {
            "transport_succeeded": True,
            "provider_receipt": {
                "provider_id": "provider-1",
                "request_fingerprint": preflight.request_fingerprint,
                "current": True,
                "proof_ref": "provider:receipt",
            },
            "semantic_readback": {
                "current": True,
                "independent": True,
                "matches_expected": True,
                "verified_states": ["CANARY_READY"],
                "proof_ref": "provider:readback",
            },
        })
        self.assertTrue(guard.guard_claim_release(record, "CANARY_READY")["claim_authorized"])
        self.assertFalse(guard.guard_claim_release(record, "PRODUCTION")["claim_authorized"])


if __name__ == "__main__":
    unittest.main()
