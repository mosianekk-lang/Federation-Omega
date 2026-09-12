import unittest

from federation.orchestration.strategic_decision_primitives import (
    CrossSurfaceReceiptCheck,
    ForecastSubmission,
    ForecastTournamentRecord,
    PortfolioAction,
    QualitySettlement,
    RegretIdentifiability,
    StrategicDecisionRecord,
    StrategicPortfolioRiskVector,
    can_promote_cross_surface_proof,
    detect_schema_version,
    normalize_record,
)


class SchemaNormalizationTests(unittest.TestCase):
    def test_detects_known_legacy_record(self):
        self.assertEqual(
            detect_schema_version("Strategic_Forecast_Calibration", "FCT-005"),
            "legacy_v1",
        )

    def test_current_record_normalizes_against_current_header(self):
        values = (
            "FCT-009", "2026-09-06T22:17:34+02:00", "enterprise agents",
            "event", "12_MONTHS", "0.82", "0.82", "indicator", "falsifier",
            "", "", "", "0.8-0.9", "Strategic FUSE", "learning", "OPEN",
        )
        rec = normalize_record("Strategic_Forecast_Calibration", "FCT-009", values)
        self.assertTrue(rec.normalized)
        self.assertEqual(rec.values["Forecast_ID"], "FCT-009")
        self.assertEqual(rec.values["Probability"], "0.82")

    def test_legacy_record_is_never_zipped_against_current_header(self):
        raw = ("FCT-005", "HYP-005", "event", "0.86", "2026-09-06", "2027-09-06")
        rec = normalize_record("Strategic_Forecast_Calibration", "FCT-005", raw)
        self.assertFalse(rec.normalized)
        self.assertIsNone(rec.values)
        self.assertEqual(rec.raw_values, raw)

    def test_unknown_ledger_fails_closed(self):
        with self.assertRaises(KeyError):
            detect_schema_version("Unknown", "X")


class CrossSurfaceProofTests(unittest.TestCase):
    def test_requires_logical_identity_cardinality_semantics_source_and_freshness(self):
        check = CrossSurfaceReceiptCheck(
            logical_receipt_id="TC-20260908T184610+0200-STRATFUSE-CJERL-REFERENTIAL-REPAIR",
            match_count=1,
            semantic_match=True,
            source_identity_match=True,
            fresh=True,
        )
        self.assertTrue(can_promote_cross_surface_proof(check))

    def test_physical_row_pointer_is_not_evidence_identity(self):
        check = CrossSurfaceReceiptCheck("row10114", 1, True, True, True)
        self.assertFalse(check.valid)

    def test_duplicate_or_missing_or_mismatched_receipt_fails(self):
        base = "TC-STABLE-LOGICAL-ID"
        self.assertFalse(CrossSurfaceReceiptCheck(base, 0, True, True, True).valid)
        self.assertFalse(CrossSurfaceReceiptCheck(base, 2, True, True, True).valid)
        self.assertFalse(CrossSurfaceReceiptCheck(base, 1, False, True, True).valid)
        self.assertFalse(CrossSurfaceReceiptCheck(base, 1, True, False, True).valid)
        self.assertFalse(CrossSurfaceReceiptCheck(base, 1, True, True, False).valid)


class DecisionRecordTests(unittest.TestCase):
    def test_requires_no_op_and_selected_candidate(self):
        with self.assertRaises(ValueError):
            StrategicDecisionRecord(
                decision_id="D1", mission_id="M1", decision_epoch="t", source_epoch="s",
                world_snapshot_ref="W", candidate_option_refs=("A",), selected_option_ref="B",
                no_op_baseline_ref="NOOP", decision_mechanism="changed route",
                alternative_rejection_reasons={}, authority_class="A0", effect_ceiling="S0",
            )

        with self.assertRaises(ValueError):
            StrategicDecisionRecord(
                decision_id="D1", mission_id="M1", decision_epoch="t", source_epoch="s",
                world_snapshot_ref="W", candidate_option_refs=("A",), selected_option_ref="A",
                no_op_baseline_ref="", decision_mechanism="changed route",
                alternative_rejection_reasons={}, authority_class="A0", effect_ceiling="S0",
            )

    def test_valid_decision_keeps_regret_identifiability_explicit(self):
        rec = StrategicDecisionRecord(
            decision_id="D1", mission_id="M1", decision_epoch="t", source_epoch="s",
            world_snapshot_ref="W", candidate_option_refs=("A", "B"), selected_option_ref="A",
            no_op_baseline_ref="B", decision_mechanism="mechanism",
            alternative_rejection_reasons={"B": "no information gain"},
            authority_class="A1", effect_ceiling="S0",
            regret_identifiability=RegretIdentifiability.ESTIMABLE,
        )
        self.assertEqual(rec.regret_identifiability, RegretIdentifiability.ESTIMABLE)


