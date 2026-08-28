from __future__ import annotations
import unittest
from ops.sovara_mcf_v3_1.forensic_decision_cell_ao5 import *


class AO5IntegrationTests(unittest.TestCase):
    def test_execution_requires_preflight(self):
        c=ForensicDecisionCellAO5()
        with self.assertRaisesRegex(ValueError,'PREFLIGHT'):
            c.transition(ExecutionState.S11_EXECUTION)

    def test_release_requires_three_gates(self):
        c=ForensicDecisionCellAO5(); c.preflight(PreflightInput())
        with self.assertRaisesRegex(ValueError,'RELEASE_REQUIRES'):
            c.transition(ExecutionState.S21_RELEASE)

    def test_capability_reality_inflation_blocked(self):
        r=CapabilityRecord('C','demo',CapabilityRealityState.C2_TOOL_BOUND)
        with self.assertRaisesRegex(ValueError,'REALITY_INFLATION'):
            r.assert_claimable_as(CapabilityRealityState.C4_PROVIDER_VERIFIED)

    def test_hidden_spof_detected(self):
        d=DecisionDAG()
        self.assertEqual(d.hidden_spofs({'A':{'X','Y'},'B':{'X'},'C':{'Z'}})['X'],('A','B'))

    def test_path_budget_caps_active_and_shadow(self):
        ps=[PathRecord(f'P{i}','O','x',(),(),(),(),(),.8,.8,.8,.8,.8,.8,.5,.5,.5) for i in range(9)]
        a=PathBudgetGovernor().allocate(ps)
        self.assertEqual((len(a['ACTIVE']),len(a['SHADOW']),len(a['ARCHIVED'])),(3,3,3))

    def test_derivative_repetition_not_independent(self):
        r=EvidenceIndependenceEngine.classify(['A','A','A','B'])
        self.assertEqual((r['origin_count'],r['independent_source_count'],r['derivative_count']),(4,2,2))

    def test_semantic_firewall_blocks_inflation(self):
        v=SemanticRegressionFirewall.check([('may','did'),('partial','complete'),('fact','fact')])
        self.assertEqual(v,('MAY->DID','PARTIAL->COMPLETE'))

    def test_confidence_dimensions_remain_separate(self):
        c=ConfidenceVector(.9,.95,.8,.4,.7,.2,.8,.8,.6,.5)
        self.assertGreater(c.fact_confidence,c.causal_confidence)

    def test_evidence_quality_dimensions_remain_separate(self):
        e=EvidenceQualityVector(.9,.8,.9,.2,.7,.8,.8,.9,.7,1.0)
        self.assertEqual(len(e.dimensions()),10); self.assertEqual(e.independence,.2)

    def test_recurrence_and_promotion_laws(self):
        self.assertEqual(FailureLearningModel.recurrence_action(1),'STRENGTHEN_CONTROL')
        self.assertEqual(FailureLearningModel.recurrence_action(2),'OMEGA_SCIENTIST_ARCHITECTURE_REVIEW')
        self.assertEqual(FailureLearningModel.recurrence_action(3),'EXISTING_FIX_FAILED_REDESIGN_OR_ROLLBACK')
        self.assertEqual(FailureLearningModel.promotion_state(fixed=True,tested_control=False,regression_survived=False),'INCIDENT')
        self.assertEqual(FailureLearningModel.promotion_state(fixed=True,tested_control=True,regression_survived=False),'LEARNING')
        self.assertEqual(FailureLearningModel.promotion_state(fixed=True,tested_control=True,regression_survived=True),'CAPABILITY')

    def test_harmonization_preserves_sovara_authority(self):
        h=ForensicDecisionCellAO5.harmonization_contract()
        self.assertEqual(h.ao5_role,'FORENSIC_DECISION_INTELLIGENCE_METHOD_CELL')
        self.assertIn('SOVARA',h.provider_effect_authority)
        self.assertFalse(h.cross_project_case_data_transfer)

    def test_consequence_gate_fail_closed(self):
        self.assertEqual(ForensicDecisionCellAO5.consequence_gate(owner_approval=False,provider_authority=True),'BLOCK_OWNER_APPROVAL_REQUIRED')
        self.assertEqual(ForensicDecisionCellAO5.consequence_gate(owner_approval=True,provider_authority=False),'BLOCK_PROVIDER_AUTHORITY_REQUIRED')

    def test_synthetic_canary(self):
        r=run_synthetic_canary()
        self.assertEqual(r['status'],'PASS'); self.assertTrue(all(r['checks'].values()))
        self.assertEqual(r['receipt']['external_effects'],0)


if __name__=='__main__': unittest.main()
