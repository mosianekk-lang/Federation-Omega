"""Execute Apps Script semantics in Node; effectful Google services are denied."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps_script/cognitive_surface_bridge/FuseCognitiveSurfaceBridge.gs"
COURT = r"""
const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const context={Utilities:{DigestAlgorithm:{SHA_256:'sha256'},Charset:{UTF_8:'utf8'},
 computeDigest:(algorithm,text)=>[...crypto.createHash(algorithm).update(text,'utf8').digest()],
 newBlob:text=>({getBytes:()=>[...Buffer.from(text,'utf8')]})}};
let serviceTouches=0;
for(const service of ['SpreadsheetApp','LockService','PropertiesService','UrlFetchApp','ScriptApp']){
 Object.defineProperty(context,service,{get(){serviceTouches++;throw Error('EFFECTFUL_SERVICE_FORBIDDEN:'+service);}});
}
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const packet=()=>({mission_id:'M-1',objective:'Keep the exact objective',idempotency_key:'M-1:1',
 acceptance_predicates:['verified result'],required_capabilities:['reasoning'],evidence_refs:['evidence:1'],
 uncertainty:['unknown:1'],falsifiers:['falsifier:1'],authority_ceiling:'A0_INTERNAL',maximum_effect:'OBSERVE',
 privacy_class:'P2_CONFIDENTIAL',cost_ceiling:0,proof_floor:'INDEPENDENT_READBACK',deadline_seconds:600,
 surface_ids:['GOOGLE-APPS-SCRIPT'],automation_required:true,research_required:false,creative_required:false,challenger_required:false});
const reject=(change,code)=>assert.throws(()=>context.fuseCognitiveNormalizePacket_({...packet(),...change}),code);
const p=packet(),prepared=context.fuseCognitiveQueueInternal(p);
assert.equal(prepared.state,'PREPARED_NOT_QUEUED');assert.equal(prepared.write_performed,false);
assert.equal(prepared.provider_effect_authorized,false);assert.equal(prepared.provider_execution_proven,false);
for(const [key,value] of Object.entries(p))assert.equal(JSON.stringify(prepared.packet[key]),JSON.stringify(value));
assert.equal(prepared.digest,context.fuseCognitivePacketDigest_(p));
const changed=context.fuseCognitiveQueueInternal({...p,objective:'Changed objective'});
assert.notEqual(changed.digest,prepared.digest);assert.equal(changed.state,'PREPARED_NOT_QUEUED');
assert.equal(context.fuseCognitiveQueueInternal({...p,idempotency_key:'=1+1'}).packet.idempotency_key,'=1+1');
const heartbeat=context.fuseCognitiveHeartbeat();
assert.equal(heartbeat.state,'SOURCE_AVAILABLE');assert.equal(heartbeat.runtime_readiness,'UNASSESSED');
assert.equal(heartbeat.canonical_writer_binding,'UNASSESSED');assert.equal(heartbeat.provider_execution_proven,false);
for(const surface of ['constructor','toString','__proto__','UNKNOWN'])reject({surface_ids:[surface]},/SURFACE_NOT_ALLOWLISTED/);
for(const deadline of ['not-a-number',NaN,Infinity,-Infinity,0,1.5,true])reject({deadline_seconds:deadline},/DEADLINE_INVALID/);
for(const cost of [NaN,Infinity,-1,'0',true])reject({cost_ceiling:cost},/COST_CEILING_INVALID/);
for(const key of ['acceptance_predicates','required_capabilities','evidence_refs','uncertainty','falsifiers']){
 reject({[key]:Array(33).fill('value')},/ARRAY_TOO_LARGE/);reject({[key]:['']},/STRING_REQUIRED/);reject({[key]:'not-an-array'},/ARRAY_REQUIRED/);
}
reject({acceptance_predicates:[]},/ACCEPTANCE_REQUIRED/);
const missing=packet();delete missing.acceptance_predicates;
assert.throws(()=>context.fuseCognitiveNormalizePacket_(missing),/ACCEPTANCE_REQUIRED/);
reject({objective:'界'.repeat(11000)},/PACKET_TOO_LARGE/);
reject({provider_effect_authorized:'false'},/EFFECT_AUTHORITY_FORBIDDEN/);reject({external_effect_authorized:true},/EFFECT_AUTHORITY_FORBIDDEN/);
reject({maximum_effect:'REVERSIBLE_WRITE'},/EFFECT_CEILING_EXCEEDED/);reject({authority_ceiling:'A2_OWNER_RESERVED'},/AUTHORITY_CEILING_EXCEEDED/);
for(const key of ['automation_required','research_required','creative_required','challenger_required'])reject({[key]:'false'},/BOOLEAN_REQUIRED/);
for(const key of ['objective','acceptance_predicates','authority_ceiling','privacy_class','cost_ceiling','required_capabilities',
 'evidence_refs','uncertainty','falsifiers','deadline_seconds','proof_floor','idempotency_key','maximum_effect']){
 const value=p[key],alternate=Array.isArray(value)?[...value,'changed']:typeof value==='number'?value+1:
 key==='authority_ceiling'?'A1_INTERNAL':key==='maximum_effect'?'INTERNAL':value+' changed';
 assert.notEqual(context.fuseCognitivePacketDigest_({...p,[key]:alternate}),prepared.digest,key);
}
p.acceptance_predicates.push('caller mutation');assert.equal(prepared.packet.acceptance_predicates.length,1);
assert.equal(serviceTouches,0);console.log(JSON.stringify({passed:true,effectful_service_accesses:serviceTouches}));
"""


class CognitiveSurfaceAppsScriptBridgeTests(unittest.TestCase):
    def test_actual_bridge_validates_and_prepares_without_queue_effects(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required; Apps Script behavioral coverage cannot be skipped")
        result = subprocess.run([node, "-e", COURT, str(SOURCE)], text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:])
        receipt = json.loads(result.stdout)
        self.assertTrue(receipt["passed"])
        self.assertEqual(receipt["effectful_service_accesses"], 0)


if __name__ == "__main__":
    unittest.main()
