from pathlib import Path
import unittest
SRC=(Path(__file__).parents[1]/'apps_script/federation_bridge_consumer/Code.gs').read_text()
class BridgeHardening(unittest.TestCase):
 def test_no_dynamic_dispatch(self): self.assertNotIn('this[fn]',SRC); self.assertNotIn('globalThis[',SRC)
 def test_generic_dispatch_disabled(self): self.assertIn('GENERIC_DISPATCH_DISABLED_USE_ACTION_SPECIFIC_CELL',SRC)
 def test_all_legacy_contracts_high(self):
  for f in ['INSTALL_SOURCE_PACKAGE','gasSchedulerInstall','processMetaExecutorQueueV2','processSentinelQueue','genesisCompleteSetup']: self.assertIn(f,SRC)
  self.assertGreaterEqual(SRC.count("risk:'HIGH'"),5)
 def test_high_effect_held(self): self.assertIn('HELD_AUTHORITY_ACTION_SPECIFIC_CELL_REQUIRED',SRC)
 def test_no_direct_function_call(self): self.assertNotIn('target(payload',SRC); self.assertNotIn('target(payload || {})',SRC)
 def test_provider_effect_false(self): self.assertIn('providerEffect:false',SRC)
if __name__=='__main__': unittest.main()
