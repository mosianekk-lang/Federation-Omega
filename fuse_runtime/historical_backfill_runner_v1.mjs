import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { runTen, persistReceipt } from './autonomous-improvement-loop-v1.mjs';

const ROOT=path.join(process.env.LOCALAPPDATA||path.join(os.homedir(),'AppData','Local'),'FUSE','SovereignPlane');
const sha=v=>crypto.createHash('sha256').update(JSON.stringify(v)).digest('hex');

export function runEvidenceCorpus(manifestPath){
  const corpus=JSON.parse(fs.readFileSync(manifestPath,'utf8'));
  const scope=String(corpus.scope||'recoverable-evidence').replace(/[^a-zA-Z0-9._-]+/g,'-');
  const dir=path.join(ROOT,'state','autonomous-improvement',scope);
  fs.mkdirSync(dir,{recursive:true});
  const receipts=[];
  for(const record of corpus.records||[]){
    const r=runTen(record,{iterations:10,target_type:corpus.record_type||'RECOVERABLE_EVIDENCE',historical:true});
    r.persisted_path=persistReceipt(r,dir);
    receipts.push(r);
  }
  const summary={
    schema:'FUSE_RECOVERABLE_EVIDENCE_10X_BACKFILL_SUMMARY_V1',
    scope:corpus.scope,
    record_type:corpus.record_type,
    record_count:receipts.length,
    iterations_per_record:10,
    total_iterations:receipts.reduce((n,r)=>n+r.iterations_completed,0),
    all_profiles_complete:receipts.every(r=>r.final_state==='TEN_ITERATIONS_COMPLETE_VERIFIED'),
    counts_as_exact_native_chat:corpus.counts_as_exact_native_chat===true,
    native_account_totality:corpus.native_account_totality||'UNVERIFIED',
    truth_boundary:corpus.truth_boundary,
    receipt_digests:receipts.map(r=>({target_id:r.target_id,sha256:r.receipt_sha256})),
    generated_at:new Date().toISOString()
  };
  summary.receipt_sha256=sha(summary);
  fs.writeFileSync(path.join(dir,'SUMMARY-'+summary.receipt_sha256.slice(0,16)+'.json'),JSON.stringify(summary,null,2));
  return summary;
}

if(process.argv[1]&&import.meta.url===new URL('file:///'+process.argv[1].replaceAll('\\','/')).href){
  if(!process.argv[2])throw new Error('MANIFEST_PATH_REQUIRED');
  console.log(JSON.stringify(runEvidenceCorpus(process.argv[2]),null,2));
}