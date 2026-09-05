"""Airlock admission bridge for the canonical Veritas-Ω six-contract suite.

The Federation Omega Airlock already executes ``test_phoenix_provider_cutover_v3*.py``.
This bridge makes the exact standalone Veritas regression class part of that admitted
pattern without weakening or bypassing any existing guard.
"""

from test_veritas_six_contract_adapter import VeritasSixContractAdapterTests


def load_tests(loader, tests, pattern):
    """Execute the exact canonical Veritas adapter regression class in Airlock."""
    return loader.loadTestsFromTestCase(VeritasSixContractAdapterTests)
