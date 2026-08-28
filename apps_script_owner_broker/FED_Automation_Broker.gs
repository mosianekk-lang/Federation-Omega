/**
 * FEDERATION Ω — OWNER-OAUTH APPS SCRIPT BROKER v1.0.0
 *
 * Runs inside the already-authorized owner Apps Script control surface.
 * It is deliberately separate from the Cloud Run service-account executor.
 *
 * Shared ingress: Federation Ω — Shared Automation Authority Fabric
 *   17WRSvjj98RbOKZrnTefcZkfK-z9gZYdZX_pACm8VuOQ
 * Canonical target registry: Federation Lab Kernel / LAB_REGISTRY
 *   1q5dZZCg_wzOVK6XqBIzs0A2ZMv2Td6Cd05SerQ8IWRM
 *
 * Supported actions:
 *   APPS_SCRIPT_GET_CONTENT
 *   APPS_SCRIPT_GET_DEPLOYMENTS
 *   APPS_SCRIPT_UPSERT_FILE
 *   APPS_SCRIPT_REPLACE_CONTENT
 *   APPS_SCRIPT_ROLLBACK_CONTENT
 *   APPS_SCRIPT_CREATE_VERSION
 *   APPS_SCRIPT_CREATE_DEPLOYMENT
 *   APPS_SCRIPT_UPDATE_DEPLOYMENT
 *
 * Direct scripts.run is intentionally NOT provided here as a generic action.
 * Google requires API-executable deployment and a common standard Cloud
 * project between caller and target. Runtime execution stays a separate proof
 * gate until those exact conditions are established for the target.
 */

const FED_AS_BROKER = Object.freeze({
  VERSION: '1.0.0',
  FABRIC_ID: '17WRSvjj98RbOKZrnTefcZkfK-z9gZYdZX_pACm8VuOQ',
  LAB_KERNEL_CONTROL_ID: '1q5dZZCg_wzOVK6XqBIzs0A2ZMv2Td6Cd05SerQ8IWRM',
  QUEUE: 'COMMAND_QUEUE',
  RECEIPTS: 'COMMAND_RECEIPTS',
  LEASES: 'AUTHORITY_LEASES',
  HEARTBEAT: 'RUNTIME_HEARTBEAT',
  BROKER_STATE: 'APPS_SCRIPT_BROKER_STATE',
  LAB_REGISTRY: 'LAB_REGISTRY',
  API_ROOT: 'https://script.googleapis.com/v1',
  HANDLER: 'FED_authorityFabricAppsScriptTick',
  BACKUP_FOLDER: 'Federation Automation Apps Script Backups',
  LOCK_MS: 25000,
  MAX_BATCH: 20,
  LOGICAL_TZ: 'Africa/Johannesburg'
});

const FED_AS_ACTIONS = Object.freeze({
  APPS_SCRIPT_GET_CONTENT: 'READ',
  APPS_SCRIPT_GET_DEPLOYMENTS: 'READ',
  APPS_SCRIPT_UPSERT_FILE: 'CONTROL_PLANE_WRITE',
  APPS_SCRIPT_REPLACE_CONTENT: 'CONTROL_PLANE_WRITE',
  APPS_SCRIPT_ROLLBACK_CONTENT: 'CONTROL_PLANE_WRITE',
  APPS_SCRIPT_CREATE_VERSION: 'CONTROL_PLANE_WRITE',
  APPS_SCRIPT_CREATE_DEPLOYMENT: 'CONTROL_PLANE_WRITE',
  APPS_SCRIPT_UPDATE_DEPLOYMENT: 'CONTROL_PLANE_WRITE'
});

// Self-installing bootstrap: the module is added through the existing protected
// code manager. On the next already-installed host trigger execution this IIFE
// installs the broker trigger exactly once. Failures are swallowed and written
// later by FED_authorityFabricAppsScriptTick so the existing host stays healthy.
var FED_AS_BROKER_BOOTSTRAP = (function () {
  try {
    FED_asEnsureTrigger_();
    return true;
  } catch (error) {
    console.log('FED AS broker bootstrap deferred: ' + String(error));
    return false;
  }
})();

