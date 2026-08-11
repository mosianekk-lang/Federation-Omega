const SENTINEL = Object.freeze({
  spreadsheetId: '1LSVjK9YK6u2CMrvetOcXpun4VQnOh5cE6b3w6z_KTHg',
  queueSheet: 'SENTINEL_Activation_Queue',
  heartbeatSheet: 'Heartbeat',
  failureSheet: 'Failures',
  processorVersion: 'FEDOMEGA-GAS-1.0.0',
  maxRowsPerRun: 25,
  lockTimeoutMs: 25000,
});

function installSentinelProcessor() {
  const lock = LockService.getScriptLock();
  lock.waitLock(SENTINEL.lockTimeoutMs);
  try {
    removeSentinelTriggers_();
    ScriptApp.newTrigger('processSentinelQueue').timeBased().everyMinutes(5).create();
    writeHeartbeat_('INSTALLED', { triggerCount: listSentinelTriggers_().length });
    return activationReceipt_('FEDOMEGA-GAS-INSTALLED');
  } finally {
    lock.releaseLock();
  }
}

function processSentinelQueue() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(SENTINEL.lockTimeoutMs)) {
    writeHeartbeat_('SKIPPED_LOCKED', {});
    return;
  }
  const started = new Date();
  let processed = 0;
  let failed = 0;
  try {
    const ss = SpreadsheetApp.openById(SENTINEL.spreadsheetId);
    const sheet = requireSheet_(ss, SENTINEL.queueSheet);
    const values = sheet.getDataRange().getValues();
    if (values.length < 2) {
      writeHeartbeat_('IDLE_EMPTY_QUEUE', {});
      return;
    }
    const headers = values[0].map(String);
    const idx = headerIndex_(headers);
    for (let r = 1; r < values.length && processed < SENTINEL.maxRowsPerRun; r++) {
      const row = values[r];
      const commandId = String(row[idx.commandId] || '').trim();
      const status = String(row[idx.status] || '').trim();
      if (!commandId || !isRunnableStatus_(status)) continue;
      const idemKey = commandId + '|' + String(row[idx.command] || '') + '|' + String(row[idx.payload] || '');
      if (alreadyProcessed_(idemKey)) continue;
      try {
        markRunning_(sheet, r + 1, idx, commandId);
        const result = dispatchCommand_(String(row[idx.command] || ''), String(row[idx.payload] || ''), commandId);
        markComplete_(sheet, r + 1, idx, result);
        rememberProcessed_(idemKey, result.receipt || 'OK');
      } catch (err) {
        failed++;
        markFailed_(sheet, r + 1, idx, err);
        writeFailure_(commandId, err);
      }
      processed++;
    }
    writeHeartbeat_('RUN_COMPLETE', {
      processed: processed,
      failed: failed,
      durationMs: new Date().getTime() - started.getTime(),
    });
  } catch (err) {
    writeHeartbeat_('RUN_FATAL', { error: safeError_(err) });
    throw err;
  } finally {
    lock.releaseLock();
  }
}

function dispatchCommand_(command, payloadText, commandId) {
  const payload = parseJson_(payloadText);
  switch (command) {
    case 'HEARTBEAT_CANARY':
      return { receipt: 'GAS-CANARY-' + commandId, result: { ok: true, payload: payload } };
    case 'READ_SPREADSHEET_RANGE':
      return readSpreadsheetRange_(payload, commandId);
    case 'WRITE_SPREADSHEET_CELL':
      return writeSpreadsheetCell_(payload, commandId);
    default:
      throw new Error('UNSUPPORTED_COMMAND:' + command);
  }
}

function readSpreadsheetRange_(payload, commandId) {
  if (!payload.spreadsheetId || !payload.range) throw new Error('INVALID_READ_PAYLOAD');
  const ss = SpreadsheetApp.openById(String(payload.spreadsheetId));
  const values = ss.getRange(String(payload.range)).getDisplayValues();
  return { receipt: 'GAS-READ-' + commandId, result: { rows: values.length, values: values } };
}

function writeSpreadsheetCell_(payload, commandId) {
  if (!payload.spreadsheetId || !payload.range) throw new Error('INVALID_WRITE_PAYLOAD');
  const ss = SpreadsheetApp.openById(String(payload.spreadsheetId));
  const range = ss.getRange(String(payload.range));
  range.setValue(payload.value == null ? '' : payload.value);
  SpreadsheetApp.flush();
  const readback = range.getDisplayValue();
  if (String(readback) !== String(payload.value == null ? '' : payload.value)) throw new Error('WRITE_READBACK_MISMATCH');
  return { receipt: 'GAS-WRITE-' + commandId, result: { readback: readback } };
}

