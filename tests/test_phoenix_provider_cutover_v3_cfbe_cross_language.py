"""Airlock admission shim for CFBE-Ω Python/Apps-Script-compatible JS parity."""

import unittest

from sovara_operator_adapter.test_cfbe_sovereign_cross_language import (
    CFBESovereignCrossLanguageTests,
)


class CFBESovereignCrossLanguageAirlockAdmission(CFBESovereignCrossLanguageTests):
    """Execute cross-language route-semantic parity tests in existing Airlock."""


if __name__ == "__main__":
    unittest.main()
