from __future__ import annotations

from .alpha_omega_models import (
    AlphaOmegaCaptureError,
    AlphaOmegaRestoreMode,
    CaptureObservation,
    CapturePath,
    CapturePathConflict,
    CapturePathKind,
    CapturePathNotRegistered,
    CapturePathState,
    ConversationStream,
    ObservationConflict,
    OrderingAuthority,
    ReconciliationState,
    ReplayChunk,
    StreamExpectation,
    StreamManifestError,
)
from .alpha_omega_assess import AlphaOmegaAssessMixin
from .alpha_omega_canonical import AlphaOmegaCanonicalMixin
from .alpha_omega_findings import AlphaOmegaFindingsMixin
from .alpha_omega_paths import AlphaOmegaPathsMixin
from .alpha_omega_reconcile import AlphaOmegaReconcileMixin
from .alpha_omega_replay import AlphaOmegaReplayMixin
from .alpha_omega_stage import AlphaOmegaStageMixin
from .alpha_omega_store_core import AlphaOmegaStoreCoreMixin


class AlphaOmegaConversationCapture(
    AlphaOmegaStoreCoreMixin,
    AlphaOmegaFindingsMixin,
    AlphaOmegaPathsMixin,
    AlphaOmegaStageMixin,
    AlphaOmegaCanonicalMixin,
    AlphaOmegaReconcileMixin,
    AlphaOmegaAssessMixin,
    AlphaOmegaReplayMixin,
):
    """Durable Alpha→Omega multi-path/multi-stream capture orchestrator.

    The engine composes multiple authorised acquisition paths into one canonical FFCL
    sequence. It preserves path failures, stream gaps and conflicting observations instead
    of choosing silently. The route layer reuses AO-HARMONIC's FormationEngine; exact
    promotion requires sequence-complete FFCL proof plus explicit ordering, a complete
    declared stream manifest and independent path corroboration.
    """

    VERSION = "AO-CAPTURE-1.0"
    CHATBRIDGE_VERSION = "CHATBRIDGE-Ω4.9-ALPHA-OMEGA-MULTIPATH-MULTISTREAM"
    ARCHITECTURE_CYCLE = (
        "ALPHA_BIND",
        "PATH_DISCOVERY",
        "STREAM_DISCOVERY",
        "STAGE",
        "RECONCILE",
        "CONFLICT_AND_GAP_TEST",
        "CANONICAL_APPEND",
        "OMEGA_COMPLETION_WITNESS",
        "REPLAY",
        "READBACK",
    )


__all__ = [
    "AlphaOmegaCaptureError",
    "AlphaOmegaConversationCapture",
    "AlphaOmegaRestoreMode",
    "CaptureObservation",
    "CapturePath",
    "CapturePathConflict",
    "CapturePathKind",
    "CapturePathNotRegistered",
    "CapturePathState",
    "ConversationStream",
    "ObservationConflict",
    "OrderingAuthority",
    "ReconciliationState",
    "ReplayChunk",
    "StreamExpectation",
    "StreamManifestError",
]
