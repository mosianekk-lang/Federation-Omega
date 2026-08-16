"""AO-HARMONIC-GENOME v3.0 — Federation Cognitive Operating Fabric.

Source implementation only. Importing this package does not establish provider
runtime, deployment, authority expansion, or operational maturity.
"""

from .runtime import AOHarmonicV3, bootstrap

__all__ = ["AOHarmonicV3", "bootstrap"]
__version__ = "3.0.0"