function headerIndex_(headers) {
  function find(names, fallback) {
    for (let i = 0; i < names.length; i++) {
      const p = headers.indexOf(names[i]);
      if (p >= 0) return p;
    }
    return fallback;
  }
  return {
    commandId: find(['Command_ID', 'CommandId', 'command_id'], 0),
    command: find(['Command', 'Action'], 1),
    payload: find(['Payload_JSON', 'Payload', 'Input_JSON'], 2),
    status: find(['Status'], 5),
    updatedAt: find(['Updated_At', 'UpdatedAt', 'Last_Update'], 6),
    result: find(['Result_JSON', 'Result'], 7),
    receipt: find(['Receipt'], 8),
    nextAction: find(['Next_Action', 'NextAction'], 9),
  };
}

function isRunnableStatus_(status) {
  return ['QUEUED', 'READY', 'PENDING', 'USER_AUTHORISED_FULL_AUTOMATION', 'RETRY_READY'].indexOf(status) >= 0;
}

function markRunning_(sheet, row, idx, commandId) {
  setCells_(sheet, row, [[idx.status, 'RUNNING_GAS'], [idx.updatedAt, isoNow_()], [idx.receipt, 'GAS-START-' + commandId]]);
}

function markComplete_(sheet, row, idx, outcome) {
  setCells_(sheet, row, [
    [idx.status, 'CLOSED_VERIFIED_GAS'],
    [idx.updatedAt, isoNow_()],
    [idx.result, JSON.stringify(outcome.result || {})],
    [idx.receipt, outcome.receipt || 'GAS-COMPLETE'],
    [idx.nextAction, 'NONE'],
  ]);
}

function markFailed_(sheet, row, idx, err) {
  setCells_(sheet, row, [
    [idx.status, 'FAILED_GAS_EXACT'],
    [idx.updatedAt, isoNow_()],
    [idx.result, JSON.stringify({ error: safeError_(err) })],
    [idx.receipt, 'GAS-FAIL-' + Utilities.getUuid()],
    [idx.nextAction, 'REPAIR_FROM_EXACT_ERROR'],
  ]);
}

function setCells_(sheet, row, entries) {
  entries.forEach(function(entry) {
    const col = Number(entry[0]);
    if (col >= 0) sheet.getRange(row, col + 1).setValue(entry[1]);
  });
  SpreadsheetApp.flush();
}

function writeHeartbeat_(status, details) {
  const ss = SpreadsheetApp.openById(SENTINEL.spreadsheetId);
  const sheet = getOrCreateSheet_(ss, SENTINEL.heartbeatSheet, ['checkedAt', 'version', 'status', 'scriptId', 'detailsJson']);
  sheet.appendRow([isoNow_(), SENTINEL.processorVersion, status, ScriptApp.getScriptId(), JSON.stringify(details || {})]);
}

function writeFailure_(commandId, err) {
  const ss = SpreadsheetApp.openById(SENTINEL.spreadsheetId);
  const sheet = getOrCreateSheet_(ss, SENTINEL.failureSheet, ['failedAt', 'version', 'commandId', 'error']);
  sheet.appendRow([isoNow_(), SENTINEL.processorVersion, commandId, safeError_(err)]);
}

function activationReceipt_(receipt) {
  return {
    receipt: receipt,
    version: SENTINEL.processorVersion,
    scriptId: ScriptApp.getScriptId(),
    queueSpreadsheetId: SENTINEL.spreadsheetId,
    triggerCount: listSentinelTriggers_().length,
    checkedAt: isoNow_(),
  };
}

function listSentinelTriggers_() {
  return ScriptApp.getProjectTriggers().filter(function(t) { return t.getHandlerFunction() === 'processSentinelQueue'; });
}

function removeSentinelTriggers_() {
  listSentinelTriggers_().forEach(function(t) { ScriptApp.deleteTrigger(t); });
}

function alreadyProcessed_(key) {
  return CacheService.getScriptCache().get(key) !== null || PropertiesService.getScriptProperties().getProperty('idem:' + key) !== null;
}

function rememberProcessed_(key, receipt) {
  CacheService.getScriptCache().put(key, receipt, 21600);
  PropertiesService.getScriptProperties().setProperty('idem:' + key, receipt);
}

function parseJson_(text) {
  if (!text) return {};
  try { return JSON.parse(text); } catch (err) { throw new Error('INVALID_JSON:' + err.message); }
}

function requireSheet_(ss, name) {
  const sheet = ss.getSheetByName(name);
  if (!sheet) throw new Error('MISSING_SHEET:' + name);
  return sheet;
}

function getOrCreateSheet_(ss, name, headers) {
  let sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);
  if (sheet.getLastRow() === 0) sheet.appendRow(headers);
  return sheet;
}

function safeError_(err) {
  return String(err && err.stack ? err.stack : err).slice(0, 5000);
}

function isoNow_() {
  return new Date().toISOString();
}
