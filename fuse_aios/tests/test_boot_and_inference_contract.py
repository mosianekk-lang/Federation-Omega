#!/usr/bin/env python3
import json, pathlib, subprocess, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class TestBootAndInferenceContract(unittest.TestCase):
    def test_boot_contract_is_dual_arch_and_truth_bounded(self):
        c=json.loads((ROOT/'boot/boot-contract.json').read_text())
        self.assertEqual(set(c['architectures']), {'x86_64','arm64'})
        self.assertEqual(c['sentinel'],'FUSE_AIOS_BOOT_OK')
        self.assertEqual(c['truth_on_pass'],'EMULATED_BOOT_SENTINEL_PROVED')
    def test_init_has_exact_sentinel(self):
        self.assertIn('FUSE_AIOS_BOOT_OK', (ROOT/'rootfs/init').read_text())
    def test_cpu_inference_smoke(self):
        p=subprocess.run([sys.executable,str(ROOT/'ai/inference_smoke.py'),'--model',str(ROOT/'ai/smoke-model.json')],capture_output=True,text=True,check=True)
        r=json.loads(p.stdout); self.assertEqual(r['status'],'PASS'); self.assertFalse(r['llm_or_framework_runtime_proved'])
    def test_transactional_update_recovery_court(self):
        p=subprocess.run([sys.executable,str(ROOT/'update/run_transactional_court.py')],capture_output=True,text=True,check=True)
        r=json.loads(p.stdout)
        self.assertEqual(r['status'],'PASS')
        self.assertEqual(r['truth'],'TRANSACTIONAL_UPDATE_STATE_MACHINE_PROVED')
        self.assertEqual(r['scenarios']['commit']['state'],'COMMITTED')
        self.assertEqual(r['scenarios']['failed_health']['state'],'ROLLED_BACK')
        self.assertEqual(r['scenarios']['interrupted_activation']['state'],'ROLLED_BACK')
        self.assertFalse(r['real_block_device_rollback_proved'])
        self.assertFalse(r['firmware_or_bootloader_rollback_proved'])
if __name__=='__main__': unittest.main()
