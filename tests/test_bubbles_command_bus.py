import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from bubbles.command_bus import build_receipt
from bubbles.control_plane import ActionRequest, BubblesControlPlane, EffectClass


HEAD = "b70244dd2eadb28ddab5cb5596507d9081b1c2df"
FIXED_NOW = datetime(2026, 9, 2, 14, 0, 0, tzinfo=timezone.utc)


class BubblesCommandBusTests(unittest.TestCase):
    def command(self, **overrides):
        base = {
            "schema": "BUBBLES-CONTROL-COMMAND-V1",
            "adapter_id": "bubbles_command_bus",
            "action": "canary",
            "effect": "READ",
            "target_alias": "GITHUB_ACTIONS_A0_A1",
            "payload": {"message": "CHATGPT_TO_ACTIONS_CANARY"},
        }
        base.update(overrides)
        return base

    def run_command(self, command, actor="mosianekk-lang"):
        return build_receipt(
            json.dumps(command),
            actor=actor,
            event_name="pull_request",
            source_ref="PR-CANARY",
        )

    def recovery_command(self, event, **payload_overrides):
        payload = {"event": event, **payload_overrides}
        return self.command(
            action="recover_chat_failure",
            effect="READ",
            target_alias="EVIDENCEOPS_CFRE_LOCAL",
            payload=payload,
        )

    def edpf_payload(self):
        return {
            "cycle_id": "EDPF-BUBBLES-HOST-CYCLE-001",
            "mission_id": "mission-bubbles-edpf-host-001",
            "system_source_head_sha": HEAD,
            "mission_snapshot_digest": "sha256:bubbles-edpf-host-snapshot-001",
            "domain": "bubbles_command_bus",
            "matter_scope": "GLOBAL",
            "sensitivity": "PUBLIC_SAFE",
            "claims": [
                {
                    "claim_id": "claim:bubbles-canary-success",
                    "kind": "HYPOTHESIS",
                    "statement": "A later hosted Bubbles command-bus canary will complete successfully.",
                    "probability": 0.78,
                    "evidence_refs": [
                        {
                            "evidence_id": "evidence:bubbles-command-source",
                            "evidence_class": "PRIMARY",
                            "source_fingerprint": "github:main:bubbles-command-bus",
                            "freshness": 1.0,
                            "reliability": 0.95,
                            "supports": 0.7,
                        },
                        {
                            "evidence_id": "evidence:bubbles-gate-history",
                            "evidence_class": "AUTHENTICATED_DERIVATIVE",
                            "source_fingerprint": "github:actions:bubbles-gates",
                            "freshness": 0.95,
                            "reliability": 0.9,
                            "supports": 0.65,
                        },
                    ],
                }
            ],
            "options": [
                {
                    "option_id": "option:run-shadow-canary",
                    "expected_value": 0.8,
                    "success_probability": 0.75,
                    "reversibility": 1.0,
                    "information_gain": 0.9,
                    "cost": 0.05,
                    "latency": 0.1,
                    "owner_burden": 0.0,
                    "risk": 0.02,
                    "external_effect": False,
                },
                {
                    "option_id": "option:hold-shadow-canary",
                    "expected_value": 0.2,
                    "success_probability": 1.0,
                    "reversibility": 1.0,
                    "information_gain": 0.0,
                    "cost": 0.0,
                    "latency": 0.0,
                    "owner_burden": 0.0,
                    "risk": 0.0,
                    "external_effect": False,
                },
            ],
            "evidence_candidates": [
                {
                    "candidate_id": "candidate:bubbles-canary-runtime-receipt",
                    "resolves_claim_ids": ["claim:bubbles-canary-success"],
                    "decision_flip_probability": 0.8,
                    "uncertainty_reduction": 0.9,
                    "acquisition_cost": 0.05,
                    "acquisition_risk": 0.02,
                    "freshness_gain": 1.0,
                }
            ],
            "event": "A subsequent Bubbles command-bus canary invoked through the hosted GitHub Actions lane completes with state SUCCESS.",
            "outcome_criterion": "Observed Bubbles receipt has state SUCCESS, request action canary, and execution kind LOCAL_COMMAND_BUS_CANARY.",
            "outcome_observability": 1.0,
            "evidence_refs": ["github:main:bubbles-command-bus", "github:actions:recent-bubbles-gates"],
            "observability_basis_refs": ["github-actions:immutable-bubbles-command-receipt"],
            "prediction_window_seconds": 5,
            "outcome_window_seconds": 900,
            "context": {"route": "existing-bubbles-github-actions-host", "mode": "shadow-no-effect"},
            "outcome_context": {"expected_receipt_kind": "LOCAL_COMMAND_BUS_CANARY"},
            "predictor": {
                "predictor_id": "GPT-5.6-SOL-SESSION",
                "source_fingerprint": "openai:gpt-5.6-sol:chat-session",
                "predictor_version": "gpt-5.6-sol/2026-09-02",
                "provider_backed": False,
                "profile": {"attempts": 0, "brier_sum": 0.0, "absolute_error_sum": 0.0, "resolved_correct": 0},
                "relevance": 0.5,
                "independence": 1.0,
                "expected_information_gain": 0.5,
                "cost": 0.0,
                "latency": 0.1,
            },
            "forecast": {
                "response_id": "EDPF-RESP-BUBBLES-HOST-001",
                "probability": 0.82,
                "expected_value": 0.8,
                "expected_latency": 0.1,
                "expected_owner_burden": 0.0,
                "evidence_refs": ["github:main:bubbles-command-bus", "github:actions:recent-bubbles-gates"],
            },
        }

    def edpf_predict_command(self, **payload_overrides):
        payload = {**self.edpf_payload(), **payload_overrides}
        return self.command(
            action="edpf_shadow_predict",
            effect="READ",
            target_alias="SOVARA_EDPF_LIVING_STATE_SHADOW",
            payload=payload,
        )

    def test_internal_canary_succeeds_without_external_provider_effect(self):
        receipt = self.run_command(self.command())
        self.assertEqual(receipt["state"], "SUCCESS")
        self.assertEqual(receipt["execution"]["kind"], "LOCAL_COMMAND_BUS_CANARY")
        self.assertIn("does not prove Google Cloud", receipt["truth_boundary"])

    def test_edpf_shadow_predict_runs_canonical_chain_and_ingests_explicit_probability(self):
        with patch("bubbles.command_bus._edpf_now", return_value=FIXED_NOW):
            receipt = self.run_command(self.edpf_predict_command())
        self.assertEqual("SUCCESS", receipt["state"])
        execution = receipt["execution"]
        self.assertEqual("EDPF_SHADOW_PREDICTION_HOST", execution["kind"])
        self.assertEqual("PREDICTION_RECORDED", execution["state"])
        self.assertEqual("SEEK_EVIDENCE", execution["decision"]["state"])
        self.assertEqual("FORECAST_QUESTION_READY", execution["bridge"]["state"])
        self.assertEqual(0.82, execution["response"]["probability"])
        self.assertEqual("RUNTIME_READBACK", execution["response"]["proof_maturity"])
        self.assertEqual("APPLIED", execution["prediction_ingress_receipt"]["disposition"])
        self.assertTrue(execution["prediction_ingress_receipt"]["readback_verified"])
        self.assertFalse(execution["forecast_probability_generated_by_host"])
        self.assertTrue(execution["forecast_probability_supplied_by_predictor"])
        self.assertFalse(execution["prediction_accuracy_proven_at_ingress"])
        self.assertEqual(0, execution["external_effects"])
        self.assertIn("does not prove the prediction is true", receipt["truth_boundary"])

    def test_edpf_shadow_predict_holds_instead_of_inventing_when_not_seeking_evidence(self):
        payload = self.edpf_payload()
        payload["claims"][0]["probability"] = 0.99
        with patch("bubbles.command_bus._edpf_now", return_value=FIXED_NOW):
            receipt = self.run_command(self.edpf_predict_command(**payload))
        self.assertEqual("SUCCESS", receipt["state"])
        self.assertEqual("HOLD", receipt["execution"]["state"])
        self.assertFalse(receipt["execution"]["forecast_probability_generated_by_host"])
        self.assertEqual(0, receipt["execution"]["external_effects"])

    def test_edpf_shadow_predict_rejects_provider_backed_predictor_claim(self):
        payload = self.edpf_payload()
        payload["predictor"] = {**payload["predictor"], "provider_backed": True}
        with patch("bubbles.command_bus._edpf_now", return_value=FIXED_NOW):
            receipt = self.run_command(self.edpf_predict_command(**payload))
        self.assertEqual("FAILURE", receipt["state"])
        self.assertIn("non-provider-backed", receipt["reason"])

    def test_edpf_shadow_resolve_replays_prediction_then_applies_observed_canary(self):
        with patch("bubbles.command_bus._edpf_now", return_value=FIXED_NOW):
            predicted = self.run_command(self.edpf_predict_command())
        bundle = predicted["execution"]["portable_resolution_bundle"]
        observed = self.run_command(self.command())
        resolution = self.command(
            action="edpf_shadow_resolve",
            effect="READ",
            target_alias="SOVARA_EDPF_LIVING_STATE_SHADOW",
            payload={
                "prediction_bundle": bundle,
                "observed_bubbles_receipt": observed,
                "observed_receipt_ref": "github-actions:run:canary-001:artifact:receipt",
                "realised_latency": 0.1,
                "realised_owner_burden": 0.0,
            },
        )
        later = datetime(2026, 9, 2, 14, 0, 10, tzinfo=timezone.utc)
        with patch("bubbles.command_bus._edpf_now", return_value=later):
            resolved = self.run_command(resolution)
        self.assertEqual("SUCCESS", resolved["state"])
        execution = resolved["execution"]
        self.assertEqual("EDPF_SHADOW_OUTCOME_HOST", execution["kind"])
        self.assertEqual("OUTCOME_RECORDED", execution["state"])
        self.assertTrue(execution["occurred"])
        self.assertEqual(0.82, execution["forecast_probability"])
        self.assertEqual("APPLIED", execution["prediction_replay_receipt"]["disposition"])
        self.assertEqual("APPLIED", execution["outcome_ingress_receipt"]["disposition"])
        self.assertTrue(execution["outcome_ingress_receipt"]["readback_verified"])
        self.assertFalse(execution["calibration_superiority_proven"])
        self.assertFalse(execution["live_predictor_weight_change_authorized"])
        self.assertEqual(0, execution["external_effects"])

    def test_edpf_shadow_command_cannot_be_promoted_to_write(self):
        receipt = self.run_command(
            self.edpf_predict_command(effect="LOW_RISK_WRITE")
        )
        self.assertEqual("CONSTRAINT", receipt["state"])
        self.assertIn("read-only", receipt["reason"])

    def test_archon_apps_script_public_probe_runs_as_read_only_command(self):
        probe = {
            "schema": "BUBBLES-ARCHON-APPS-SCRIPT-DEPLOYMENT-PROBE-V1",
            "overall_classification": "DEPLOYMENT_HEALTH_SEMANTICS_VERIFIED",
            "mutation_attempted": False,
            "credential_values_recorded": False,
        }
        with patch("bubbles.command_bus.run_apps_script_deployment_probe", return_value=probe):
            receipt = self.run_command(
                self.command(
                    action="probe_archon_apps_script_deployment",
                    effect="READ",
                    target_alias="ARCHON_APPS_SCRIPT_PUBLIC_DEPLOYMENT",
                    payload={},
                )
            )
        self.assertEqual("SUCCESS", receipt["state"])
        self.assertEqual(
            "READ_ONLY_PUBLIC_APPS_SCRIPT_DEPLOYMENT_PROBE",
            receipt["execution"]["kind"],
        )
        self.assertEqual(probe, receipt["execution"]["probe"])
        self.assertFalse(receipt["execution"]["provider_effects"])
        self.assertIn("nested provider classification", receipt["truth_boundary"])

    def test_archon_apps_script_public_probe_cannot_be_promoted_to_write(self):
        receipt = self.run_command(
            self.command(
                action="probe_archon_apps_script_deployment",
                effect="LOW_RISK_WRITE",
                target_alias="ARCHON_APPS_SCRIPT_PUBLIC_DEPLOYMENT",
                payload={},
            )
        )
        self.assertEqual("CONSTRAINT", receipt["state"])
        self.assertIn("read-only", receipt["reason"])

    def test_chat_failure_recovery_invokes_cfre_for_connection_interruption(self):
        receipt = self.run_command(self.recovery_command({
            "message": "Connection interrupted. Waiting for the complete answer",
            "active_directive": "continue until complete",
            "next_pending_action": "resume current operation",
        }))
        self.assertEqual("SUCCESS", receipt["state"])
        self.assertEqual("LOCAL_CHAT_FAILURE_RECOVERY", receipt["execution"]["kind"])
        recovery = receipt["execution"]["recovery"]
        self.assertEqual("TRANSPORT_INTERRUPTION", recovery["failure_class"])
        self.assertTrue(recovery["must_continue"])
        self.assertEqual("RETRY_SAME_ATOMIC_ACTION", recovery["next_automated_action"])
        self.assertFalse(receipt["execution"]["provider_effects"])

    def test_chat_failure_recovery_uses_readback_before_tool_timeout_replay(self):
        receipt = self.run_command(self.recovery_command({
            "message": "tool call timeout",
            "tool_inflight": True,
            "tool_call_id": "tool-write-1",
            "next_pending_action": "finish provider write",
        }))
        recovery = receipt["execution"]["recovery"]
        self.assertEqual("TOOL_OR_CONNECTOR_FAILURE", recovery["failure_class"])
        self.assertEqual("READBACK_TOOL_OUTCOME_BEFORE_RETRY", recovery["next_automated_action"])
        actions = [step["action"] for step in recovery["recovery_steps"]]
        self.assertLess(
            actions.index("READBACK_TOOL_OUTCOME_BEFORE_RETRY"),
            actions.index("DISCOVER_EQUIVALENT_AUTHORIZED_ROUTE"),
        )

    def test_chat_failure_recovery_respects_explicit_user_stop(self):
        receipt = self.run_command(self.recovery_command({"message": "user cancelled"}))
        recovery = receipt["execution"]["recovery"]
        self.assertEqual("USER_INTERRUPTION", recovery["failure_class"])
        self.assertFalse(recovery["must_continue"])
        self.assertEqual("WAIT_FOR_USER_RESUME", recovery["next_automated_action"])

    def test_recovery_requires_event_object(self):
        receipt = self.run_command(self.command(
            action="recover_chat_failure",
            effect="READ",
            target_alias="EVIDENCEOPS_CFRE_LOCAL",
            payload={"event": "not-an-object"},
        ))
        self.assertEqual("FAILURE", receipt["state"])
        self.assertIn("payload.event", receipt["reason"])

    def test_unapproved_actor_is_blocked(self):
        receipt = self.run_command(self.command(), actor="untrusted-user")
        self.assertEqual(receipt["state"], "CONSTRAINT")
        self.assertIn("not allowed", receipt["reason"])

    def test_provider_route_is_blocked_without_fresh_runtime_proofs(self):
        receipt = self.run_command(
            self.command(
                adapter_id="google_cloud",
                action="run_harmless_canary",
                effect="LOW_RISK_WRITE",
                target_alias="GOOGLE_CLOUD_EXECUTION_PLANE",
                payload={},
            )
        )
        self.assertEqual(receipt["state"], "CONSTRAINT")
        self.assertIn("provider_identity_verified", receipt["missing_proofs"])
        self.assertIn("no provider action executed", receipt["truth_boundary"].lower())

    def test_secret_bearing_payload_fails_validation(self):
        receipt = self.run_command(
            self.command(payload={"api_key": "never-store-me"})
        )
        self.assertEqual(receipt["state"], "FAILURE")
        self.assertIn("Secret-bearing", receipt["reason"])

    def test_tampered_command_hash_is_rejected(self):
        control = BubblesControlPlane()
        request = ActionRequest(
            adapter_id="bubbles_command_bus",
            action="canary",
            effect=EffectClass.READ,
            target_alias="GITHUB_ACTIONS_A0_A1",
            payload={"message": "CHATGPT_TO_ACTIONS_CANARY"},
        )
        command = control.command_envelope(request)
        command["command_sha256"] = "0" * 64
        receipt = self.run_command(command)
        self.assertEqual(receipt["state"], "CONSTRAINT")
        self.assertIn("does not match", receipt["reason"])

    def test_native_route_cannot_be_smuggled_through_command_bus(self):
        receipt = self.run_command(
            self.command(
                adapter_id="github",
                action="enqueue",
                effect="READ",
                target_alias="FEDERATION_OMEGA_CONTROL_PLANE",
                payload={},
            )
        )
        self.assertEqual(receipt["state"], "CONSTRAINT")
        self.assertIn("GITHUB_COMMAND_BUS", receipt["reason"])


if __name__ == "__main__":
    unittest.main()