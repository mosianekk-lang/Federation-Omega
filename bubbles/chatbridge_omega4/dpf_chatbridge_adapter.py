from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence

from .design_provenance_fabric import DesignProvenanceBridge


def bind_design_provenance_fabric(
    chatbridge_runtime: Any,
    *,
    manifest_sink: Optional[Callable[[Dict[str, Any]], Any]] = None,
    reconciliation_sink: Optional[Callable[[Dict[str, Any]], Any]] = None,
    cleanup_sink: Optional[Callable[[Dict[str, Any]], Any]] = None,
    design_gene_extractor: Optional[
        Callable[[Sequence[Mapping[str, Any]]], Iterable[Mapping[str, Any]]]
    ] = None,
) -> DesignProvenanceBridge:
    """Bind the current ChatBridge full-fidelity ledger to the DPF controller.

    This is intentionally dependency-light: ChatBridge remains the raw capture authority,
    while sinks are injected by the private runtime/control plane. No Drive IDs, secrets,
    credentials or provider authority are embedded in public source.
    """

    ledger = getattr(chatbridge_runtime, "full_fidelity", None)
    if ledger is None:
        raise ValueError("chatbridge_runtime must expose full_fidelity ledger authority")
    return DesignProvenanceBridge(
        ledger,
        manifest_sink=manifest_sink,
        reconciliation_sink=reconciliation_sink,
        cleanup_sink=cleanup_sink,
        design_gene_extractor=design_gene_extractor,
    )


__all__ = ["bind_design_provenance_fabric"]
