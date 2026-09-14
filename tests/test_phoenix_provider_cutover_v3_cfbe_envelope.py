"""Airlock admission shim for CFBE-Ω portable invocation envelope."""

import unittest

from sovara_operator_adapter.test_cfbe_sovereign_envelope import (
    CFBESovereignEnvelopeTests,
)


class CFBESovereignEnvelopeAirlockAdmission(CFBESovereignEnvelopeTests):
    """Execute the portable-envelope regression suite in existing Airlock."""


if __name__ == "__main__":
    unittest.main()