class ForecastTournamentTests(unittest.TestCase):
    def _submission(self, who, p, hash_):
        return ForecastSubmission(
            forecaster_id=who,
            provider_model_method=who,
            probability=p,
            confidence=0.8,
            evidence_cutoff="2026-09-12T18:00:00+02:00",
            blind_cohort="COHORT-1",
            submission_hash=hash_,
        )

    def test_blind_tournament_aggregates_and_scores(self):
        t = ForecastTournamentRecord(
            tournament_id="T1", forecast_id="F1", mission_id="M1", domain="runtime",
            horizon="7D", issued_at="now", resolve_by="later",
            evidence_snapshot_ref="ART-1",
            evidence_cutoff="2026-09-12T18:00:00+02:00",
            submissions=(self._submission("A", 0.8, "h1"), self._submission("B", 0.6, "h2")),
            aggregation_method="mean",
        )
        self.assertAlmostEqual(t.aggregate_probability, 0.7)
        self.assertAlmostEqual(t.disagreement, 0.1)
        scores = t.score(True)
        self.assertAlmostEqual(scores["A"]["brier"], 0.04)
        self.assertAlmostEqual(scores["B"]["brier"], 0.16)

    def test_rejects_duplicate_forecaster_or_different_evidence_cutoff(self):
        a = self._submission("A", 0.7, "h1")
        with self.assertRaises(ValueError):
            ForecastTournamentRecord(
                "T", "F", "M", "d", "7D", "now", "later", "ART", a.evidence_cutoff,
                (a, self._submission("A", 0.6, "h2")),
            )
        b = ForecastSubmission("B", "B", 0.6, 0.8, "DIFFERENT", "COHORT-1", "h2")
        with self.assertRaises(ValueError):
            ForecastTournamentRecord(
                "T", "F", "M", "d", "7D", "now", "later", "ART", a.evidence_cutoff,
                (a, b),
            )


class PortfolioTests(unittest.TestCase):
    def test_high_reuse_high_overlap_without_value_proof_merges(self):
        v = StrategicPortfolioRiskVector(
            opportunity_id="AECB",
            strategic_value=0.96,
            commercial_value=0.88,
            option_value=0.95,
            information_value=0.96,
            reuse_value=0.9,
            direct_owner_value_proven=False,
            commercial_validation_proven=False,
            architecture_overlap=0.9,
            capability_rent=0.7,
            evidence_uncertainty=0.6,
            time_to_value_uncertainty=0.8,
        )
        self.assertEqual(v.reunderwrite(), PortfolioAction.MERGE)

    def test_scale_requires_real_owner_and_commercial_proof(self):
        v = StrategicPortfolioRiskVector(
            opportunity_id="P",
            strategic_value=0.9, commercial_value=0.9, option_value=0.7,
            information_value=0.6, reuse_value=0.5,
            direct_owner_value_proven=True, commercial_validation_proven=True,
            architecture_overlap=0.2, capability_rent=0.2,
            evidence_uncertainty=0.1, time_to_value_uncertainty=0.2,
        )
        self.assertEqual(v.reunderwrite(), PortfolioAction.SCALE)

    def test_low_reuse_low_option_low_information_kills(self):
        v = StrategicPortfolioRiskVector(
            opportunity_id="P",
            strategic_value=0.2, commercial_value=0.1, option_value=0.2,
            information_value=0.2, reuse_value=0.1,
            direct_owner_value_proven=False, commercial_validation_proven=False,
            architecture_overlap=0.2, capability_rent=0.4,
            evidence_uncertainty=0.7, time_to_value_uncertainty=0.9,
        )
        self.assertEqual(v.reunderwrite(), PortfolioAction.KILL)


class QualitySettlementTests(unittest.TestCase):
    def test_success_does_not_inherit_between_layers(self):
        q = QualitySettlement(True, True, True, False)
        self.assertFalse(q.complete)
        self.assertTrue(QualitySettlement(True, True, True, True).complete)


if __name__ == "__main__":
    unittest.main()
