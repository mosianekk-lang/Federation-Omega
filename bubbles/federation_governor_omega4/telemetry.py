from __future__ import annotations


class FederationTelemetry:
    """Small shared metric surface; raw chat content is not recorded."""

    def __init__(self, registry):
        self.registry = registry

    def record(self, *, cache_hit=None, prevented_call=None, shim_bytes=None,
               retrieval_ms=None, stall_recovery=None):
        if cache_hit is not None:
            self.registry.update_metric("federation.cache_hit_rate", 1.0 if cache_hit else 0.0)
        if prevented_call is not None:
            self.registry.update_metric("federation.prevented_call_rate", 1.0 if prevented_call else 0.0)
        if shim_bytes is not None:
            self.registry.update_metric("federation.shim_bytes", float(shim_bytes))
        if retrieval_ms is not None:
            self.registry.update_metric("federation.retrieval_ms", float(retrieval_ms))
        if stall_recovery is not None:
            self.registry.update_metric("federation.stall_recovery_rate", 1.0 if stall_recovery else 0.0)

    def snapshot(self):
        keys = [
            "federation.cache_hit_rate",
            "federation.prevented_call_rate",
            "federation.shim_bytes",
            "federation.retrieval_ms",
            "federation.stall_recovery_rate",
        ]
        return {key: self.registry.metric(key) for key in keys}