function FED_authorityFabricAppsScriptTick() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(FED_AS_BROKER.LOCK_MS)) {
    return {status: 'BLOCKED', reason: 'BROKER_ALREADY_RUNNING'};
  }

  const started = Date.now();
  const processed = [];
  try {
    const fabric = SpreadsheetApp.openById(FED_AS_BROKER.FABRIC_ID);
    const queue = fabric.getSheetByName(FED_AS_BROKER.QUEUE);
    if (!queue) throw new Error('COMMAND_QUEUE missing');

    const values = queue.getDataRange().getValues();
    if (values.length < 2) {
      FED_asHeartbeat_(fabric, processed, started);
      return {status: 'DONE', processed: []};
    }

    const completedIdempotency = FED_asCompletedIdempotency_(values);
    let count = 0;

    for (let i = 1; i < values.length && count < FED_AS_BROKER.MAX_BATCH; i++) {
      const row = values[i];
      if (String(row[14] || '') !== 'QUEUED') continue;
      if (String(row[6] || '') !== 'apps_script') continue;

      const command = FED_asParseCommand_(row, i + 1);
      const terminal = FED_asProcessOne_(fabric, queue, command, completedIdempotency);
      processed.push(terminal);
      count++;
    }

    FED_asHeartbeat_(fabric, processed, started);
    FED_asWriteBrokerState_(fabric, 'LAST_TICK', 'DONE', {
      processed: processed.length,
      elapsedMs: Date.now() - started
    });

    return {status: 'DONE', processed: processed, elapsedMs: Date.now() - started};
  } catch (error) {
    try {
      const fabric = SpreadsheetApp.openById(FED_AS_BROKER.FABRIC_ID);
      FED_asWriteBrokerState_(fabric, 'LAST_TICK', 'FAILED', FED_asError_(error));
    } catch (_) {}
    return {status: 'FAILED', error: FED_asError_(error)};
  } finally {
    lock.releaseLock();
  }
}

function FED_asProcessOne_(fabric, queue, command, completedIdempotency) {
  const startedAt = FED_asNow_();
  const receiptId = 'RCP-AS-' + Utilities.getUuid();

  if (command.idempotencyKey && completedIdempotency[command.idempotencyKey]) {
    FED_asReceipt_(fabric, receiptId, command, 'REJECTED', startedAt,
      'IDEMPOTENCY_REPLAY_BLOCKED', {classification: 'DUPLICATE_ALREADY_COMPLETED'}, false);
    FED_asFinishQueue_(queue, command.rowNumber, 'REJECTED', receiptId, 'IDEMPOTENCY_REPLAY');
    return {commandId: command.commandId, state: 'REJECTED'};
  }

  const targetSet = FED_asCanonicalTargetSet_();
  if (!command.scriptId || !targetSet[command.scriptId]) {
    FED_asReceipt_(fabric, receiptId, command, 'REJECTED', startedAt,
      'TARGET_NOT_IN_LAB_REGISTRY', {scriptId: command.scriptId}, false);
    FED_asFinishQueue_(queue, command.rowNumber, 'REJECTED', receiptId, 'TARGET_NOT_CANONICAL');
    return {commandId: command.commandId, state: 'REJECTED'};
  }

  const effect = FED_AS_ACTIONS[command.action];
  if (!effect) {
    FED_asReceipt_(fabric, receiptId, command, 'REJECTED', startedAt,
      'ACTION_NOT_ALLOWLISTED', {action: command.action}, false);
    FED_asFinishQueue_(queue, command.rowNumber, 'REJECTED', receiptId, 'ACTION_NOT_ALLOWLISTED');
    return {commandId: command.commandId, state: 'REJECTED'};
  }

  const decision = FED_asAuthorize_(fabric, command, effect);
  if (!decision.allowed) {
    FED_asReceipt_(fabric, receiptId, command, 'REJECTED', startedAt,
      decision.reason, {decision: decision}, false);
    FED_asFinishQueue_(queue, command.rowNumber, 'REJECTED', receiptId, 'POLICY_REJECTED');
    return {commandId: command.commandId, state: 'REJECTED'};
  }

  const claimUntil = new Date(Date.now() + 5 * 60 * 1000).toISOString();
  queue.getRange(command.rowNumber, 15, 1, 5).setValues([[
    'EXECUTING',
    Number(command.attempts || 0) + 1,
    'OWNER_OAUTH_APPS_SCRIPT_BROKER',
    claimUntil,
    startedAt
  ]]);
  SpreadsheetApp.flush();

  if (decision.consumeLease) {
    FED_asConsumeLease_(fabric, command.leaseId);
  }

  try {
    const result = FED_asExecute_(command);
    const state = result.status || 'FAILED';
    FED_asReceipt_(fabric, receiptId, command, state, startedAt,
      result.semanticReadback || '', result.proof || {}, Boolean(result.productionEffect));
    FED_asFinishQueue_(queue, command.rowNumber, state, receiptId, '');
    if (command.idempotencyKey && (state === 'DONE' || state === 'PARTIAL')) {
      completedIdempotency[command.idempotencyKey] = true;
    }
    return {commandId: command.commandId, state: state, receiptId: receiptId};
  } catch (error) {
    FED_asReceipt_(fabric, receiptId, command, 'FAILED', startedAt,
      'EXECUTION_EXCEPTION', FED_asError_(error), false);
    FED_asFinishQueue_(queue, command.rowNumber, 'FAILED', receiptId,
      error && error.name ? error.name : 'Error');
    return {commandId: command.commandId, state: 'FAILED', receiptId: receiptId};
  }
}

