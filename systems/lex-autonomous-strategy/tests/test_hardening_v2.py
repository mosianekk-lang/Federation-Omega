import unittest

from lex_strategy.hardening_v2 import LexHardeningSupportV2, LexMatterReleaseCourtV2


def good_matter():
    return {
        "matter_id": "M1",
        "events": [{"event_id": "EV1", "event_time": "2026-01-01T10:00:00+02:00"}],
        "decisions": [{
            "decision_id": "D1", "decision_maker": "DM", "authority": "AUTH",
            "decision_date": "2026-01-02", "evidence_considered": ["E1"],
            "findings": ["F"], "alternatives_considered": ["ALT"],
            "prejudice_weighed": ["P"], "reasons": ["R"], "review_path": "REVIEW",
        }],
        "remedies": [{
            "remedy_id": "R1", "forum": "FORUM", "prerequisites": ["X"],
            "evidence_required": ["E1"], "timing": "30d", "enforcement_path": "ORDER",
        }],
        "opponent_strongest_factual": ["OF"],
        "opponent_strongest_legal": ["OL"],
        "opponent_strongest_procedural": ["OP"],
        "opponent_likely_next": ["NEXT"],
        "opponent_surprise": ["SURPRISE"],
        "reasons_we_could_lose": ["L1"],
        "weak_authorities": ["WA"],
        "missing_evidentiary_links": ["ML"],
        "do_not_concede": ["DC"],
        "unknowns": [{
            "unknown_id": "U1", "legal_importance": 1, "case_theory_impact": 1,
            "opponent_defeat_value": 1, "procedural_urgency": 1, "fragility": 1,
            "accessibility": 1, "cost": 0, "owner_effort": 0, "downstream_leverage": 1,
        }],
    }


def good_packet():
    return {
        "matter": good_matter(),
        "upstream": {
            "lex_omega_state": "PASS", "jfrie_state": "PASS",
            "truthgrid_state": "READY", "caseforge_state": "PASS",
            "authority_semantic_verified": True, "current_law_verified": True,
        },
        "lase_run": {
            "truth_boundary": {"external_effect": False, "consequential_actions_owner_reserved": True},
            "forecast_tree": [{"step": 1}], "selected_strategy": {"route_id": "R"},
        },
    }


