import unittest

from evidenceops.build_system.objective_completion_guard import REQUIRED_OPERATIONAL_LAYERS, evaluate


def complete_packet():
    return {
        "mission": {
            "objective": "Operate the Secure Capability Box across the live estate.",
            "terminalCriteria": [
                {"id": "SOURCE", "critical": True, "state": "PROVEN"},
                {"id": "LIVE_OPERATION", "critical": True, "state": "PROVEN"},
            ],
            "terminalFruit": ["authorized live action succeeds", "revocation prevents reuse"],
        },
        "systemBuild": {"operationalLayers": {
            name: {"applicable": True, "state": "PROVEN"} for name in REQUIRED_OPERATIONAL_LAYERS
        }},
        "cycle": {
            "durationHours": 24, "elapsedHours": 12, "artifactComplete": True,
            "completionRequested": True, "assistantStopping": False,
            "reportingOpenWork": False, "movingToUnrelatedWork": False,
        },
        "execution": {
            "authorizedRouteAvailable": False, "nextAutomatedAction": "",
            "routeExhaustionProven": False, "manualUserTasksAllowed": False,
            "manualUserTasks": [],
        },
        "proof": {
            "observedTerminalFruit": ["authorized live action succeeds", "revocation prevents reuse"],
            "independentLiveReadback": True,
        },
    }


class ObjectiveCompletionGuardTests(unittest.TestCase):
    def test_original_secure_box_source_only_stop_is_rejected(self):
        packet = complete_packet()
        packet["mission"]["terminalCriteria"][1]["state"] = "OPEN"
        for layer in ("configuration", "identityAuthentication", "authorization", "integration", "deployment", "liveReadback"):
            packet["systemBuild"]["operationalLayers"][layer]["state"] = "OPEN"
        packet["proof"] = {"observedTerminalFruit": [], "independentLiveReadback": False}
        packet["cycle"].update({"assistantStopping": True, "reportingOpenWork": True})
        packet["execution"].update({
            "authorizedRouteAvailable": True,
            "nextAutomatedAction": "deploy and execute authenticated canary",
        })
        result = evaluate(packet)
        self.assertEqual("BLOCK_PREMATURE_COMPLETION", result["decision"])
        self.assertFalse(result["finalResponsePermitted"])
        self.assertTrue(result["mustContinue"])
        self.assertIn("OPEN_WORK_REPORTED_INSTEAD_OF_EXECUTED", result["prematureStoppingSignals"])

    def test_fully_proven_operational_build_can_close(self):
        result = evaluate(complete_packet())
        self.assertEqual("MISSION_COMPLETE", result["decision"])
        self.assertTrue(result["completionClaimPermitted"])
        self.assertTrue(result["finalResponsePermitted"])

    def test_open_route_forces_automatic_continuation(self):
        packet = complete_packet()
        packet["mission"]["terminalCriteria"][1]["state"] = "OPEN"
        packet["cycle"].update({"artifactComplete": False, "completionRequested": False})
        packet["proof"]["independentLiveReadback"] = False
        packet["execution"].update({
            "authorizedRouteAvailable": True, "nextAutomatedAction": "run deployment route"
        })
        self.assertEqual("CONTINUE_AUTOMATICALLY", evaluate(packet)["decision"])

    def test_missing_route_requires_internal_discovery(self):
        packet = complete_packet()
        packet["mission"]["terminalCriteria"][1]["state"] = "OPEN"
        packet["cycle"].update({"artifactComplete": False, "completionRequested": False})
        packet["proof"]["independentLiveReadback"] = False
        result = evaluate(packet)
        self.assertEqual("DISCOVER_NEXT_ROUTE", result["decision"])
        self.assertFalse(result["finalResponsePermitted"])

    def test_proven_route_exhaustion_allows_blocked_report_not_completion(self):
        packet = complete_packet()
        packet["mission"]["terminalCriteria"][1]["state"] = "BLOCKED"
        packet["cycle"].update({"artifactComplete": False, "completionRequested": False})
        packet["proof"]["independentLiveReadback"] = False
        packet["execution"]["routeExhaustionProven"] = True
        result = evaluate(packet)
        self.assertEqual("BLOCKED_ROUTE_EXHAUSTED", result["decision"])
        self.assertTrue(result["finalResponsePermitted"])
        self.assertFalse(result["completionClaimPermitted"])

    def test_manual_work_transfer_is_rejected_and_removed(self):
        packet = complete_packet()
        packet["execution"].update({
            "manualUserTasks": ["configure credentials"],
            "authorizedRouteAvailable": True,
            "nextAutomatedAction": "discover managed identity route",
        })
        result = evaluate(packet)
        self.assertEqual("BLOCK_PREMATURE_COMPLETION", result["decision"])
        self.assertEqual([], result["manualUserTasks"])
        self.assertFalse(result["ownerActionRequired"])

    def test_24_hour_expiry_rolls_over_instead_of_closing(self):
        packet = complete_packet()
        packet["mission"]["terminalCriteria"][1]["state"] = "OPEN"
        packet["cycle"].update({"elapsedHours": 24, "artifactComplete": False, "completionRequested": False})
        packet["proof"]["independentLiveReadback"] = False
        packet["execution"].update({
            "authorizedRouteAvailable": True, "nextAutomatedAction": "open next cycle and deploy canary"
        })
        result = evaluate(packet)
        self.assertEqual("OPEN_NEXT_24H_CYCLE", result["cycleAction"])
        self.assertFalse(result["completionClaimPermitted"])


if __name__ == "__main__":
    unittest.main()