function FED_asParseCommand_(row, rowNumber) {
  const payload = FED_asJson_(row[10], {});
  return {
    rowNumber: rowNumber,
    commandId: String(row[0] || ''),
    createdAt: String(row[1] || ''),
    requestedByChat: String(row[2] || ''),
    engine: String(row[3] || ''),
    missionId: String(row[4] || ''),
    leaseId: String(row[5] || ''),
    adapterId: String(row[6] || ''),
    action: String(row[7] || '').toUpperCase(),
    effectClass: String(row[8] || ''),
    targetAlias: String(row[9] || ''),
    payload: payload,
    scriptId: String(payload.script_id || ''),
    requiredProofs: FED_asJson_(row[11], []),
    idempotencyKey: String(row[12] || ''),
    priority: String(row[13] || 'P2'),
    attempts: Number(row[15] || 0)
  };
}

function FED_asAuthorize_(fabric, command, expectedEffect) {
  if (expectedEffect === 'READ') {
    return {allowed: true, authorityMode: 'AUTO_READ', consumeLease: false};
  }

  if (command.effectClass !== expectedEffect && command.effectClass !== 'LAB_WRITE') {
    return {allowed: false, reason: 'EFFECT_CLASS_MISMATCH'};
  }

  const leases = fabric.getSheetByName(FED_AS_BROKER.LEASES);
  if (!leases || !command.leaseId) {
    return {allowed: false, reason: 'MISSION_LEASE_REQUIRED'};
  }

  const rows = leases.getDataRange().getValues();
  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    if (String(row[0] || '') !== command.leaseId) continue;
    if (String(row[2] || '') !== 'ACTIVE') return {allowed: false, reason: 'LEASE_NOT_ACTIVE'};
    const expiry = new Date(row[8]);
    if (isNaN(expiry.getTime()) || expiry.getTime() < Date.now()) {
      return {allowed: false, reason: 'LEASE_EXPIRED'};
    }
    const maxCommands = Number(row[9] || 0);
    const used = Number(row[10] || 0);
    if (maxCommands > 0 && used >= maxCommands) {
      return {allowed: false, reason: 'LEASE_BUDGET_EXHAUSTED'};
    }
    const effects = String(row[4] || '').split(',').map(function (x) {return x.trim();});
    if (effects.indexOf(expectedEffect) < 0 && effects.indexOf(command.effectClass) < 0) {
      return {allowed: false, reason: 'LEASE_EFFECT_OUT_OF_SCOPE'};
    }
    const targets = String(row[5] || '').split(',').map(function (x) {return x.trim();});
    const targetAllowed = targets.some(function (pattern) {
      if (!pattern) return false;
      if (pattern === 'FEDERATION_LAB_REGISTRY/*') return true;
      return pattern === command.targetAlias;
    });
    if (!targetAllowed) return {allowed: false, reason: 'LEASE_TARGET_OUT_OF_SCOPE'};
    return {allowed: true, authorityMode: 'MISSION_LEASE', consumeLease: true};
  }
  return {allowed: false, reason: 'LEASE_NOT_FOUND'};
}

function FED_asConsumeLease_(fabric, leaseId) {
  const sheet = fabric.getSheetByName(FED_AS_BROKER.LEASES);
  const rows = sheet.getDataRange().getValues();
  for (let i = 1; i < rows.length; i++) {
    if (String(rows[i][0] || '') !== leaseId) continue;
    sheet.getRange(i + 1, 11).setValue(Number(rows[i][10] || 0) + 1);
    return;
  }
  throw new Error('Lease disappeared before consumption: ' + leaseId);
}