class LexHardeningV2Tests(unittest.TestCase):
    def test_good_packet_is_internal_only(self):
        out = LexMatterReleaseCourtV2().adjudicate(good_packet())
        self.assertEqual(out["state"], "INTERNAL_WORK_PRODUCT_ELIGIBLE")
        self.assertFalse(out["external_effect"])
        self.assertEqual(out["upstream_reuse"]["legal_authority"], "LEX_OMEGA_REUSED")

    def test_jfrie_failure_is_p0_hold(self):
        packet = good_packet(); packet["upstream"]["jfrie_state"] = "FAIL"
        out = LexMatterReleaseCourtV2().adjudicate(packet)
        self.assertEqual(out["state"], "HOLD")
        self.assertTrue(any(f["gate"] == "JFRIE" and f["severity"] == "P0" for f in out["findings"]))

    def test_authsem_must_be_bound_to_matter(self):
        packet = good_packet(); packet["upstream"]["authority_semantic_verified"] = False
        self.assertTrue(any(f["gate"] == "AUTHSEM_UPSTREAM" for f in LexMatterReleaseCourtV2().adjudicate(packet)["findings"]))

    def test_current_law_must_be_bound(self):
        packet = good_packet(); packet["upstream"]["current_law_verified"] = False
        self.assertTrue(any(f["gate"] == "CURRENT_LAW" for f in LexMatterReleaseCourtV2().adjudicate(packet)["findings"]))

    def test_lase_must_be_no_effect(self):
        packet = good_packet(); packet["lase_run"]["truth_boundary"]["external_effect"] = True
        self.assertTrue(any(f["gate"] == "LASE_EFFECT" for f in LexMatterReleaseCourtV2().adjudicate(packet)["findings"]))

    def test_decision_record_must_be_complete(self):
        packet = good_packet(); packet["matter"]["decisions"][0]["reasons"] = []
        self.assertTrue(any(f["gate"] == "DECISION_RECORD" for f in LexMatterReleaseCourtV2().adjudicate(packet)["findings"]))

    def test_decision_cannot_claim_future_evidence(self):
        packet = good_packet(); packet["matter"]["events"] = [{
            "event_id": "EV", "decision_time": "2026-01-01T10:00:00+02:00",
            "evidence_available_time": "2026-01-02T10:00:00+02:00", "claimed_considered": True,
        }]
        self.assertTrue(any(f["gate"] == "DECISION_EVIDENCE_SEQUENCE" for f in LexMatterReleaseCourtV2().adjudicate(packet)["findings"]))

    def test_derivative_timestamp_cannot_precede_source(self):
        packet = good_packet(); packet["matter"]["events"] = [{
            "event_id": "EV", "source_native_time": "2026-01-02T10:00:00+02:00",
            "derivative_time": "2026-01-01T10:00:00+02:00",
        }]
        self.assertTrue(any(f["gate"] == "TEMPORAL_DERIVATIVE" for f in LexMatterReleaseCourtV2().adjudicate(packet)["findings"]))

    def test_event_sequence_is_enforced(self):
        packet = good_packet(); packet["matter"]["events"] = [
            {"event_id": "A", "event_time": "2026-01-02T10:00:00+02:00"},
            {"event_id": "B", "event_time": "2026-01-01T10:00:00+02:00", "must_follow_event_id": "A"},
        ]
        self.assertTrue(any(f["gate"] == "EVENT_SEQUENCE" for f in LexMatterReleaseCourtV2().adjudicate(packet)["findings"]))

    def test_remedy_prerequisites_are_required(self):
        packet = good_packet(); packet["matter"]["remedies"][0]["prerequisites"] = []
        self.assertTrue(any(f["gate"] == "REMEDY_STACK" for f in LexMatterReleaseCourtV2().adjudicate(packet)["findings"]))

    def test_opponent_twin_must_be_complete(self):
        packet = good_packet(); packet["matter"]["opponent_strongest_legal"] = []
        self.assertTrue(any(f["gate"] == "OPPONENT_TWIN" for f in LexMatterReleaseCourtV2().adjudicate(packet)["findings"]))

    def test_tribunal_twin_must_include_loss_and_nonconcession(self):
        packet = good_packet(); packet["matter"]["do_not_concede"] = []
        self.assertTrue(any(f["gate"] == "TRIBUNAL_TWIN" for f in LexMatterReleaseCourtV2().adjudicate(packet)["findings"]))

    def test_information_gain_ranking_is_deterministic(self):
        support = LexHardeningSupportV2()
        unknowns = good_matter()["unknowns"] + [{
            "unknown_id": "U2", "legal_importance": 0, "case_theory_impact": 0,
            "opponent_defeat_value": 0, "procedural_urgency": 0, "fragility": 0,
            "accessibility": 0, "cost": 1, "owner_effort": 1, "downstream_leverage": 0,
        }]
        self.assertEqual(support.information_gain_queue(unknowns)[0]["unknown_id"], "U1")

    def test_capability_graph_separates_maturity_and_duplicates(self):
        out = LexHardeningSupportV2().capability_graph([
            {"capability_id": "C1", "maturity": "TESTED"},
            {"capability_id": "C1", "maturity": "MAGIC"},
        ])
        self.assertEqual(out["duplicate_ids"], ["C1"])
        self.assertEqual(out["invalid_maturity"], ["C1"])

    def test_failure_win_never_self_promotes(self):
        out = LexHardeningSupportV2().failure_to_operational_win({"failed_expectation": "x"})
        self.assertEqual(out["state"], "REPAIR_CYCLE_OPEN")
        self.assertFalse(out["operational_win_verified"])


if __name__ == "__main__":
    unittest.main()
