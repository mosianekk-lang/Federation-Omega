"""Airlock admission shim for the CFBE-Ω sovereign core.

The existing Federation Omega Airlock already executes every
``test_phoenix_provider_cutover_v3*.py`` test.  This reuses that approved lane
instead of adding another workflow or weakening the default-deny allowlist.
"""

import unittest

from sovara_operator_adapter.test_cfbe_sovereign_core import CFBESovereignCoreTests


class CFBESovereignAirlockAdmission(CFBESovereignCoreTests):
    """Execute the canonical sovereign-core regression suite in Airlock."""


if __name__ == "__main__":
    unittest.main()
