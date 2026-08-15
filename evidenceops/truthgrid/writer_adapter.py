from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Mapping, Sequence

from .guards import MutationIntent, TruthGridGuard, TruthGridViolation


@dataclass(frozen=True)
class WriterReceipt:
    """Bounded readback receipt for one guarded writer operation.

    This receipt proves only that the injected writer/readback pair returned the
    expected values for the requested stable target after the intent was bound to
    a freshly read live schema. It does not prove provider identity, deployment,
    legal correctness, or global TruthGrid completion.
    """

    sheet: str
    target_key: str
    operation: str
    readback: Mapping[str, object]
    provider_readback_verified: bool
    live_schema: tuple[str, ...]
    schema_binding_verified: bool


@dataclass
class TruthGridWriterAdapter:
    """Bind ``TruthGridGuard`` and live-schema checks before provider mutation.

    The adapter deliberately contains no provider credentials and no Google API
    implementation. A caller must inject its existing writer, independent
    readback and provider-backed live-header reader functions. The guard and live
    schema binding always run before the writer callback.
    """

    writer: Callable[[MutationIntent], object]
    readback: Callable[[str, str], Mapping[str, object]]
    schema_reader: Callable[[str], Sequence[str]]
    guard: TruthGridGuard = field(default_factory=TruthGridGuard)

    def execute(self, intent: MutationIntent) -> WriterReceipt:
        self.guard.validate_mutation(intent)
        if not intent.target_key:
            raise TruthGridViolation("KEY_BOUND_TARGET_REQUIRED")

        bound_intent, live_schema = self._bind_to_live_schema(intent)
        self.writer(bound_intent)
        observed = dict(self.readback(bound_intent.sheet, bound_intent.target_key))
        mismatches = {
            key: (expected, observed.get(key))
            for key, expected in bound_intent.values.items()
            if observed.get(key) != expected
        }
        if mismatches:
            keys = ",".join(sorted(mismatches))
            raise TruthGridViolation("PROVIDER_READBACK_MISMATCH:" + keys)

        return WriterReceipt(
            sheet=bound_intent.sheet,
            target_key=bound_intent.target_key,
            operation=bound_intent.operation,
            readback=observed,
            provider_readback_verified=True,
            live_schema=live_schema,
            schema_binding_verified=True,
        )

    def _bind_to_live_schema(self, intent: MutationIntent) -> tuple[MutationIntent, tuple[str, ...]]:
        live_schema = tuple(str(header) for header in self.schema_reader(intent.sheet))
        if not live_schema:
            raise TruthGridViolation("LIVE_SCHEMA_REQUIRED")
        if any(not header.strip() for header in live_schema):
            raise TruthGridViolation("LIVE_SCHEMA_BLANK_HEADER")
        if len(set(live_schema)) != len(live_schema):
            raise TruthGridViolation("LIVE_SCHEMA_DUPLICATE_HEADER")

        unknown_fields = sorted(set(intent.values).difference(live_schema))
        if unknown_fields:
            raise TruthGridViolation("LIVE_SCHEMA_FIELD_MISMATCH:" + ",".join(unknown_fields))

        if intent.operation.upper() == "APPEND":
            missing_fields = [header for header in live_schema if header not in intent.values]
            if missing_fields:
                raise TruthGridViolation("APPEND_REQUIRES_FULL_LIVE_SCHEMA:" + ",".join(missing_fields))

        ordered_values = {
            header: intent.values[header]
            for header in live_schema
            if header in intent.values
        }
        return replace(intent, values=ordered_values), live_schema


__all__ = ["TruthGridWriterAdapter", "WriterReceipt"]
