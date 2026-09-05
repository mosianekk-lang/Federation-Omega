"""Airlock admission shim for CFBE-Ω Engineering Value Density guardrails."""

import unittest

from sovara_operator_adapter.test_engineering_value_density import (
    EngineeringValueDensityTests,
)


class EngineeringValueDensityAirlockAdmission(EngineeringValueDensityTests):
    """Run the canonical EVD tests through the existing approved v3 wildcard."""


if __name__ == "__main__":
    unittest.main()
