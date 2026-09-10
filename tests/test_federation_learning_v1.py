from pathlib import Path
import tempfile
import pytest
from federation.federation_learning_v1 import FederationLearningLedger, LearningEvent, plan_receiver_propagation




def event():
    return LearningEvent("E1","NOW","M","BUILD","V5",{},"LOCAL_TESTED","TEST","A","B",receiver_compatibility=("CFBE",),rollback_ref="V4")




def test_learning_ledger_hash_chain():
    with tempfile.TemporaryDirectory() as td:
        l=FederationLearningLedger(Path(td)/"l.jsonl")
        l.append(event())
        e2=LearningEvent("E2","NOW","M","BUILD","V5",{},"LOCAL_TESTED","TEST","A","B",receiver_compatibility=("CFBE",),rollback_ref="V4")
        l.append(e2)
        assert l.verify()==(True,2)




def test_no_private_chain_of_thought_storage():
    bad=LearningEvent("E","NOW","M","BUILD","V5",{},"LOCAL_TESTED","TEST","A","B",private_chain_of_thought_stored=True)
    with pytest.raises(ValueError): bad.validate()




def test_receiver_propagation_requires_compatibility_regression_and_rollback():
    e=event()
    out=plan_receiver_propagation(e,[
        ("CFBE",True,True,"rb"),("STRATEGIC_FUSE",True,True,"rb"),("CFBE",True,False,"rb"),("CFBE",True,True,"")
    ])
    assert [x["action"] for x in out]==["ELIGIBLE","HOLD","HOLD","HOLD"]
