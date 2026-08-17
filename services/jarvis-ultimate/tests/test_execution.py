from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from jarvis import main
from jarvis.core import ACTION_SPECS
from jarvis.execution import ExecutionEvidenceError, TwentyMinuteGovernor
from jarvis.orchestrator import Jarvis


SERVICE = Path(__file__).resolve().parents[1]
REPOSITORY = Path(__file__).resolve().parents[3]


def quality_evidence(governor: TwentyMinuteGovernor, *, passed: bool = True, observed_at: int | None = None):
    now = int(governor._clock()) if observed_at is None else observed_at
    rows = {}
    for gate in governor.policy.quality_gates:
        rows[gate] = {
            "passed": passed,
            "sourceClass": "INDEPENDENT_VERIFIER" if gate == "ADVERSARIAL_CHECK" else "TEST_HARNESS",
            "proofRef": f"test:{gate.lower()}",
            "semanticDigest": hashlib.sha256(f"{gate}:{passed}:{now}".encode()).hexdigest(),
            "observedAt": now,
            "independent": gate == "ADVERSARIAL_CHECK",
        }
    return rows


def success_route(route_id: str = "primary"):
    return {
        "routeId": route_id,
        "state": "SUCCESS",
        "stateDelta": "requested result produced in the locked form",
        "proofRef": f"test:route:{route_id}",
    }


def blocked_route(route_id: str = "provider"):
    return {
        "routeId": route_id,
        "state": "BLOCKED",
        "stateDelta": "provider authority remains unproven",
        "proofRef": f"test:route:{route_id}",
        "nextRoute": "preserve local fruit and run a bounded provider-native readback canary",
    }


class TwentyMinuteLessonGateTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_000_000.0
        self.governor = TwentyMinuteGovernor(clock=lambda: self.now)

    def test_plan_locks_objective_form_and_expected_delta(self):
        plan = self.governor.build_plan(
            "M1",
            "Finish the governed build",
            "stacked GitHub pull request",
            "v1.5 source and proof receipt exist without changing main",
        )
        self.assertEqual(plan["deadlineAt"] - plan["startedAt"], 1200)
        self.assertEqual(sum(phase["max_seconds"] for phase in plan["phases"]), 1200)
        self.assertEqual(plan["objectiveLock"]["deliverableForm"], "stacked GitHub pull request")
        self.assertEqual(plan["objectiveLock"]["weakerSubstitution"], "DENY")
        self.assertEqual({path["path_class"] for path in plan["paths"]}, {"PRIMARY", "PROTECTIVE", "FAILURE_RECOVERY"})
        self.assertLessEqual(len(plan["paths"]), 3)
        self.assertLessEqual(len(plan["streams"]), 6)

    def test_time_controls_force_split_convergence_release_deadline(self):
        started = self.now
        self.assertEqual(self.governor.control_state(started, started + 719)["state"], "GREEN")
        self.assertEqual(self.governor.control_state(started, started + 720)["state"], "SPLIT_REQUIRED")
        self.assertEqual(self.governor.control_state(started, started + 900)["state"], "CONVERGENCE_ONLY")
        self.assertEqual(self.governor.control_state(started, started + 1080)["state"], "RELEASE_ONLY")
        self.assertEqual(self.governor.control_state(started, started + 1200)["state"], "DEADLINE_REACHED")

    def test_bare_boolean_quality_claim_is_rejected(self):
        evidence = {gate: True for gate in self.governor.policy.quality_gates}
        with self.assertRaisesRegex(ExecutionEvidenceError, "QUALITY_GATE_EVIDENCE_OBJECT_REQUIRED"):
            self.governor.review_cycle(500, evidence, [success_route()], "continue automatically")

    def test_stale_quality_evidence_is_rejected(self):
        evidence = quality_evidence(self.governor, observed_at=int(self.now) - 86_401)
        with self.assertRaisesRegex(ExecutionEvidenceError, "QUALITY_GATE_EVIDENCE_STALE"):
            self.governor.review_cycle(500, evidence, [success_route()], "refresh proof and retry")

    def test_adversarial_gate_requires_independent_evidence(self):
        evidence = quality_evidence(self.governor)
        evidence["ADVERSARIAL_CHECK"]["independent"] = False
        with self.assertRaisesRegex(ExecutionEvidenceError, "ADVERSARIAL_CHECK_INDEPENDENCE_REQUIRED"):
            self.governor.review_cycle(500, evidence, [success_route()], "run independent challenge")

    def test_route_level_failure_preserves_successful_lane(self):
        review = self.governor.review_cycle(
            700,
            quality_evidence(self.governor),
            [success_route(), blocked_route()],
            "run the provider-native authority readback while preserving the verified local result",
        )
        self.assertTrue(review["cyclePass"])
        self.assertEqual(review["completionState"], "BOUNDED_COMPLETE")
        self.assertEqual(review["releaseDecision"], "HOLD")
        self.assertEqual(review["successfulRoutes"], ["primary"])
        self.assertEqual(review["openRoutes"], ["provider"])

    def test_no_op_route_forces_materially_different_next_route(self):
        route = {
            "routeId": "unchanged-retry",
            "state": "NO_OP",
            "stateDelta": "none",
            "proofRef": "test:no-op",
            "nextRoute": "switch to exact provider metadata readback",
        }
        review = self.governor.review_cycle(
            400,
            quality_evidence(self.governor),
            [route],
            "switch to exact provider metadata readback",
        )
        self.assertTrue(review["noOpCircuitOpened"])
        self.assertEqual(review["releaseDecision"], "REPAIR")
        self.assertEqual(review["omegaScientist"]["promotionState"], "REJECTED")

    def test_deadline_breach_cannot_be_promoted(self):
        review = self.governor.review_cycle(
            1201,
            quality_evidence(self.governor),
            [success_route()],
            "decompose the next cycle before execution",
        )
        self.assertFalse(review["deadlinePass"])
        self.assertFalse(review["cyclePass"])
        self.assertEqual(review["releaseDecision"], "REPAIR")
        self.assertEqual(review["omegaScientist"]["promotionState"], "REJECTED")

    def test_speed_gain_is_shadow_only_after_complete_verified_cycle(self):
        review = self.governor.review_cycle(
            600,
            quality_evidence(self.governor),
            [success_route()],
            "run the next bounded regression at the shadow target",
        )
        self.assertEqual(review["completionState"], "COMPLETE_VERIFIED")
        self.assertEqual(review["releaseDecision"], "MERGE")
        self.assertEqual(review["omegaScientist"]["promotionState"], "SHADOW_CANDIDATE")
        self.assertEqual(review["omegaScientist"]["candidateNextTargetSeconds"], 570)
        self.assertEqual(len(review["receiptDigest"]), 64)

    def test_known_failure_replay_is_mandatory(self):
        evidence = quality_evidence(self.governor)
        evidence.pop("KNOWN_FAILURE_REPLAY")
        with self.assertRaisesRegex(ExecutionEvidenceError, "MISSING_QUALITY_GATES:KNOWN_FAILURE_REPLAY"):
            self.governor.review_cycle(500, evidence, [success_route()], "replay known failures")

    def test_next_automated_pathway_is_mandatory(self):
        with self.assertRaisesRegex(ExecutionEvidenceError, "NEXT_BEST_AUTOMATED_PATHWAY_REQUIRED"):
            self.governor.review_cycle(500, quality_evidence(self.governor), [success_route()], "  ")

    def test_email_send_rule_requires_explicit_owner_authority(self):
        self.assertIn("EXPLICIT_CURRENT_OWNER_GRANT", self.governor.policy.email_send_rule)
        self.assertEqual(ACTION_SPECS["gmail.send"].risk.value, "EFFECTFUL")
        self.assertEqual(ACTION_SPECS["gmail.forward"].risk.value, "EFFECTFUL")

    def test_orchestrator_persists_structured_cycle_review(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Jarvis(directory)
            evidence = quality_evidence(app.execution, observed_at=int(time.time()))
            result = app.review_cycle(
                650,
                evidence,
                [success_route()],
                "execute the next verified lane automatically",
            )
            self.assertEqual(result["completionState"], "COMPLETE_VERIFIED")
            self.assertTrue(result["learningHash"])
            self.assertEqual(result["learningPromotion"], "NOT_PROMOTED")
            self.assertTrue(app.ledger.verify())

    def test_lesson_gate_preserves_maturity_boundaries(self):
        gate = json.loads((SERVICE / "LESSON_GATE_72H.json").read_text(encoding="utf-8"))
        contract = json.loads((SERVICE / "BUILD_CONTRACT.json").read_text(encoding="utf-8"))
        self.assertEqual(gate["preGateFinding"]["decision"], "REPAIR_REQUIRED")
        self.assertEqual(gate["postRepairDecision"]["decision"], "HOLD")
        self.assertFalse(contract["states"]["ready"])
        self.assertFalse(contract["states"]["deployed"])
        self.assertFalse(contract["states"]["proven"])

    def test_lesson_gate_contains_no_chat_restore_claim(self):
        gate = json.loads((SERVICE / "LESSON_GATE_72H.json").read_text(encoding="utf-8"))
        boundary = gate["nonNegotiableBoundaries"]
        self.assertFalse(boundary["chatDataRestored"])
        self.assertFalse(boundary["workstreamsRestored"])
        self.assertFalse(boundary["caseDataImported"])
        self.assertEqual(boundary["emailActionsPerformedByThisGate"], 0)
        self.assertEqual(len(gate["lessons"]), 21)

    def test_no_new_workflow_is_introduced(self):
        self.assertFalse((REPOSITORY / ".github" / "workflows" / "jarvis-ultimate-t20-ci.yml").exists())


class T20HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app_patch = patch.object(main, "APP", Jarvis(self.tmp.name))
        self.app_patch.start()
        self.token_patch = patch.dict(os.environ, {"JARVIS_API_TOKEN": "secret"})
        self.token_patch.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), main.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.token_patch.stop()
        self.app_patch.stop()
        self.tmp.cleanup()

    def request(self, path, payload=None, token="secret"):
        data = None if payload is None else json.dumps(payload).encode()
        headers = {"content-type": "application/json"}
        if token is not None:
            headers["authorization"] = f"Bearer {token}"
        request = Request(
            self.base + path,
            data=data,
            headers=headers,
            method="POST" if payload is not None else "GET",
        )
        with urlopen(request, timeout=3) as response:
            body = response.read()
            return response.status, json.loads(body) if body else {}

    def test_http_policy_and_cycle_review_are_protected_and_proof_bearing(self):
        with self.assertRaises(HTTPError) as denied:
            self.request("/v1/execution-policy", token=None)
        self.assertEqual(denied.exception.code, 403)
        status, policy = self.request("/v1/execution-policy")
        self.assertEqual(status, 200)
        self.assertEqual(policy["id"], "T20-AO-OMEGA-SCIENTIST-1.1")

        bare = {gate: True for gate in main.APP.execution.policy.quality_gates}
        with self.assertRaises(HTTPError) as rejected:
            self.request(
                "/v1/cycle-review",
                {
                    "elapsedSeconds": 500,
                    "qualityEvidence": bare,
                    "routeResults": [success_route()],
                    "nextBestAutomatedPathway": "continue",
                },
            )
        self.assertEqual(rejected.exception.code, 400)

        evidence = quality_evidence(main.APP.execution, observed_at=int(time.time()))
        status, review = self.request(
            "/v1/cycle-review",
            {
                "elapsedSeconds": 500,
                "qualityEvidence": evidence,
                "routeResults": [success_route()],
                "nextBestAutomatedPathway": "continue automatically with the next verified lane",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(review["completionState"], "COMPLETE_VERIFIED")
        self.assertTrue(review["learningHash"])


if __name__ == "__main__":
    unittest.main()
