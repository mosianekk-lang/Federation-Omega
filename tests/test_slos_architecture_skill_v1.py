import unittest
from superior_logic.architecture_genome import ArchitectureGenome,ArchitecturePattern,ArchitectureRequirement,core_ai_patterns
from superior_logic.skill_forge import SkillForge,SkillReplay,TrajectoryLesson

class ArchitectureTests(unittest.TestCase):
 def test_composes_required_capabilities(self):
  req=ArchitectureRequirement(('agents','durability','verification','tools'),max_components=4,min_proof_strength=.7); opts=ArchitectureGenome().rank(req,core_ai_patterns()); self.assertFalse(opts[0].residual_gaps); self.assertIn('MISSION_DAG_AGENTS',opts[0].pattern_ids); self.assertIn('INDEPENDENT_PROOF_SIDECAR',opts[0].pattern_ids)
 def test_incompatibility_respected(self):
  p1=ArchitecturePattern('A',('x',),.9,.1,.1,.9,incompatible_with=('B',)); p2=ArchitecturePattern('B',('y',),.9,.1,.1,.9); opts=ArchitectureGenome().rank(ArchitectureRequirement(('x','y'),max_components=2),[p1,p2]); self.assertTrue(all(set(o.pattern_ids)!={'A','B'} for o in opts))

class SkillTests(unittest.TestCase):
 def lessons(self): return [TrajectoryLesson(f'm{i}',('inspect repo','run tests','apply patch','rerun tests'),(f'proof://{i}',),True,True) for i in range(3)]
 def test_skill_from_repeated_proof(self):
  s=SkillForge().propose(name='Safe Patch',description='Patch with verification',lessons=self.lessons()); self.assertEqual(s.status,'CANDIDATE'); self.assertIn('apply patch',s.steps); self.assertIn('Procedure',SkillForge().render_skill_md(s,checks=('tests pass',)))
 def test_skill_promotion_requires_independent_replay(self):
  s=SkillForge().propose(name='Safe Patch',description='Patch',lessons=self.lessons()); r=[SkillReplay('r1',True,True,True,'proof://r1'),SkillReplay('r2',True,True,True,'proof://r2')]; self.assertEqual(SkillForge().evaluate(s,r),'ADOPT_CANDIDATE')
 def test_regression_rejects(self):
  s=SkillForge().propose(name='Safe Patch',description='Patch',lessons=self.lessons()); self.assertEqual(SkillForge().evaluate(s,[SkillReplay('r1',True,True,False,'proof://r1')]),'REJECT_REGRESSION')

if __name__=='__main__': unittest.main()
