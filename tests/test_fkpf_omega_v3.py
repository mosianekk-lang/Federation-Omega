"""ProofOS discovery bridge for the FKPF Ω∞ v3 deterministic court.

The canonical tests live with the implementation under
``federation/fkpf_omega_v3/tests/test_kernel.py``.  ProofOS executes
``unittest_glob`` targets from the repository-level ``tests`` directory, so
this module re-exports the canonical TestCase classes without duplicating test
logic or creating a second test authority plane.
"""

from federation.fkpf_omega_v3.tests.test_kernel import (  # noqa: F401
    BusPropagationTests,
    DeltaPolicyTests,
    InteropIdentityTests,
    LedgerTests,
    MissionWorkflowTests,
    RetryReleaseProofTests,
)
