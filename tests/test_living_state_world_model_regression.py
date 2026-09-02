"""Top-level ProofOS wrapper for the canonical Living State world-model court.

The authoritative regression remains in
``federation/living_state/tests/test_world_model.py``. This wrapper only exposes
that existing TestCase to ProofOS's top-level unittest-glob discovery contract;
it does not duplicate, weaken or alter the regression.
"""

from federation.living_state.tests.test_world_model import LivingWorldModelTests

__all__ = ["LivingWorldModelTests"]
