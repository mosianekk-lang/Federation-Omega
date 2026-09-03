const FED_BRIDGE = Object.freeze({
  controlSpreadsheetId: '1OsMaGUmAfv3iszkd6hbY6H1oNznYJ84uqtAga17xpj0',
  bridgeSheet: 'DB_ScriptRunBridge',
  proofSheet: 'DB_ScriptRunProof',
  version: 'FEDOMEGA-BRIDGE-CONSUMER-1.1.0-KIOAS-HARDENED',
  lockTimeoutMs: 25000,
  maxRowsPerRun: 10,
  functionContracts: Object.freeze({
    INSTALL_SOURCE_PACKAGE: Object.freeze({risk:'HIGH', route:'EXACT_SOURCE_AUTHORITY_CELL'}),
    gasSchedulerInstall: Object.freeze({risk:'HIGH', route:'EXACT_GNS3_RECOVERY_CELL'}),
    processMetaExecutorQueueV2: Object.freeze({risk:'HIGH', route:'METAEXECUTOR_ACTION_SPECIFIC_GATE'}),
    processSentinelQueue: Object.freeze({risk:'HIGH', route:'SENTINEL_ACTION_SPECIFIC_GATE'}),
    genesisCompleteSetup: Object.freeze({risk:'HIGH', route:'GENESIS_ACTION_SPECIFIC_GATE'})
  })
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
  } finally { lock.releaseLock(); }
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
      const fn = String(row[idx.fn] || '').trim();
      const contract = FED_BRIDGE.functionContracts[fn];
      if (!contract) {
        hold_(bridge, r + 1, idx, runId, 'FUNCTION_NOT_CONTRACTED:' + fn);
        appendProof_(proof, runId, 'AUTHORITY_PREFLIGHT', {functionName:fn,state:'HELD',reason:'FUNCTION_NOT_CONTRACTED'}, 'HELD_EXACT');
        processed++;
        continue;
      }
      if (contract.risk === 'HIGH' || contract.risk === 'CRITICAL') {
        const held = {functionName:fn,state:'HELD_AUTHORITY',risk:contract.risk,route:contract.route,providerEffect:false,checkedAt:new Date().toISOString()};
        hold_(bridge, r + 1, idx, runId, 'HELD_AUTHORITY_ACTION_SPECIFIC_CELL_REQUIRED:' + contract.route);
        appendProof_(proof, runId, 'AUTHORITY_PREFLIGHT', held, 'HELD_EXACT');
        processed++;
        continue;
      }
      hold_(bridge, r + 1, idx, runId, 'NO_LOW_RISK_GENERIC_FUNCTIONS_ADMITTED');
      appendProof_(proof, runId, 'AUTHORITY_PREFLIGHT', {functionName:fn,state:'HELD',reason:'NO_LOW_RISK_GENERIC_FUNCTIONS_ADMITTED'}, 'HELD_EXACT');
      processed++;
    }
    return {status:'RUN_COMPLETE',processed:processed,version:FED_BRIDGE.version,providerEffect:false,checkedAt:new Date().toISOString()};
  } finally { lock.releaseLock(); }
}

function dispatch_() { throw new Error('GENERIC_DISPATCH_DISABLED_USE_ACTION_SPECIFIC_CELL'); }

function index_(h) {
  const find = (names, fallback) => { for (let i=0;i<names.length;i++){ const p=h.indexOf(names[i]); if(p>=0)return p; } return fallback; };
  return {runId:find(['Run_ID','ID'],0),status:find(['Status'],2),fn:find(['Function','Action'],4),payload:find(['Payload','Payload_JSON'],5),result:find(['Result'],9),processedAt:find(['ProcessedAt'],10),notes:find(['Notes'],11)};
}
function hold_(sheet,row,idx,runId,reason){ set_(sheet,row,[[idx.status,'HELD_AUTHORITY'],[idx.processedAt,new Date().toISOString()],[idx.result,JSON.stringify({runId:runId,state:'HELD_AUTHORITY',reason:reason,providerEffect:false})],[idx.notes,reason]]); }
function set_(sheet,row,entries){ entries.forEach(e=>{ if(e[0]>=0) sheet.getRange(row,e[0]+1).setValue(e[1]); }); SpreadsheetApp.flush(); }
function appendProof_(sheet,runId,expected,actual,status){ sheet.appendRow(['SRP-'+Utilities.getUuid(),new Date().toISOString(),runId,expected,JSON.stringify(actual),status,'Bridge consumer '+FED_BRIDGE.version]); }
function requireSheet_(ss,name){ const sh=ss.getSheetByName(name); if(!sh) throw new Error('MISSING_SHEET:'+name); return sh; }