function FED_asExecute_(command) {
  switch (command.action) {
    case 'APPS_SCRIPT_GET_CONTENT':
      return FED_asGetContent_(command.scriptId);
    case 'APPS_SCRIPT_GET_DEPLOYMENTS':
      return FED_asGetDeployments_(command.scriptId);
    case 'APPS_SCRIPT_UPSERT_FILE':
      return FED_asUpsertFile_(command);
    case 'APPS_SCRIPT_REPLACE_CONTENT':
      return FED_asReplaceContent_(command);
    case 'APPS_SCRIPT_ROLLBACK_CONTENT':
      return FED_asRollbackContent_(command);
    case 'APPS_SCRIPT_CREATE_VERSION':
      return FED_asCreateVersion_(command);
    case 'APPS_SCRIPT_CREATE_DEPLOYMENT':
      return FED_asCreateDeployment_(command);
    case 'APPS_SCRIPT_UPDATE_DEPLOYMENT':
      return FED_asUpdateDeployment_(command);
    default:
      throw new Error('Unsupported Apps Script broker action: ' + command.action);
  }
}

function FED_asGetContent_(scriptId) {
  const content = FED_asApi_('get', '/projects/' + encodeURIComponent(scriptId) + '/content');
  const files = content.files || [];
  return {
    status: files.length ? 'DONE' : 'FAILED',
    semanticReadback: files.length ? 'APPS_SCRIPT_SOURCE_READBACK' : 'EMPTY_SOURCE',
    proof: {
      scriptId: scriptId,
      fileCount: files.length,
      projectHash: FED_asProjectHash_(files),
      files: files.map(FED_asFileSummary_)
    },
    productionEffect: false
  };
}

function FED_asGetDeployments_(scriptId) {
  const value = FED_asApi_('get', '/projects/' + encodeURIComponent(scriptId) + '/deployments?pageSize=100');
  const deployments = value.deployments || [];
  return {
    status: 'DONE',
    semanticReadback: 'APPS_SCRIPT_DEPLOYMENT_READBACK',
    proof: {scriptId: scriptId, deploymentCount: deployments.length, deployments: deployments},
    productionEffect: false
  };
}

function FED_asUpsertFile_(command) {
  const incoming = command.payload.file;
  if (!incoming || !incoming.name || typeof incoming.source !== 'string') {
    throw new Error('payload.file{name,type,source} is required');
  }
  if (!/^[A-Za-z0-9_.-]{1,120}$/.test(String(incoming.name))) {
    throw new Error('Invalid Apps Script file name');
  }

  const before = FED_asApi_('get', '/projects/' + encodeURIComponent(command.scriptId) + '/content');
  const backup = FED_asBackup_(command.scriptId, before, command.commandId, 'PRE_UPSERT');
  let files = JSON.parse(JSON.stringify(before.files || []));
  files = files.filter(function (file) {return file.name !== incoming.name;});
  files.push({name: incoming.name, type: incoming.type || 'SERVER_JS', source: incoming.source});
  const expected = FED_asProjectHash_(files);

  FED_asApi_('put', '/projects/' + encodeURIComponent(command.scriptId) + '/content', {files: files});
  const after = FED_asApi_('get', '/projects/' + encodeURIComponent(command.scriptId) + '/content');
  const actual = FED_asProjectHash_(after.files || []);
  if (actual !== expected) {
    FED_asRestoreBackup_(command.scriptId, backup.fileId);
    throw new Error('Post-update hash mismatch; automatic rollback completed');
  }

  return {
    status: 'DONE',
    semanticReadback: 'SOURCE_UPDATE_HASH_MATCHED',
    proof: {scriptId: command.scriptId, beforeHash: FED_asProjectHash_(before.files || []), afterHash: actual, backup: backup},
    productionEffect: true
  };
}

