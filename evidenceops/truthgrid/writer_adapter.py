from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping

from .guards import MutationIntent, TruthGridGuard, TruthGridViolation


@dataclass(frozen=True)
class WriterReceipt:
    """Bounded readback receipt for one guarded writer operation.

    This receipt proves only that the injected writer/readback pair returned the
    expected values for the requested stable target. It does not prove provider
    identity, deployment, legal correctness, or global TruthGrid completion.
    """

    sheet: str
    target_key: str
    operation: str
    readback: Mapping[str, object]
    provider_readback_verified: bool


@dataclass
class TruthGridWriterAdapter:
    """Bind ``TruthGridGuard`` to an injected writer before any mutation occurs.

    The adapter deliberately contains no provider credentials and no Google API
    implementation. A caller must inject its existing writer and independent
    readback functions. The guard always runs before the writer callback.
    """

    writer: Callable[[MutationIntent], object]
    readback: Callable[[str, str], Mapping[str, object]]
    guard: TruthGridGuard = field(default_factory=TruthGridGuard)

    def execute(self, intent: MutationIntent) -> WriterReceipt:
        self.guard.validate_mutation(intent)
        if not intent.target_key:
            raise TruthGridViolation("KEY_BOUND_TARGET_REQUIRED")

        self.writer(intent)
        observed = dict(self.readback(intent.sheet, intent.target_key))
        mismatches = {
            key: (expected, observed.get(key))
            for key, expected in intent.values.items()
            if observed.get(key) != expected
        }
        if mismatches:
            keys = ",".join(sorted(mismatches))
            raise TruthGridViolation("PROVIDER_READBACK_MISMATCH:" + keys)

        return WriterReceipt(
            sheet=intent.sheet,
            target_key=intent.target_key,
            operation=intent.operation,
            readback=observed,
            provider_readback_verified=True,
        )


__all__ = ["TruthGridWriterAdapter", "WriterReceipt"]
