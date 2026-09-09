import re
import subprocess
import sys
import unittest


class CFB_FASCG_FullCourt(unittest.TestCase):
    def test_full_fascg_court_is_green(self):
        proc = subprocess.run(
            [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_fascg_*.py', '-v'],
            text=True, capture_output=True, check=False,
        )
        combined = (proc.stdout or '') + '\n' + (proc.stderr or '')
        self.assertEqual(proc.returncode, 0, combined[-12000:])
        match = re.findall(r'Ran\s+(\d+)\s+tests?', combined)
        self.assertTrue(match, combined[-12000:])
        self.assertGreaterEqual(int(match[-1]), 320)
        self.assertIn('OK', combined)


if __name__ == '__main__':
    unittest.main()
