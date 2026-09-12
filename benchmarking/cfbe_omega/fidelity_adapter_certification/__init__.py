"""Four-surface, effect-free CFBE fidelity adapter certification."""

from .core import (
    CertificationError,
    load_observations,
    load_profiles,
    run_certification,
    write_json_atomic,
)

__all__ = [
    "CertificationError",
    "load_observations",
    "load_profiles",
    "run_certification",
    "write_json_atomic",
]
