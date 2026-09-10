from pathlib import Path
import tempfile
import pytest
from federation.run_store_v1 import RunStore, VersionConflict




def test_checkpoint_cas_and_hash():
    with tempfile.TemporaryDirectory() as td:
        s=RunStore(Path(td)/"x.db")
        c1=s.put("M",{"a":1},expected_version=None)
        c2=s.put("M",{"a":2},expected_version=1)
        assert c2.version==2 and s.read("M").state["a"]==2
        with pytest.raises(VersionConflict): s.put("M",{"a":3},expected_version=1)




def test_reentry_is_idempotent():
    with tempfile.TemporaryDirectory() as td:
        s=RunStore(Path(td)/"x.db")
        c=s.put("M",{"a":1},expected_version=None)
        a=s.enqueue_reentry("M",c,{"x":1}); b=s.enqueue_reentry("M",c,{"x":1})
        assert a==b and len(s.ready_reentries("M"))==1
