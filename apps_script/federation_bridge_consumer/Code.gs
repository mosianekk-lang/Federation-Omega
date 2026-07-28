const FED_BRIDGE = Object.freeze({
  controlSpreadsheetId: '1OsMaGUmAfv3iszkd6hbY6H1oNznYJ84uqtAga17xpj0',
  bridgeSheet: 'DB_ScriptRunBridge',
  proofSheet: 'DB_ScriptRunProof',
  version: 'FEDOMEGA-BRIDGE-CONSUMER-1.0.0',
  lockTimeoutMs: 25000,
  maxRowsPerRun: 10,
  allowedFunctions: Object.freeze([
    'INSTALL_SOURCE_PACKAGE',
    'gasSchedulerInstall',
    'processMetaExecutorQueueV2',
    'processSentinelQueue',
    'genesisCompleteSetup'
  ])
});

function installFederationBridgeConsumer() {
  const lock = LockService.getScriptLock();
  lock.waitLock(FED_BRIDGE.lockTimeoutMs);
  try {
    ScriptApp.getProjectTriggers()
      .filter(t => t.getHandlerFunction() === 'processFederationScriptRunBridge')
      .forEach(t => ScriptApp.deleteTrigger(t));
    const trigger = ScriptApp.newTrigger('processFederationScriptRunBridge').timeBased().everyMinutes(5).create();
    return {status:'INSTALLED',version:FED_BRIDGE.version,triggerId:trigger.getUniqueId(),checkedAt:new Date().toISOString()};
  } finally {
    lock.releaseLock();
  }
}

function processFederationScriptRunBridge() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(FED_BRIDGE.lockTimeoutMs)) return {status:'SKIPPED_LOCKED'};
  try {
    const ss = SpreadsheetApp.openById(FED_BRIDGE.controlSpreadsheetId);
    const bridge = requireSheet_(ss, FED_BRIDGE.bridgeSheet);
    const proof = requireSheet_(ss, FED_BRIDGE.proofSheet);
    const values = bridge.getDataRange().getValues();
    if (values.length < 2) return {status:'IDLE'};
    const headers = values[0].map(String);
    const idx = index_(headers);
    let processed = 0;
    for (let r = 1; r < values.length && processed < FED_BRIDGE.maxRowsPerRun; r++) {
      const row = values[r];
      const runId = String(row[idx.runId] || '').trim();
      const status = String(row[idx.status] || '').trim();
      if (!runId || status !== 'READY') continue;
      const payload = parseJson_(String(row[idx.payload] || ''));
      if (!dependenciesSatisfied_(values, idx, payload.dependsOn)) continue;
      claim_(bridge, r + 1, idx, runId);
      try {
        const fn = String(row[idx.fn] || '').trim();
        if (FED_BRIDGE.allowedFunctions.indexOf(fn) < 0) throw new Error('FUNCTION_NOT_ALLOWED:' + fn);
        const result = dispatch_(fn, payload);
        complete_(bridge, r + 1, idx, result);
        appendProof_(proof, runId, 'ACTION_SPECIFIC_RESULT', result, 'PROVEN');
      } catch (err) {
        fail_(bridge, r + 1, idx, err);
        appendProof_(proof, runId, 'EXECUTION_FAILURE', {error:safeError_(err)}, 'FAILED_EXACT');
      }
      processed++;
    }
    return {status:'RUN_COMPLETE',processed:processed,version:FED_BRIDGE.version,checkedAt:new Date().toISOString()};
  } finally {
    lock.releaseLock();
  }
}

function dispatch_(fn, payload) {
  if (fn === 'INSTALL_SOURCE_PACKAGE') throw new Error('INSTALL_SOURCE_PACKAGE_REQUIRES_BOUND_INSTALLER');
  const target = this[fn];
  if (typeof target !== 'function') throw new Error('FUNCTION_NOT_PRESENT:' + fn);
  const result = target(payload || {});
  return {functionName:fn,result:result,checkedAt:new Date().toISOString()};
}

function dependenciesSatisfied_(values, idx, dependsOn) {
  if (!dependsOn) return true;
  for (let i = 1; i < values.length; i++) {
    if (String(values[i][idx.runId] || '') === String(dependsOn)) {
      return ['DONE','CLOSED_VERIFIED','PROVEN'].indexOf(String(values[i][idx.status] || '')) >= 0;
    }
  }
  return false;
}

function index_(h) {
  const find = (names, fallback) => { for (let i=0;i<names.length;i++){ const p=h.indexOf(names[i]); if(p>=0)return p; } return fallback; };
  return {
    runId: find(['Run_ID','ID'],0),
    status: find(['Status'],2),
    fn: find(['Function','Action'],4),
    payload: find(['Payload','Payload_JSON'],5),
    result: find(['Result'],9),
    processedAt: find(['ProcessedAt'],10),
    notes: find(['Notes'],11)
  };
}

function claim_(sheet,row,idx,runId){ set_(sheet,row,[[idx.status,'RUNNING'],[idx.processedAt,new Date().toISOString()],[idx.notes,'CLAIMED:'+runId]]); }
function complete_(sheet,row,idx,result){ set_(sheet,row,[[idx.status,'DONE'],[idx.result,JSON.stringify(result)],[idx.processedAt,new Date().toISOString()]]); }
function fail_(sheet,row,idx,err){ set_(sheet,row,[[idx.status,'FAILED_EXACT'],[idx.result,JSON.stringify({error:safeError_(err)})],[idx.processedAt,new Date().toISOString()]]); }
function set_(sheet,row,entries){ entries.forEach(e=>{ if(e[0]>=0) sheet.getRange(row,e[0]+1).setValue(e[1]); }); SpreadsheetApp.flush(); }
function appendProof_(sheet,runId,expected,actual,status){ sheet.appendRow(['SRP-'+Utilities.getUuid(),new Date().toISOString(),runId,expected,JSON.stringify(actual),status,'Bridge consumer '+FED_BRIDGE.version]); }
function requireSheet_(ss,name){ const sh=ss.getSheetByName(name); if(!sh) throw new Error('MISSING_SHEET:'+name); return sh; }
function parseJson_(text){ if(!text) return {}; try{return JSON.parse(text);}catch(e){throw new Error('INVALID_JSON:'+e.message);} }
function safeError_(err){ return String(err && err.stack ? err.stack : err).slice(0,5000); }
