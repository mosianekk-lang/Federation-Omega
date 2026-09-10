from pathlib import Path
import json, os, subprocess, sys, time
from urllib import request
ROOT=Path(__file__).resolve().parents[1]
env=os.environ.copy(); env.update({'AEGIS_ENV':'development','AEGIS_CASE_STORE':'memory','AEGIS_EVIDENCE_BUCKET':'','AEGIS_PUBSUB_TOPIC':'','AEGIS_GCP_PROJECT':''})
p=subprocess.Popen([sys.executable,'-m','uvicorn','aegis_omega.api:app','--app-dir','src','--host','127.0.0.1','--port','18099'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    health=None
    for _ in range(30):
        try:
            with request.urlopen('http://127.0.0.1:18099/healthz', timeout=1) as r:
                health=json.load(r); break
        except Exception:
            time.sleep(.1)
    assert health and health['status']=='ok' and health['mode']=='defensive-only'
    payload={"request_id":"smoke-http-001","events":[
      {"event_id":"evt-a","device_id":"dev-a","event_class":"device_integrity","severity":.95,"confidence":.94,"source":"integrity","consent":True},
      {"event_id":"evt-b","device_id":"dev-a","event_class":"forensic_artifact","severity":.93,"confidence":.95,"source":"forensics","consent":True},
      {"event_id":"evt-c","device_id":"dev-a","event_class":"network_risk","severity":.88,"confidence":.90,"source":"network","consent":True},
      {"event_id":"evt-d","device_id":"dev-a","event_class":"identity_risk","severity":.84,"confidence":.90,"source":"identity","consent":True}
    ]}
    req=request.Request('http://127.0.0.1:18099/v1/assess',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    with request.urlopen(req, timeout=3) as r: assessment=json.load(r)
    assert assessment['requires_human_approval'] is True
    assert assessment['disposition'] in {'investigate','containment_recommended'}
    print(json.dumps({'health':health,'assessment_disposition':assessment['disposition'],'assessment_risk':assessment['risk_score']}))
finally:
    p.terminate()
    try: p.wait(timeout=3)
    except subprocess.TimeoutExpired: p.kill()