function FED_asReplaceContent_(command) {
  const files = command.payload.files;
  if (!Array.isArray(files) || files.length === 0) throw new Error('payload.files is required');
  if (!files.some(function (file) {return file.name === 'appsscript' && file.type === 'JSON';})) {
    throw new Error('Replacement content must contain appsscript JSON manifest');
  }

  const before = FED_asApi_('get', '/projects/' + encodeURIComponent(command.scriptId) + '/content');
  const backup = FED_asBackup_(command.scriptId, before, command.commandId, 'PRE_REPLACE');
  const expected = FED_asProjectHash_(files);
  FED_asApi_('put', '/projects/' + encodeURIComponent(command.scriptId) + '/content', {files: files});
  const after = FED_asApi_('get', '/projects/' + encodeURIComponent(command.scriptId) + '/content');
  const actual = FED_asProjectHash_(after.files || []);
  if (actual !== expected) {
    FED_asRestoreBackup_(command.scriptId, backup.fileId);
    throw new Error('Post-replace hash mismatch; automatic rollback completed');
  }

  return {
    status: 'DONE',
    semanticReadback: 'SOURCE_REPLACE_HASH_MATCHED',
    proof: {scriptId: command.scriptId, beforeHash: FED_asProjectHash_(before.files || []), afterHash: actual, backup: backup},
    productionEffect: true
  };
}

function FED_asRollbackContent_(command) {
  const fileId = String(command.payload.backup_file_id || '');
  if (!fileId) throw new Error('payload.backup_file_id is required');
  const result = FED_asRestoreBackup_(command.scriptId, fileId);
  return {
    status: 'DONE',
    semanticReadback: 'ROLLBACK_HASH_MATCHED',
    proof: result,
    productionEffect: true
  };
}

function FED_asCreateVersion_(command) {
  const before = FED_asApi_('get', '/projects/' + encodeURIComponent(command.scriptId) + '/content');
  const expectedHash = FED_asProjectHash_(before.files || []);
  const version = FED_asApi_('post', '/projects/' + encodeURIComponent(command.scriptId) + '/versions', {
    description: String(command.payload.description || ('Federation release ' + command.commandId))
  });
  if (!version.versionNumber) throw new Error('Version creation returned no versionNumber');
  return {
    status: 'DONE',
    semanticReadback: 'IMMUTABLE_VERSION_CREATED',
    proof: {scriptId: command.scriptId, version: version, sourceHash: expectedHash},
    productionEffect: true
  };
}

function FED_asCreateDeployment_(command) {
  const versionNumber = Number(command.payload.version_number || 0);
  if (!versionNumber) throw new Error('payload.version_number is required');
  const deployment = FED_asApi_('post', '/projects/' + encodeURIComponent(command.scriptId) + '/deployments', {
    versionNumber: versionNumber,
    manifestFileName: 'appsscript',
    description: String(command.payload.description || ('Federation deployment ' + command.commandId))
  });
  if (!deployment.deploymentId) throw new Error('Deployment creation returned no deploymentId');
  const readback = FED_asApi_('get', '/projects/' + encodeURIComponent(command.scriptId) + '/deployments/' + encodeURIComponent(deployment.deploymentId));
  const ok = String(readback.deploymentId || '') === String(deployment.deploymentId);
  return {
    status: ok ? 'DONE' : 'FAILED',
    semanticReadback: ok ? 'DEPLOYMENT_ID_EXACT' : 'DEPLOYMENT_READBACK_FAILED',
    proof: {scriptId: command.scriptId, deployment: readback},
    productionEffect: true
  };
}

function FED_asUpdateDeployment_(command) {
  const deploymentId = String(command.payload.deployment_id || '');
  const versionNumber = Number(command.payload.version_number || 0);
  if (!deploymentId || !versionNumber) throw new Error('deployment_id and version_number are required');
  FED_asApi_('put', '/projects/' + encodeURIComponent(command.scriptId) + '/deployments/' + encodeURIComponent(deploymentId), {
    deploymentConfig: {
      scriptId: command.scriptId,
      versionNumber: versionNumber,
      manifestFileName: 'appsscript',
      description: String(command.payload.description || ('Federation promotion ' + command.commandId))
    }
  });
  const readback = FED_asApi_('get', '/projects/' + encodeURIComponent(command.scriptId) + '/deployments/' + encodeURIComponent(deploymentId));
  const config = readback.deploymentConfig || {};
  const ok = String(readback.deploymentId || '') === deploymentId && Number(config.versionNumber || 0) === versionNumber;
  return {
    status: ok ? 'DONE' : 'FAILED',
    semanticReadback: ok ? 'DEPLOYMENT_VERSION_EXACT' : 'DEPLOYMENT_READBACK_FAILED',
    proof: {scriptId: command.scriptId, deployment: readback},
    productionEffect: true
  };
}

