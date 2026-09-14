#!/usr/bin/env python3
import argparse, hashlib, json, math, pathlib

def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x); return 1.0 / (1.0 + z)
    z = math.exp(x); return z / (1.0 + z)

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument('--model',required=True); ns=ap.parse_args()
    path=pathlib.Path(ns.model); raw=path.read_bytes(); model=json.loads(raw)
    results=[]
    for case in model['cases']:
        x=case['input']
        hidden=[sigmoid(sum(wi*xi for wi,xi in zip(w,x))+b) for w,b in zip(model['hidden_weights'],model['hidden_bias'])]
        score=sigmoid(sum(w*h for w,h in zip(model['output_weights'],hidden))+model['output_bias'])
        predicted=int(score >= 0.5); expected=int(case['expected'])
        results.append({'input':x,'score':round(score,8),'predicted':predicted,'expected':expected,'pass':predicted==expected})
    ok=all(r['pass'] for r in results)
    receipt={'schema':'FUSE-AIOS-CPU-INFERENCE-RECEIPT-V1','model_sha256':hashlib.sha256(raw).hexdigest(),'cases':results,'status':'PASS' if ok else 'FAIL','truth':'LOCAL_CPU_NUMERIC_NN_INFERENCE_PROVED','llm_or_framework_runtime_proved':False}
    print(json.dumps(receipt,sort_keys=True))
    if not ok: raise SystemExit(1)
if __name__=='__main__': main()
