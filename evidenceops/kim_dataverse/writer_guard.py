from __future__ import annotations

from dataclasses import dataclass, replace

from evidenceops.truthgrid.guards import MutationIntent
from evidenceops.truthgrid.writer_adapter import TruthGridWriterAdapter, WriterReceipt

from .schema_contract import KDVSchemaRegistry


@dataclass
class KDVTypedWriterAdapter:
    """Typed KDV wrapper around the already-admitted TruthGrid writer guard.

    Adds schema normalisation before the existing live-schema binding, provider
    mutation and independent readback sequence. It contains no credentials or
    provider authority.
    """

    registry: KDVSchemaRegistry
    truthgrid_writer: TruthGridWriterAdapter

    def execute(self, intent: MutationIntent, *, block_id: str | None = None) -> WriterReceipt:
        normalised = self.registry.normalise_record(
            intent.sheet,
            intent.values,
            block_id=block_id,
            require_full_schema=intent.operation.upper() == "APPEND",
        )
        block = self.registry.sheet(intent.sheet).block(block_id)
        self.registry.validate_live_headers(
            intent.sheet,
            self.truthgrid_writer.schema_reader(intent.sheet),
            block_id=block.block_id,
        )
        return self.truthgrid_writer.execute(replace(intent, values=normalised))
