"""Airlock compatibility binding for AO-HARMONIC v3 regressions.

The existing Federation Omega Airlock already admits files matching
``test_phoenix_provider_cutover_v3*.py``.  Re-exporting the AO-HARMONIC
``unittest.TestCase`` here binds the new fabric regressions into that governed
path without creating or broadening a workflow.
"""

from test_ao_harmonic_v3 import AOHarmonicV3Tests

__all__ = ["AOHarmonicV3Tests"]
