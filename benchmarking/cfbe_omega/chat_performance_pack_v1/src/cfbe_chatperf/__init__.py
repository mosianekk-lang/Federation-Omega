"""CFBE Chat Performance Pack."""

__version__ = "1.0.0"

from .benchmark import score_benchmark
from .canary_controller import evaluate_canary
from .context_capsule import build_capsule
from .ledger_head import LedgerHead
from .recovery_snapshot import sign_snapshot, verify_snapshot
from .stream_guard import assess_stream

__all__ = [
    "LedgerHead",
    "assess_stream",
    "build_capsule",
    "evaluate_canary",
    "score_benchmark",
    "sign_snapshot",
    "verify_snapshot",
]
