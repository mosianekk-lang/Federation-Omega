"""Federation Artifact Fabric v3 public API."""

from .adapters import (
    HMACReceiptSigner,
    InMemoryProjection,
    InMemoryStorage,
    ReceiptSigner,
    RegistryProjection,
    StorageAdapter,
)
from .canonical import canonical_json_bytes, merkle_root, sha256_bytes, sha256_json
from .gateway import ArtifactGateway, InjectedCrash
from .ledger import ArtifactLedger
from .migration import GenesisImporter, LegacyArtifactRecord
from .model import (
    ArtifactRequest,
    DeliveryOutcome,
    DriftFinding,
    FabricError,
    IdempotencyCollision,
    InvalidTransition,
    PermanentProviderError,
    ProviderObject,
    ProviderReadback,
    RetentionClass,
    ScanReport,
    ScanViolation,
    SensitivityClass,
    SignatureEnvelope,
    TemporaryProviderError,
    TransactionState,
)
from .reconcile import ArtifactReconciler
from .security import scan_artifact

__all__ = [
    "ArtifactGateway",
    "ArtifactLedger",
    "ArtifactReconciler",
    "ArtifactRequest",
    "DeliveryOutcome",
    "DriftFinding",
    "FabricError",
    "HMACReceiptSigner",
    "GenesisImporter",
    "IdempotencyCollision",
    "InjectedCrash",
    "InMemoryProjection",
    "InMemoryStorage",
    "InvalidTransition",
    "LegacyArtifactRecord",
    "PermanentProviderError",
    "ProviderObject",
    "ProviderReadback",
    "ReceiptSigner",
    "RegistryProjection",
    "RetentionClass",
    "ScanReport",
    "ScanViolation",
    "SensitivityClass",
    "SignatureEnvelope",
    "StorageAdapter",
    "TemporaryProviderError",
    "TransactionState",
    "canonical_json_bytes",
    "merkle_root",
    "scan_artifact",
    "sha256_bytes",
    "sha256_json",
]

__version__ = "3.0.0"
