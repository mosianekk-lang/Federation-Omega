"""Kim DataVerse integrity controls.

Strengthens the existing Kim DataVerse estate without replacing canonical
identities. Supplies format-aware export decoding, typed schema normalisation,
current-state projection contracts and guarded write helpers.
"""

from .schema_contract import (
    FieldContract,
    KDVSchemaRegistry,
    SchemaContractError,
    SheetContract,
    TableBlockContract,
    structural_schema_payload,
    structural_schema_sha256,
)
from .projection_contract import (
    ProjectionContractError,
    ProviderEffectProof,
    RuntimeAttestationObservation,
    SourceFrontierObservation,
    compile_projection,
    require_expected_source,
)
from .xlsx_semantic import XlsxSemanticError, XlsxSemanticWorkbook

__all__ = [
    "FieldContract",
    "KDVSchemaRegistry",
    "ProjectionContractError",
    "ProviderEffectProof",
    "RuntimeAttestationObservation",
    "SchemaContractError",
    "SheetContract",
    "SourceFrontierObservation",
    "TableBlockContract",
    "structural_schema_payload",
    "structural_schema_sha256",
    "XlsxSemanticError",
    "XlsxSemanticWorkbook",
    "compile_projection",
    "require_expected_source",
]
