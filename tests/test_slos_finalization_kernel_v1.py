import unittest
from superior_logic.finalization_kernel import FinalizationDirective, SLOSFinalizationKernel

class FinalizationKernelTests(unittest.TestCase):
    def test_compiles_end_to_end_blueprint(self):
        directive=FinalizationDirective(
            mission_id='slos-final',base_revision='abc',objective='improve repository intelligence and verified coding runtime',
            required_capabilities=('repository_intelligence','prepared_workspace','coding_fleet','verification_supercourt','capability_closure'),
            optional_capabilities=('semantic_readback','rollback'),risk='HIGH')
        files={'superior_logic/x.py':'def repository_intelligence():\n    pass\n','tests/test_x.py':'def test_x():\n    assert True\n'}
        bp=SLOSFinalizationKernel().compile(directive,repository_files=files,toolchain={'python':'3.12'},dependencies={'pytest':'8.4.1'})
        self.assertFalse(bp.architecture_residual)
        self.assertEqual(bp.closure_action,'NOT_REQUIRED')
        self.assertEqual(len(bp.required_final_proofs),11)
        self.assertTrue(bp.blueprint_sha256)

    def test_missing_capability_creates_residual_closure(self):
        directive=FinalizationDirective(mission_id='m',base_revision='abc',objective='novel capability',required_capabilities=('unknown_x',))
        bp=SLOSFinalizationKernel().compile(directive,repository_files={'a.py':'x=1'},toolchain={},dependencies={})
        self.assertEqual(bp.architecture_residual,('unknown_x',))
        self.assertEqual(bp.closure_action,'BUILD_SMALLEST_GAP')

if __name__=='__main__': unittest.main()
