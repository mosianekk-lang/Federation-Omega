import pytest

from .design_provenance_fabric import DesignProvenanceBridge
from .dpf_chatbridge_adapter import bind_design_provenance_fabric


class FakeRuntime:
    def __init__(self):
        self.full_fidelity = object()


def test_bind_design_provenance_fabric_uses_chatbridge_raw_authority():
    runtime = FakeRuntime()
    bridge = bind_design_provenance_fabric(runtime)
    assert isinstance(bridge, DesignProvenanceBridge)
    assert bridge.ledger is runtime.full_fidelity


def test_bind_design_provenance_fabric_rejects_runtime_without_full_fidelity():
    with pytest.raises(ValueError):
        bind_design_provenance_fabric(object())
