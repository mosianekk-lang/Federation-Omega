"""Defensive adversarial qualification components for AEGIS-Ω.

The package intentionally avoids eager cross-module imports so the production
fusion engine can consume the evidence-graph primitive without circular loading.
All scenarios are synthetic metadata-only simulations for authorized defense.
"""

__all__ = [
    "twin", "immune_graph", "neural_sentinel", "evolution_tournament", "court",
]