function FED_asApi_(method, path, body) {
  const options = {
    method: method,
    headers: {Authorization: 'Bearer ' + ScriptApp.getOAuthToken()},
    muteHttpExceptions: true
  };
  if (typeof body !== 'undefined') {
    options.contentType = 'application/json';
    options.payload = JSON.stringify(body);
  }
  const response = UrlFetchApp.fetch(FED_AS_BROKER.API_ROOT + path, options);
  const status = response.getResponseCode();
  const text = response.getContentText();
  const parsed = FED_asJson_(text, {raw: text});
  if (status < 200 || status >= 300) {
    throw new Error(JSON.stringify({code: 'APPS_SCRIPT_API_ERROR', httpStatus: status, path: path, response: parsed}));
  }
  return parsed;
}

function FED_asCanonicalTargetSet_() {
  const sheet = SpreadsheetApp.openById(FED_AS_BROKER.LAB_KERNEL_CONTROL_ID)
    .getSheetByName(FED_AS_BROKER.LAB_REGISTRY);
  if (!sheet) throw new Error('LAB_REGISTRY missing');
  const rows = sheet.getDataRange().getValues();
  const set = {};
  for (let i = 1; i < rows.length; i++) {
    const scriptId = String(rows[i][3] || '');
    if (scriptId) set[scriptId] = String(rows[i][0] || '');
  }
  return set;
}

function FED_asCompletedIdempotency_(queueValues) {
  const set = {};
  for (let i = 1; i < queueValues.length; i++) {
    const key = String(queueValues[i][12] || '');
    const state = String(queueValues[i][14] || '');
    if (key && (state === 'DONE' || state === 'PARTIAL')) set[key] = true;
  }
  return set;
}

function FED_asBackup_(scriptId, content, transactionId, reason) {
  const folder = FED_asBackupFolder_();
  const files = content.files || [];
  const projectHash = FED_asProjectHash_(files);
  const payload = {
    schema: 'FED_AS_CONTENT_BACKUP_V1',
    scriptId: scriptId,
    transactionId: transactionId,
    reason: reason,
    createdAt: FED_asNow_(),
    projectHash: projectHash,
    content: content
  };
  const file = folder.createFile(
    'FED_AS_BACKUP_' + scriptId + '_' + transactionId + '_' + Date.now() + '.json',
    JSON.stringify(payload, null, 2),
    MimeType.PLAIN_TEXT
  );
  const readback = JSON.parse(file.getBlob().getDataAsString('UTF-8'));
  if (readback.projectHash !== projectHash) {
    file.setTrashed(true);
    throw new Error('Apps Script backup verification failed');
  }
  return {fileId: file.getId(), projectHash: projectHash, createdAt: payload.createdAt};
}

function FED_asRestoreBackup_(scriptId, backupFileId) {
  const backup = JSON.parse(DriveApp.getFileById(backupFileId).getBlob().getDataAsString('UTF-8'));
  if (backup.schema !== 'FED_AS_CONTENT_BACKUP_V1') throw new Error('Unsupported backup schema');
  if (String(backup.scriptId) !== String(scriptId)) throw new Error('Backup belongs to a different script');
  FED_asApi_('put', '/projects/' + encodeURIComponent(scriptId) + '/content', backup.content);
  const readback = FED_asApi_('get', '/projects/' + encodeURIComponent(scriptId) + '/content');
  const restoredHash = FED_asProjectHash_(readback.files || []);
  if (restoredHash !== backup.projectHash) throw new Error('Rollback hash mismatch');
  return {status: 'RESTORED', scriptId: scriptId, backupFileId: backupFileId, restoredHash: restoredHash};
}

function FED_asBackupFolder_() {
  const props = PropertiesService.getScriptProperties();
  const stored = props.getProperty('FED_AS_BROKER_BACKUP_FOLDER_ID');
  if (stored) {
    try { return DriveApp.getFolderById(stored); } catch (_) {}
  }
  const iterator = DriveApp.getFoldersByName(FED_AS_BROKER.BACKUP_FOLDER);
  const folder = iterator.hasNext() ? iterator.next() : DriveApp.createFolder(FED_AS_BROKER.BACKUP_FOLDER);
  props.setProperty('FED_AS_BROKER_BACKUP_FOLDER_ID', folder.getId());
  return folder;
}

