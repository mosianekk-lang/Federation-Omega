from __future__ import annotations

import unittest

from bubbles.browser_runtime_canary import EXPECTED_MARKER, EXPECTED_STATE, verify_dom


class BubblesBrowserRuntimeCanaryTests(unittest.TestCase):
    def test_dom_verifier_requires_js_marker_and_state_transition(self) -> None:
        dom = f'<html><body {EXPECTED_STATE}><div>{EXPECTED_MARKER}</div></body></html>'
        marker_ok, state_ok = verify_dom(dom)
        self.assertTrue(marker_ok)
        self.assertTrue(state_ok)

    def test_static_pre_execution_dom_does_not_promote(self) -> None:
        dom = '<html><body data-state="boot"><div>PENDING</div></body></html>'
        marker_ok, state_ok = verify_dom(dom)
        self.assertFalse(marker_ok)
        self.assertFalse(state_ok)


if __name__ == "__main__":
    unittest.main()