function FED_asReceipt_(fabric, receiptId, command, state, startedAt, semanticReadback, proof, productionEffect) {
  const sheet = fabric.getSheetByName(FED_AS_BROKER.RECEIPTS);
  if (!sheet) throw new Error('COMMAND_RECEIPTS missing');
  const proofText = JSON.stringify(proof || {});
  sheet.appendRow([
    receiptId,
    command.commandId,
    state,
    'OWNER_OAUTH_APPS_SCRIPT_BROKER',
    '',
    command.targetAlias,
    command.action,
    command.effectClass,
    startedAt,
    FED_asNow_(),
    state,
    semanticReadback,
    '',
    '',
    proof && proof.backup ? proof.backup.fileId || '' : '',
    proofText.substring(0, 45000),
    FED_asSha256_(proofText),
    '',
    productionEffect,
    'Apps Script claims are limited to owner-OAuth provider readback recorded in this receipt.'
  ]);
}

function FED_asFinishQueue_(queue, rowNumber, state, receiptId, errorCode) {
  queue.getRange(rowNumber, 15, 1, 4).setValues([[state, queue.getRange(rowNumber, 16).getValue(), '', '']]);
  queue.getRange(rowNumber, 20, 1, 3).setValues([[FED_asNow_(), receiptId, errorCode || '']]);
  SpreadsheetApp.flush();
}

function FED_asHeartbeat_(fabric, processed, started) {
  const sheet = fabric.getSheetByName(FED_AS_BROKER.HEARTBEAT);
  if (!sheet) return;
  sheet.appendRow([
    'HB-AS-' + Utilities.getUuid(),
    FED_asNow_(),
    'federation-owner-oauth-apps-script-broker',
    FED_AS_BROKER.VERSION,
    Session.getEffectiveUser().getEmail() || 'OWNER_OAUTH',
    '',
    processed.length,
    '',
    '',
    processed.length ? processed[processed.length - 1].receiptId || '' : '',
    'HEALTHY',
    JSON.stringify({processed: processed, elapsedMs: Date.now() - started}).substring(0, 45000)
  ]);
}

function FED_asWriteBrokerState_(fabric, key, state, proof) {
  const sheet = fabric.getSheetByName(FED_AS_BROKER.BROKER_STATE);
  if (!sheet) return;
  sheet.appendRow([key, FED_AS_BROKER.VERSION, state, JSON.stringify(proof || {}).substring(0, 45000), FED_asNow_(), '']);
}

function FED_asEnsureTrigger_() {
  const exists = ScriptApp.getProjectTriggers().some(function (trigger) {
    return trigger.getHandlerFunction() === FED_AS_BROKER.HANDLER;
  });
  if (!exists) {
    ScriptApp.newTrigger(FED_AS_BROKER.HANDLER).timeBased().everyMinutes(1).create();
  }
  return true;
}

function FED_asProjectHash_(files) {
  const normalized = (files || []).slice().sort(function (a, b) {
    return String(a.name).localeCompare(String(b.name));
  }).map(function (file) {
    return {name: file.name, type: file.type, source: file.source || ''};
  });
  return FED_asSha256_(JSON.stringify(normalized));
}

function FED_asFileSummary_(file) {
  return {
    name: file.name,
    type: file.type,
    characters: String(file.source || '').length,
    hash: FED_asSha256_(file.source || '')
  };
}

function FED_asSha256_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(text || ''), Utilities.Charset.UTF_8)
    .map(function (byte) {
      const value = byte < 0 ? byte + 256 : byte;
      return value.toString(16).padStart(2, '0');
    }).join('');
}

function FED_asJson_(value, fallback) {
  if (value === null || typeof value === 'undefined' || value === '') return fallback;
  if (typeof value === 'object') return value;
  try { return JSON.parse(String(value)); } catch (_) { return fallback; }
}

function FED_asNow_() {
  return Utilities.formatDate(new Date(), FED_AS_BROKER.LOGICAL_TZ, "yyyy-MM-dd'T'HH:mm:ssXXX");
}

function FED_asError_(error) {
  return {
    name: error && error.name ? error.name : 'Error',
    message: error && error.message ? error.message : String(error),
    stack: error && error.stack ? String(error.stack).substring(0, 4000) : ''
  };
}
