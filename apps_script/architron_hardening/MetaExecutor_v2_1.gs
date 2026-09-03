/************************************************************
 * ARCHITRON MetaExecutor v2.1 — KIOAS A0/A1 Hardened Compatibility Core
 *
 * One-time install file for Apps Script.
 *
 * What this adds over v1:
 * - Sheet-based capability registry
 * - Policy/risk tiers
 * - Dry-run mode
 * - Pre-execution validation
 * - Project snapshot before file updates
 * - Rollback from snapshot
 * - Dependency checks
 * - Function discovery
 * - Failure logging
 * - Self-test suite
 * - Future module expansion through Sheets, not hardcoded edits only
 *
 * Queue Spreadsheet:
 * https://docs.google.com/spreadsheets/d/1LSVjK9YK6u2CMrvetOcXpun4VQnOh5cE6b3w6z_KTHg/edit
 ************************************************************/

const META_V2 = {
  version: '2.1.0-kioas-hardening',
  queueSpreadsheetId: '1LSVjK9YK6u2CMrvetOcXpun4VQnOh5cE6b3w6z_KTHg',
  notifyEmail: 'mosianekk@gmail.com',

  sheets: {
    commands: 'Commands',
    files: 'Files',
    logs: 'Logs',
    config: 'Config',
    capabilities: 'Capabilities',
    snapshots: 'Snapshots',
    failures: 'Failures',
    policy: 'Policy',
    heartbeat: 'Heartbeat'
  },

  triggerHandler: 'processMetaExecutorQueueV2',

  legacyApprovalKeyName: 'META_EXECUTOR_APPROVAL_KEY',
  authorityMode: 'A0_A1_ONLY',

  risk: {
    LOW: 'LOW',
    MEDIUM: 'MEDIUM',
    HIGH: 'HIGH',
    CRITICAL: 'CRITICAL'
  },

  defaultAllowedFunctions: [
    'verifyArchitronConnectorOnly',
    'checkArchitronCloudStatus',
    'testFindSourceZip',
    'getLastArchitronCloudConnectorState'
  ],

  defaultAllowedFiles: [
    'CloudConnector.gs',
    'StatusExecutor.gs',
    'SourceRepair.gs',
    'Code.gs',
    'MetaExecutor.gs',
    'appsscript.json'
  ]
};

/************************************************************
 * INSTALL / RUNNERS
 ************************************************************/

function installMetaExecutorV2() {
  ensureMetaV2Sheets_();
  seedMetaV2Defaults_();
  // KIOAS hardening: this legacy compatibility core must not own recurrence.
  // GNS3 is the sole Federation scheduler; remove legacy MetaExecutor triggers and do not recreate them.
  deleteMetaV2Triggers_();
  logMetaV2_('INFO', 'INSTALL', 'MetaExecutor v2.1 hardened compatibility core installed without recurring trigger or email.', '');
  writeHeartbeat_('INSTALLED_NO_RECURRING_TRIGGER');
  return selfTestMetaExecutorV2();
}

function runMetaExecutorV2Now() {
  ensureMetaV2Sheets_();
  seedMetaV2Defaults_();
  return processMetaExecutorQueueV2();
}

function processMetaExecutorQueueV2() {
  ensureMetaV2Sheets_();
  seedMetaV2Defaults_();
  writeHeartbeat_('RUNNING');

  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = ss.getSheetByName(META_V2.sheets.commands);
  const values = sheet.getDataRange().getValues();

  if (values.length < 2) {
    writeHeartbeat_('NO_COMMANDS');
    return { status: 'NO_COMMANDS', checkedAt: new Date().toISOString() };
  }

  const headers = values[0].map(v => String(v || '').trim());
  const idx = headerIndex_(headers, commandHeaders_());
  const processed = [];

  for (let r = 1; r < values.length; r++) {
    const row = values[r];
    const status = String(row[idx.status] || '').trim().toUpperCase();
    if (status && status !== 'PENDING') continue;

    const command = readCommandRow_(row, idx);

    try {
      sheet.getRange(r + 1, idx.id + 1).setValue(command.id);
      sheet.getRange(r + 1, idx.status + 1).setValue('RUNNING');

      const validation = validateCommand_(command);
      if (!validation.ok) throw new Error(validation.error);

      let result;
      if (command.dryRun) {
        result = {
          status: 'DRY_RUN_OK',
          command: sanitizeCommandForResult_(command),
          validation: validation,
          checkedAt: new Date().toISOString()
        };
      } else {
        result = executeCommand_(command);
      }

      sheet.getRange(r + 1, idx.status + 1).setValue('DONE');
      sheet.getRange(r + 1, idx.resultJson + 1).setValue(JSON.stringify(result, null, 2));
      sheet.getRange(r + 1, idx.processedAt + 1).setValue(new Date().toISOString());
      sheet.getRange(r + 1, idx.error + 1).setValue('');

      logMetaV2_('INFO', command.action, JSON.stringify(result), command.id);
      processed.push({ id: command.id, action: command.action, status: 'DONE' });
    } catch (error) {
      const msg = String(error && error.message ? error.message : error);
      sheet.getRange(r + 1, idx.status + 1).setValue('ERROR');
      sheet.getRange(r + 1, idx.processedAt + 1).setValue(new Date().toISOString());
      sheet.getRange(r + 1, idx.error + 1).setValue(msg);

      logMetaV2_('ERROR', command.action || 'UNKNOWN', msg, command.id);
      logFailure_(command, msg);
      processed.push({ id: command.id, action: command.action, status: 'ERROR', error: msg });
    }
  }

  writeHeartbeat_('QUEUE_PROCESSED');
  return { status: 'QUEUE_PROCESSED', processed: processed, checkedAt: new Date().toISOString() };
}

/************************************************************
 * COMMAND EXECUTION ROUTER
 ************************************************************/

function executeCommand_(command) {
  switch (command.action) {
    case 'PING':
      return { status: 'PONG', version: META_V2.version, checkedAt: new Date().toISOString() };

    case 'SELF_TEST':
      return selfTestMetaExecutorV2();

    case 'RUN_FUNCTION':
      return runAllowedFunctionV2_(command.functionName, command.payload);

    case 'GET_PROJECT_CONTENT':
      return getAppsScriptProjectContentV2_(command.scriptId);

    case 'SNAPSHOT_PROJECT':
      return snapshotProjectV2_(command.scriptId, command.id, command.payload.reason || 'Manual snapshot');

    case 'UPSERT_SCRIPT_FILE':
    case 'INSTALL_MODULE':
      return upsertAppsScriptFileV2_(command.scriptId, command.payload.fileName, command.payload.source, command.payload.type || 'SERVER_JS', command.id);

    case 'ROLLBACK_PROJECT':
      return rollbackProjectV2_(command.scriptId, command.payload.snapshotId);

    case 'DISCOVER_FUNCTIONS':
      return discoverFunctionsV2_(command.scriptId);

    case 'CHECK_DEPENDENCIES':
      return checkDependenciesV2_(command.scriptId, command.payload);

    case 'VERIFY_HEALTH':
      return verifyHealthV2_();

    case 'WRITE_LEDGER':
      return writeLedgerV2_(command.payload);

    case 'SEND_STATUS_EMAIL':
      return sendStatusEmailV2_(command.payload);

    default:
      throw new Error('Unsupported action: ' + command.action);
  }
}

function runAllowedFunctionV2_(functionName, payload) {
  if (!functionName) throw new Error('Missing functionName.');

  const capability = getCapabilityByName_(functionName);
  const allowedByRegistry = capability && capability.enabled === true && capability.type === 'FUNCTION';
  const allowedByDefault = META_V2.defaultAllowedFunctions.includes(functionName);

  if (!allowedByRegistry && !allowedByDefault) {
    throw new Error('Function not allowed by registry/default allowlist: ' + functionName);
  }

  const fn = globalThis[functionName];
  if (typeof fn !== 'function') {
    throw new Error('Function not found in this Apps Script project: ' + functionName);
  }

  return fn(payload || {});
}

/************************************************************
 * VALIDATION / POLICY
 ************************************************************/

function validateCommand_(command) {
  if (!command.action) return { ok: false, error: 'Missing action.' };
  if (!command.scriptId) command.scriptId = ScriptApp.getScriptId();

  const policy = getPolicyForAction_(command.action);
  if (!policy.enabled) return { ok: false, error: 'Action disabled by policy: ' + command.action };

  if (command.action === 'RUN_FUNCTION' && !command.functionName) {
    return { ok: false, error: 'RUN_FUNCTION requires functionName.' };
  }

  const effective = getEffectiveAuthorityV21_(command, policy);
  if (effective.held) {
    return {
      ok: false,
      error: 'HELD_AUTHORITY_ACTION_SPECIFIC_EXECUTOR_REQUIRED:' + effective.reason,
      policy: policy,
      effectiveAuthority: effective
    };
  }

  if (command.approvalKey) {
    return { ok: false, error: 'LEGACY_REUSABLE_APPROVAL_MARKER_REJECTED' };
  }

  if ((command.action === 'UPSERT_SCRIPT_FILE' || command.action === 'INSTALL_MODULE') && !command.payload.fileName) {
    return { ok: false, error: command.action + ' requires payload.fileName.' };
  }
  if ((command.action === 'UPSERT_SCRIPT_FILE' || command.action === 'INSTALL_MODULE') && !command.payload.source) {
    return { ok: false, error: command.action + ' requires payload.source.' };
  }
  if (command.action === 'ROLLBACK_PROJECT' && !command.payload.snapshotId) {
    return { ok: false, error: 'ROLLBACK_PROJECT requires payload.snapshotId.' };
  }

  return { ok: true, policy: policy, effectiveAuthority: effective };
}

function riskRankV21_(risk) {
  const order = { LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 };
  return order[String(risk || '').toUpperCase()] || 4;
}

function maxRiskV21_(a, b) {
  return riskRankV21_(a) >= riskRankV21_(b) ? String(a || 'CRITICAL').toUpperCase() : String(b || 'CRITICAL').toUpperCase();
}

function intrinsicFunctionRiskV21_(functionName) {
  const capability = getCapabilityByName_(functionName);
  let risk = capability && capability.risk ? String(capability.risk).toUpperCase() : META_V2.risk.CRITICAL;
  const effectText = [
    String(functionName || ''),
    capability ? String(capability.notes || '') : '',
    capability ? JSON.stringify(capability.dependencies || []) : ''
  ].join(' ').toLowerCase();

  // Defense in depth for historically under-classified effectful functions.
  const explicitHigh = [
    'forceDeployNow','checkAndDeployIfChanged','repairSourceZipAndForceDeploy','bootstrapAll',
    'installFederationConnectorKernelV5','installArchitronCloudConnectorHourly','processMetaExecutorQueueV2',
    'processFederationBridgeQueueV1','runArchitronCloudConnector','runFederationConnectorKernelV5',
    'listFederationSourcesV5','registerFederationSourceV5'
  ];
  if (explicitHigh.indexOf(String(functionName || '')) >= 0) risk = maxRiskV21_(risk, META_V2.risk.HIGH);
  if (/(deploy|rollback|grant|iam|traffic|permission|credential|secret|send email|source update|install.*trigger|creates.*trigger|starts.*build|creates.*job)/i.test(effectText)) {
    risk = maxRiskV21_(risk, META_V2.risk.HIGH);
  }
  return { capability: capability, risk: risk };
}

function getEffectiveAuthorityV21_(command, policy) {
  const directHeldActions = ['SEND_STATUS_EMAIL','SNAPSHOT_PROJECT','UPSERT_SCRIPT_FILE','INSTALL_MODULE','ROLLBACK_PROJECT'];
  let effectiveRisk = String(policy.risk || META_V2.risk.CRITICAL).toUpperCase();
  let reason = '';

  if (command.action === 'RUN_FUNCTION') {
    const intrinsic = intrinsicFunctionRiskV21_(command.functionName);
    effectiveRisk = maxRiskV21_(effectiveRisk, intrinsic.risk);
    if (!intrinsic.capability || intrinsic.capability.enabled !== true || intrinsic.capability.type !== 'FUNCTION') {
      // Only the reduced safe default list may bypass a missing registry row.
      if (META_V2.defaultAllowedFunctions.indexOf(command.functionName) < 0) {
        return { held: true, risk: META_V2.risk.CRITICAL, reason: 'FUNCTION_NOT_REGISTERED_OR_ENABLED', functionName: command.functionName };
      }
    }
    if (riskRankV21_(effectiveRisk) >= riskRankV21_(META_V2.risk.HIGH)) {
      reason = 'FUNCTION_EFFECT_CLASS_' + effectiveRisk + ':' + command.functionName;
      return { held: true, risk: effectiveRisk, reason: reason, functionName: command.functionName };
    }
  }

  if (directHeldActions.indexOf(command.action) >= 0 || riskRankV21_(effectiveRisk) >= riskRankV21_(META_V2.risk.HIGH)) {
    return { held: true, risk: effectiveRisk, reason: 'DIRECT_ACTION_EFFECT_CLASS_' + effectiveRisk + ':' + command.action };
  }

  return { held: false, risk: effectiveRisk, reason: 'A0_A1_ALLOWED' };
}

function getPolicyForAction_(action) {
  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = ss.getSheetByName(META_V2.sheets.policy);
  const values = sheet.getDataRange().getValues();
  const headers = values[0].map(v => String(v || '').trim());
  const idx = headerIndex_(headers, policyHeaders_());

  for (let r = 1; r < values.length; r++) {
    if (String(values[r][idx.action]).trim() === action) {
      return {
        action: action,
        enabled: String(values[r][idx.enabled]).toUpperCase() === 'TRUE',
        risk: String(values[r][idx.risk] || META_V2.risk.MEDIUM).trim(),
        requiresApproval: String(values[r][idx.requiresApproval]).toUpperCase() === 'TRUE',
        notes: String(values[r][idx.notes] || '')
      };
    }
  }

  return { action: action, enabled: false, risk: META_V2.risk.CRITICAL, requiresApproval: true, notes: 'Default deny' };
}

function getApprovalKey_() {
  // Deprecated. Reusable approval markers do not grant authority in v2.1.
  return '';
}

function isFileAllowed_(fileName) {
  if (META_V2.defaultAllowedFiles.includes(fileName)) return true;

  const capability = getCapabilityByName_(fileName);
  return Boolean(capability && capability.enabled === true && capability.type === 'FILE');
}

function getCapabilityByName_(name) {
  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = ss.getSheetByName(META_V2.sheets.capabilities);
  const values = sheet.getDataRange().getValues();
  const headers = values[0].map(v => String(v || '').trim());
  const idx = headerIndex_(headers, capabilityHeaders_());

  for (let r = 1; r < values.length; r++) {
    if (String(values[r][idx.name]).trim() === name) {
      return {
        name: name,
        type: String(values[r][idx.type] || '').trim(),
        enabled: String(values[r][idx.enabled]).toUpperCase() === 'TRUE',
        risk: String(values[r][idx.risk] || '').trim(),
        dependencies: safeJsonParseWithDefault_(String(values[r][idx.dependencies] || '[]'), []),
        notes: String(values[r][idx.notes] || '')
      };
    }
  }
  return null;
}

/************************************************************
 * APPS SCRIPT API OPERATIONS
 ************************************************************/

function getAppsScriptProjectContentV2_(scriptId) {
  const url = 'https://script.googleapis.com/v1/projects/' + encodeURIComponent(scriptId) + '/content';
  const res = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() }
  });

  const code = res.getResponseCode();
  const text = res.getContentText();
  if (code < 200 || code >= 300) {
    throw new Error('Apps Script content fetch failed. HTTP ' + code + ': ' + text);
  }
  return JSON.parse(text);
}

function putAppsScriptProjectContentV2_(scriptId, files) {
  const url = 'https://script.googleapis.com/v1/projects/' + encodeURIComponent(scriptId) + '/content';
  const res = UrlFetchApp.fetch(url, {
    method: 'put',
    contentType: 'application/json',
    payload: JSON.stringify({ files: files }),
    muteHttpExceptions: true,
    headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() }
  });

  const code = res.getResponseCode();
  const text = res.getContentText();
  if (code < 200 || code >= 300) {
    throw new Error('Apps Script content update failed. HTTP ' + code + ': ' + text);
  }
  return JSON.parse(text || '{}');
}

function upsertAppsScriptFileV2_(scriptId, fileName, source, type, commandId) {
  if (!source || typeof source !== 'string') throw new Error('Missing source string for file: ' + fileName);

  const snapshot = snapshotProjectV2_(scriptId, commandId, 'Automatic pre-upsert snapshot for ' + fileName);
  const current = getAppsScriptProjectContentV2_(scriptId);
  const files = current.files || [];
  const normalizedName = normalizeAppsScriptFileName_(fileName);
  const normalizedType = fileName === 'appsscript.json' ? 'JSON' : (type || 'SERVER_JS');

  let replaced = false;
  const nextFiles = files.map(file => {
    if (file.name === normalizedName) {
      replaced = true;
      return { name: normalizedName, type: normalizedType, source: source };
    }
    return file;
  });

  if (!replaced) nextFiles.push({ name: normalizedName, type: normalizedType, source: source });

  putAppsScriptProjectContentV2_(scriptId, nextFiles);
  updateFilesLedgerV2_(fileName, normalizedType, source, 'APPLIED', 'Snapshot: ' + snapshot.snapshotId);

  return {
    status: 'FILE_UPSERTED',
    fileName: fileName,
    appsScriptFileName: normalizedName,
    type: normalizedType,
    scriptId: scriptId,
    snapshotId: snapshot.snapshotId,
    updatedAt: new Date().toISOString()
  };
}

function snapshotProjectV2_(scriptId, commandId, reason) {
  const content = getAppsScriptProjectContentV2_(scriptId);
  const snapshotId = 'SNAP-' + new Date().toISOString() + '-' + Utilities.getUuid();
  const source = JSON.stringify(content, null, 2);
  const hash = md5HexV2_(source);

  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = ss.getSheetByName(META_V2.sheets.snapshots);
  ensureHeader_(sheet, snapshotHeaders_());
  sheet.appendRow([
    snapshotId,
    new Date().toISOString(),
    scriptId,
    commandId || '',
    reason || '',
    hash,
    source.slice(0, 45000),
    source.length > 45000 ? 'TRUNCATED_IN_SHEET_CELL' : 'FULL_IN_CELL'
  ]);

  return { status: 'SNAPSHOT_CREATED', snapshotId: snapshotId, hash: hash, scriptId: scriptId };
}

function rollbackProjectV2_(scriptId, snapshotId) {
  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = ss.getSheetByName(META_V2.sheets.snapshots);
  const values = sheet.getDataRange().getValues();
  const headers = values[0].map(v => String(v || '').trim());
  const idx = headerIndex_(headers, snapshotHeaders_());

  for (let r = values.length - 1; r >= 1; r--) {
    if (String(values[r][idx.snapshotId]).trim() === snapshotId) {
      const storedScriptId = String(values[r][idx.scriptId]).trim();
      if (storedScriptId !== scriptId) throw new Error('Snapshot scriptId mismatch.');

      const raw = String(values[r][idx.contentJson] || '');
      if (!raw || String(values[r][idx.notes]).includes('TRUNCATED')) {
        throw new Error('Snapshot content unavailable or truncated. Cannot rollback from this Sheet snapshot. Use exported backup if available.');
      }

      const content = JSON.parse(raw);
      putAppsScriptProjectContentV2_(scriptId, content.files || []);
      return { status: 'ROLLBACK_DONE', snapshotId: snapshotId, scriptId: scriptId, rolledBackAt: new Date().toISOString() };
    }
  }

  throw new Error('Snapshot not found: ' + snapshotId);
}

/************************************************************
 * DISCOVERY / HEALTH / DEPENDENCIES
 ************************************************************/

function discoverFunctionsV2_(scriptId) {
  const content = getAppsScriptProjectContentV2_(scriptId);
  const files = content.files || [];
  const functions = [];
  const regex = /function\s+([A-Za-z_$][\w$]*)\s*\(/g;

  files.forEach(file => {
    if (file.type !== 'SERVER_JS' || !file.source) return;
    let match;
    while ((match = regex.exec(file.source)) !== null) {
      functions.push({ functionName: match[1], file: file.name });
    }
  });

  return { status: 'FUNCTIONS_DISCOVERED', count: functions.length, functions: functions };
}

function checkDependenciesV2_(scriptId, payload) {
  const content = getAppsScriptProjectContentV2_(scriptId);
  const files = (content.files || []).map(f => f.name);
  const requiredFiles = payload.requiredFiles || [];
  const requiredFunctions = payload.requiredFunctions || [];
  const discovered = discoverFunctionsV2_(scriptId).functions.map(f => f.functionName);

  const missingFiles = requiredFiles.filter(name => !files.includes(normalizeAppsScriptFileName_(name)));
  const missingFunctions = requiredFunctions.filter(name => !discovered.includes(name));

  return {
    status: missingFiles.length || missingFunctions.length ? 'DEPENDENCIES_MISSING' : 'DEPENDENCIES_OK',
    missingFiles: missingFiles,
    missingFunctions: missingFunctions,
    checkedAt: new Date().toISOString()
  };
}

function verifyHealthV2_() {
  const health = {
    version: META_V2.version,
    queueSpreadsheetId: META_V2.queueSpreadsheetId,
    scriptId: ScriptApp.getScriptId(),
    sheetsOk: true,
    triggers: ScriptApp.getProjectTriggers().map(t => t.getHandlerFunction()),
    checkedAt: new Date().toISOString()
  };

  writeHeartbeat_('HEALTH_OK');
  return { status: 'HEALTH_OK', health: health };
}

function selfTestMetaExecutorV2() {
  ensureMetaV2Sheets_();
  seedMetaV2Defaults_();

  const result = {
    status: 'SELF_TEST_OK',
    version: META_V2.version,
    scriptId: ScriptApp.getScriptId(),
    spreadsheetId: META_V2.queueSpreadsheetId,
    requiredSheets: Object.values(META_V2.sheets),
    authorityMode: META_V2.authorityMode,
    recurringTriggerOwned: false,
    reusableApprovalMarkerAuthoritative: false,
    highRiskFunctionHeld: getEffectiveAuthorityV21_({action:'RUN_FUNCTION',functionName:'forceDeployNow'}, {risk:META_V2.risk.MEDIUM}).held === true,
    checkedAt: new Date().toISOString()
  };

  logMetaV2_('INFO', 'SELF_TEST', JSON.stringify(result), '');
  writeHeartbeat_('SELF_TEST_OK');
  return result;
}

/************************************************************
 * LEDGER / EMAIL HELPERS
 ************************************************************/

function writeLedgerV2_(payload) {
  const sheetName = payload.sheetName || META_V2.sheets.logs;
  const row = payload.row || [new Date().toISOString(), 'INFO', 'WRITE_LEDGER', JSON.stringify(payload), ''];
  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = getOrCreateSheet_(ss, sheetName);
  sheet.appendRow(row);
  return { status: 'LEDGER_WRITTEN', sheetName: sheetName, writtenAt: new Date().toISOString() };
}

function sendStatusEmailV2_(payload) {
  throw new Error('HELD_AUTHORITY_OUTBOUND_EMAIL_REQUIRES_EXPLICIT_ROUTE');
}

function logMetaV2_(level, event, details, commandId) {
  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = getOrCreateSheet_(ss, META_V2.sheets.logs);
  ensureHeader_(sheet, logHeaders_());
  sheet.appendRow([new Date().toISOString(), level, event, details, commandId || '']);
}

function logFailure_(command, error) {
  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = getOrCreateSheet_(ss, META_V2.sheets.failures);
  ensureHeader_(sheet, failureHeaders_());
  sheet.appendRow([
    new Date().toISOString(),
    command.id || '',
    command.action || '',
    command.functionName || '',
    error,
    JSON.stringify(sanitizeCommandForResult_(command))
  ]);
}

function writeHeartbeat_(status) {
  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = getOrCreateSheet_(ss, META_V2.sheets.heartbeat);
  ensureHeader_(sheet, heartbeatHeaders_());
  sheet.appendRow([new Date().toISOString(), META_V2.version, status, ScriptApp.getScriptId()]);
}

function updateFilesLedgerV2_(fileName, type, source, status, notes) {
  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = getOrCreateSheet_(ss, META_V2.sheets.files);
  ensureHeader_(sheet, fileHeaders_());

  const hash = md5HexV2_(source);
  const lastRow = sheet.getLastRow();
  if (lastRow >= 2) {
    const values = sheet.getRange(2, 1, lastRow - 1, 7).getValues();
    for (let i = 0; i < values.length; i++) {
      if (String(values[i][0]).trim() === fileName) {
        sheet.getRange(i + 2, 1, 1, 7).setValues([[fileName, type, source.slice(0, 45000), status, new Date().toISOString(), hash, notes || '']]);
        return;
      }
    }
  }
  sheet.appendRow([fileName, type, source.slice(0, 45000), status, new Date().toISOString(), hash, notes || '']);
}

/************************************************************
 * SHEET SETUP / DEFAULTS
 ************************************************************/

function ensureMetaV2Sheets_() {
  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  ensureHeader_(getOrCreateSheet_(ss, META_V2.sheets.commands), commandHeaders_());
  ensureHeader_(getOrCreateSheet_(ss, META_V2.sheets.files), fileHeaders_());
  ensureHeader_(getOrCreateSheet_(ss, META_V2.sheets.logs), logHeaders_());
  ensureHeader_(getOrCreateSheet_(ss, META_V2.sheets.config), configHeaders_());
  ensureHeader_(getOrCreateSheet_(ss, META_V2.sheets.capabilities), capabilityHeaders_());
  ensureHeader_(getOrCreateSheet_(ss, META_V2.sheets.snapshots), snapshotHeaders_());
  ensureHeader_(getOrCreateSheet_(ss, META_V2.sheets.failures), failureHeaders_());
  ensureHeader_(getOrCreateSheet_(ss, META_V2.sheets.policy), policyHeaders_());
  ensureHeader_(getOrCreateSheet_(ss, META_V2.sheets.heartbeat), heartbeatHeaders_());
}

function seedMetaV2Defaults_() {
  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const config = ss.getSheetByName(META_V2.sheets.config);
  const policy = ss.getSheetByName(META_V2.sheets.policy);
  const capabilities = ss.getSheetByName(META_V2.sheets.capabilities);

  upsertConfigRow_(config, 'QUEUE_SPREADSHEET_ID', META_V2.queueSpreadsheetId, 'ChatGPT-writable command queue');
  upsertConfigRow_(config, 'META_EXECUTOR_VERSION', META_V2.version, 'Current MetaExecutor version');
  upsertConfigRow_(config, 'META_EXECUTOR_AUTHORITY_MODE', META_V2.authorityMode, 'KIOAS hardened compatibility core; no reusable approval marker grants high-impact authority.');

  const policies = [
    ['PING', true, META_V2.risk.LOW, false, 'Connectivity test'],
    ['SELF_TEST', true, META_V2.risk.LOW, false, 'Internal self-test'],
    ['VERIFY_HEALTH', true, META_V2.risk.LOW, false, 'Health status'],
    ['DISCOVER_FUNCTIONS', true, META_V2.risk.LOW, false, 'Read-only discovery'],
    ['CHECK_DEPENDENCIES', true, META_V2.risk.LOW, false, 'Read-only dependency check'],
    ['GET_PROJECT_CONTENT', true, META_V2.risk.MEDIUM, false, 'Read-only project-source inspection; semantic source proof still required.'],
    ['RUN_FUNCTION', true, META_V2.risk.MEDIUM, false, 'Effective risk inherits target function intrinsic class; HIGH/CRITICAL functions are held.'],
    ['WRITE_LEDGER', true, META_V2.risk.LOW, false, 'Writes bounded internal ledger row'],
    ['SEND_STATUS_EMAIL', false, META_V2.risk.HIGH, false, 'Disabled: outbound communication requires a separate explicit route.'],
    ['SNAPSHOT_PROJECT', false, META_V2.risk.HIGH, false, 'Disabled in legacy queue: use external restore-grade backup lane.'],
    ['UPSERT_SCRIPT_FILE', false, META_V2.risk.HIGH, false, 'Disabled: source mutation requires an action-specific source executor.'],
    ['INSTALL_MODULE', false, META_V2.risk.HIGH, false, 'Disabled: source mutation requires an action-specific source executor.'],
    ['ROLLBACK_PROJECT', false, META_V2.risk.CRITICAL, false, 'Disabled: rollback requires exact external checkpoint and action-specific authority.']
  ];
  policies.forEach(p => upsertPolicyRow_(policy, p[0], p[1], p[2], p[3], p[4]));

  META_V2.defaultAllowedFunctions.forEach(name => upsertCapabilityRow_(capabilities, name, 'FUNCTION', true, META_V2.risk.LOW, '[]', 'KIOAS v2.1 safe default function'));
  META_V2.defaultAllowedFiles.forEach(name => upsertCapabilityRow_(capabilities, name, 'FILE', true, META_V2.risk.HIGH, '[]', 'Default file'));
}

/************************************************************
 * COMMAND CREATION HELPERS
 ************************************************************/

function createMetaV2PingCommand() {
  return appendCommandV2_({ action: 'PING', payload: {} });
}

function createMetaV2SelfTestCommand() {
  return appendCommandV2_({ action: 'SELF_TEST', payload: {} });
}

function createMetaV2VerifyArchitronCommand() {
  return appendCommandV2_({ action: 'RUN_FUNCTION', functionName: 'verifyArchitronConnectorOnly', payload: {} });
}

function appendCommandV2_(input) {
  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = ss.getSheetByName(META_V2.sheets.commands);
  ensureHeader_(sheet, commandHeaders_());

  const id = input.id || ('CMD-' + new Date().toISOString() + '-' + Utilities.getUuid());
  sheet.appendRow([
    id,
    new Date().toISOString(),
    'PENDING',
    input.action || '',
    input.scriptId || '',
    input.functionName || '',
    JSON.stringify(input.payload || {}),
    '',
    '',
    '',
    input.dryRun ? 'TRUE' : 'FALSE',
    input.approvalKey || ''
  ]);
  return { status: 'COMMAND_CREATED', id: id };
}

/************************************************************
 * UTILITIES
 ************************************************************/

function readCommandRow_(row, idx) {
  return {
    id: String(row[idx.id] || '').trim() || Utilities.getUuid(),
    createdAt: String(row[idx.createdAt] || '').trim(),
    status: String(row[idx.status] || '').trim(),
    action: String(row[idx.action] || '').trim(),
    scriptId: String(row[idx.scriptId] || '').trim() || ScriptApp.getScriptId(),
    functionName: String(row[idx.functionName] || '').trim(),
    payload: safeJsonParseWithDefault_(String(row[idx.payloadJson] || '{}'), {}),
    dryRun: String(row[idx.dryRun] || '').trim().toUpperCase() === 'TRUE',
    approvalKey: String(row[idx.approvalKey] || '').trim()
  };
}

function sanitizeCommandForResult_(command) {
  return {
    id: command.id,
    action: command.action,
    scriptId: command.scriptId,
    functionName: command.functionName,
    payloadKeys: Object.keys(command.payload || {}),
    dryRun: command.dryRun
  };
}

function deleteMetaV2Triggers_() {
  ScriptApp.getProjectTriggers().forEach(trigger => {
    if (trigger.getHandlerFunction() === META_V2.triggerHandler || trigger.getHandlerFunction() === 'processMetaExecutorQueue') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

function getConfigValue_(key) {
  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = ss.getSheetByName(META_V2.sheets.config);
  const values = sheet.getDataRange().getValues();
  for (let r = 1; r < values.length; r++) {
    if (String(values[r][0]).trim() === key) return String(values[r][1] || '').trim();
  }
  return '';
}

function getOrCreateSheet_(ss, name) {
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function ensureHeader_(sheet, headers) {
  const width = headers.length;
  const existing = sheet.getRange(1, 1, 1, width).getValues()[0];
  const hasAny = existing.join('').trim().length > 0;
  if (!hasAny) {
    sheet.getRange(1, 1, 1, width).setValues([headers]);
    sheet.getRange(1, 1, 1, width).setFontWeight('bold');
    return;
  }
  const mismatch = headers.some((h, i) => String(existing[i] || '').trim() !== h);
  if (mismatch) {
    sheet.insertRowBefore(1);
    sheet.getRange(1, 1, 1, width).setValues([headers]);
    sheet.getRange(1, 1, 1, width).setFontWeight('bold');
  }
}

function headerIndex_(headers, required) {
  const index = {};
  headers.forEach((h, i) => index[h] = i);
  required.forEach(h => {
    if (typeof index[h] !== 'number') throw new Error('Missing required header: ' + h);
  });
  return index;
}

function upsertConfigRow_(sheet, key, value, notes) {
  const lastRow = sheet.getLastRow();
  if (lastRow >= 2) {
    const keys = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
    for (let i = 0; i < keys.length; i++) {
      if (String(keys[i][0]).trim() === key) {
        sheet.getRange(i + 2, 2, 1, 2).setValues([[value, notes]]);
        return;
      }
    }
  }
  sheet.appendRow([key, value, notes]);
}

function upsertPolicyRow_(sheet, action, enabled, risk, requiresApproval, notes) {
  const lastRow = sheet.getLastRow();
  if (lastRow >= 2) {
    const values = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
    for (let i = 0; i < values.length; i++) {
      if (String(values[i][0]).trim() === action) {
        sheet.getRange(i + 2, 1, 1, 5).setValues([[action, String(enabled).toUpperCase(), risk, String(requiresApproval).toUpperCase(), notes]]);
        return;
      }
    }
  }
  sheet.appendRow([action, String(enabled).toUpperCase(), risk, String(requiresApproval).toUpperCase(), notes]);
}

function upsertCapabilityRow_(sheet, name, type, enabled, risk, dependencies, notes) {
  const lastRow = sheet.getLastRow();
  if (lastRow >= 2) {
    const values = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
    for (let i = 0; i < values.length; i++) {
      if (String(values[i][0]).trim() === name) {
        sheet.getRange(i + 2, 1, 1, 6).setValues([[name, type, String(enabled).toUpperCase(), risk, dependencies, notes]]);
        return;
      }
    }
  }
  sheet.appendRow([name, type, String(enabled).toUpperCase(), risk, dependencies, notes]);
}

function normalizeAppsScriptFileName_(fileName) {
  return String(fileName).replace(/\.gs$/i, '').replace(/\.json$/i, '');
}

function safeJsonParseWithDefault_(raw, fallback) {
  try { return JSON.parse(raw || JSON.stringify(fallback)); }
  catch (e) { return fallback; }
}

function md5HexV2_(value) {
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, value, Utilities.Charset.UTF_8);
  return bytes.map(b => ('0' + ((b + 256) % 256).toString(16)).slice(-2)).join('');
}

/************************************************************
 * HEADERS
 ************************************************************/

function commandHeaders_() {
  return ['id', 'createdAt', 'status', 'action', 'scriptId', 'functionName', 'payloadJson', 'resultJson', 'processedAt', 'error', 'dryRun', 'approvalKey'];
}

function fileHeaders_() {
  return ['fileName', 'type', 'source', 'status', 'lastAppliedAt', 'hash', 'notes'];
}

function logHeaders_() {
  return ['loggedAt', 'level', 'event', 'details', 'commandId'];
}

function configHeaders_() {
  return ['key', 'value', 'notes'];
}

function capabilityHeaders_() {
  return ['name', 'type', 'enabled', 'risk', 'dependencies', 'notes'];
}

function snapshotHeaders_() {
  return ['snapshotId', 'createdAt', 'scriptId', 'commandId', 'reason', 'hash', 'contentJson', 'notes'];
}

function failureHeaders_() {
  return ['failedAt', 'commandId', 'action', 'functionName', 'error', 'commandJson'];
}

function policyHeaders_() {
  return ['action', 'enabled', 'risk', 'requiresApproval', 'notes'];
}

function heartbeatHeaders_() {
  return ['checkedAt', 'version', 'status', 'scriptId'];
}

/************************************************************
 * REQUIRED appsscript.json
 *
 * Replace your manifest with:
 *
 * {
 *   "timeZone": "Africa/Johannesburg",
 *   "exceptionLogging": "STACKDRIVER",
 *   "runtimeVersion": "V8",
 *   "oauthScopes": [
 *     "https://www.googleapis.com/auth/script.external_request",
 *     "https://www.googleapis.com/auth/cloud-platform",
 *     "https://www.googleapis.com/auth/spreadsheets",
 *     "https://www.googleapis.com/auth/gmail.send",
 *     "https://www.googleapis.com/auth/script.scriptapp",
 *     "https://www.googleapis.com/auth/script.projects",
 *     "https://www.googleapis.com/auth/script.projects.readonly"
 *   ]
 * }
 ************************************************************/

/************************************************************
 * ARCHITRON Federation Connector Kernel v5.0
 * Add-on upgrade for MetaExecutor v2.
 *
 * Purpose:
 * - Adds expandable source routing without breaking the current v2 core.
 * - Lets future capabilities be inserted through registry rows.
 * - Supports native Google sources now and external connectors through
 *   webhook/proxy/dropzone patterns.
 *
 * Main entrypoints to run through RUN_FUNCTION:
 * - installFederationConnectorKernelV5
 * - runFederationConnectorKernelV5
 * - listFederationSourcesV5
 * - registerFederationSourceV5
 ************************************************************/

const FED_KERNEL_V5 = {
  version: '5.0.0',
  queueSpreadsheetId: META_V2.queueSpreadsheetId,
  notifyEmail: META_V2.notifyEmail,
  approvalKeyName: 'DEPRECATED_REUSABLE_APPROVAL_MARKER',
  defaultApprovalKey: '',

  sheets: {
    sources: 'Federation_Sources',
    sourceRuns: 'Federation_Source_Runs',
    sourceResults: 'Federation_Source_Results',
    sourceFailures: 'Federation_Source_Failures',
    connectors: 'Federation_Connectors',
    webhooks: 'Federation_Webhooks',
    dropzones: 'Federation_Dropzones',
    sourceMap: 'Federation_Source_Map'
  },

  supportedSources: [
    'GOOGLE_DRIVE_SEARCH',
    'GOOGLE_DRIVE_FILE_TEXT',
    'GOOGLE_DOC_TEXT',
    'GOOGLE_SHEET_RANGE',
    'GMAIL_SEARCH',
    'GMAIL_THREAD',
    'GOOGLE_CALENDAR_SEARCH',
    'HTTP_JSON',
    'HTTP_TEXT',
    'WEBHOOK_POST',
    'CONNECTOR_PROXY',
    'DRIVE_DROPZONE'
  ]
};

function installFederationConnectorKernelV5() {
  ensureFederationKernelSheetsV5_();
  seedFederationKernelDefaultsV5_();
  registerFederationKernelWithMetaExecutorV5_();
  logFederationSourceRunV5_('INSTALL', 'OK', { version: FED_KERNEL_V5.version });

  // KIOAS hardening: no automatic outbound email from installation.

  return {
    status: 'FEDERATION_CONNECTOR_KERNEL_INSTALLED',
    version: FED_KERNEL_V5.version,
    supportedSources: FED_KERNEL_V5.supportedSources,
    checkedAt: new Date().toISOString()
  };
}

function runFederationConnectorKernelV5(payload) {
  ensureFederationKernelSheetsV5_();
  const req = normalizeFederationRequestV5_(payload || {});
  const source = getFederationSourceV5_(req.sourceName, req.sourceType);

  try {
    const result = routeFederationSourceV5_(source, req);
    const record = {
      requestId: req.requestId,
      status: 'OK',
      sourceName: source.name,
      sourceType: source.type,
      finishedAt: new Date().toISOString(),
      result: result
    };
    writeFederationSourceResultV5_(record);
    logFederationSourceRunV5_('FETCH', 'OK', record);
    return record;
  } catch (error) {
    const failure = {
      requestId: req.requestId,
      sourceName: source.name,
      sourceType: source.type,
      error: String(error && error.message ? error.message : error),
      failedAt: new Date().toISOString()
    };
    writeFederationSourceFailureV5_(failure);
    logFederationSourceRunV5_('FETCH', 'ERROR', failure);
    throw new Error(failure.error);
  }
}

function listFederationSourcesV5() {
  ensureFederationKernelSheetsV5_();
  return {
    status: 'FEDERATION_SOURCES_LISTED',
    sources: getFederationSheetObjectsV5_(FED_KERNEL_V5.sheets.sources, federationSourceHeadersV5_())
  };
}

function registerFederationSourceV5(payload) {
  ensureFederationKernelSheetsV5_();
  if (!payload || !payload.name || !payload.type) throw new Error('registerFederationSourceV5 requires name and type.');
  if (!FED_KERNEL_V5.supportedSources.includes(payload.type)) throw new Error('Unsupported source type: ' + payload.type);

  const sheet = SpreadsheetApp.openById(FED_KERNEL_V5.queueSpreadsheetId).getSheetByName(FED_KERNEL_V5.sheets.sources);
  upsertFederationRowV5_(sheet, federationSourceHeadersV5_(), payload.name, [
    payload.name,
    payload.type,
    String(payload.enabled !== false).toUpperCase(),
    payload.baseUrl || '',
    payload.authMode || 'NONE',
    JSON.stringify(payload.config || {}),
    payload.risk || 'MEDIUM',
    payload.notes || 'Registered through Federation Kernel',
    new Date().toISOString()
  ]);

  return { status: 'FEDERATION_SOURCE_REGISTERED', name: payload.name, type: payload.type };
}

function routeFederationSourceV5_(source, req) {
  if (!source.enabled) throw new Error('Source disabled: ' + source.name);

  switch (source.type) {
    case 'GOOGLE_DRIVE_SEARCH': return federationDriveSearchV5_(req);
    case 'GOOGLE_DRIVE_FILE_TEXT': return federationDriveFileTextV5_(req);
    case 'GOOGLE_DOC_TEXT': return federationDocTextV5_(req);
    case 'GOOGLE_SHEET_RANGE': return federationSheetRangeV5_(req);
    case 'GMAIL_SEARCH': return federationGmailSearchV5_(req);
    case 'GMAIL_THREAD': return federationGmailThreadV5_(req);
    case 'GOOGLE_CALENDAR_SEARCH': return federationCalendarSearchV5_(req);
    case 'HTTP_JSON': return federationHttpFetchV5_(source, req, true);
    case 'HTTP_TEXT': return federationHttpFetchV5_(source, req, false);
    case 'WEBHOOK_POST': return federationWebhookPostV5_(source, req);
    case 'CONNECTOR_PROXY': return federationConnectorProxyV5_(source, req);
    case 'DRIVE_DROPZONE': return federationDriveDropzoneV5_(req);
    default: throw new Error('Unsupported source type: ' + source.type);
  }
}

function federationDriveSearchV5_(req) {
  const query = String(req.params.query || '').replace(/'/g, "\'");
  const max = Number(req.params.max || 20);
  const files = DriveApp.searchFiles(query ? "title contains '" + query + "'" : "trashed = false");
  const out = [];
  while (files.hasNext() && out.length < max) {
    const f = files.next();
    out.push({ id: f.getId(), name: f.getName(), mimeType: f.getMimeType(), url: f.getUrl(), updated: f.getLastUpdated().toISOString() });
  }
  return { count: out.length, files: out };
}

function federationDriveFileTextV5_(req) {
  const fileId = req.params.fileId;
  if (!fileId) throw new Error('GOOGLE_DRIVE_FILE_TEXT requires params.fileId.');
  const file = DriveApp.getFileById(fileId);
  return { id: fileId, name: file.getName(), mimeType: file.getMimeType(), text: file.getBlob().getDataAsString().slice(0, 50000) };
}

function federationDocTextV5_(req) {
  const id = req.params.documentId || req.params.fileId;
  if (!id) throw new Error('GOOGLE_DOC_TEXT requires params.documentId or params.fileId.');
  const doc = DocumentApp.openById(id);
  return { id: id, name: doc.getName(), text: doc.getBody().getText() };
}

function federationSheetRangeV5_(req) {
  const spreadsheetId = req.params.spreadsheetId;
  const sheetName = req.params.sheetName;
  const range = req.params.range || 'A1:Z100';
  if (!spreadsheetId || !sheetName) throw new Error('GOOGLE_SHEET_RANGE requires params.spreadsheetId and params.sheetName.');
  const sheet = SpreadsheetApp.openById(spreadsheetId).getSheetByName(sheetName);
  return { spreadsheetId: spreadsheetId, sheetName: sheetName, range: range, values: sheet.getRange(range).getValues() };
}

function federationGmailSearchV5_(req) {
  const query = req.params.query || '';
  const max = Number(req.params.max || 20);
  const threads = GmailApp.search(query, 0, max);
  return {
    count: threads.length,
    threads: threads.map(t => {
      const messages = t.getMessages();
      const m = messages[messages.length - 1];
      return { threadId: t.getId(), subject: m.getSubject(), from: m.getFrom(), date: m.getDate().toISOString(), snippet: m.getPlainBody().slice(0, 1000) };
    })
  };
}

function federationGmailThreadV5_(req) {
  if (!req.params.threadId) throw new Error('GMAIL_THREAD requires params.threadId.');
  const thread = GmailApp.getThreadById(req.params.threadId);
  return {
    threadId: req.params.threadId,
    messages: thread.getMessages().map(m => ({ subject: m.getSubject(), from: m.getFrom(), to: m.getTo(), date: m.getDate().toISOString(), body: m.getPlainBody().slice(0, 30000) }))
  };
}

function federationCalendarSearchV5_(req) {
  const query = req.params.query || '';
  const daysBack = Number(req.params.daysBack || 30);
  const daysForward = Number(req.params.daysForward || 90);
  const max = Number(req.params.max || 50);
  const cal = CalendarApp.getDefaultCalendar();
  const start = new Date(Date.now() - daysBack * 86400000);
  const end = new Date(Date.now() + daysForward * 86400000);
  const events = query ? cal.getEvents(start, end, { search: query }) : cal.getEvents(start, end);
  return { count: events.length, events: events.slice(0, max).map(e => ({ title: e.getTitle(), start: e.getStartTime().toISOString(), end: e.getEndTime().toISOString(), location: e.getLocation(), description: e.getDescription() })) };
}

function federationHttpFetchV5_(source, req, parseJson) {
  const url = buildFederationUrlV5_(source.baseUrl || req.params.url, req.params.queryParams || {});
  if (!url) throw new Error(source.type + ' requires baseUrl or params.url.');
  const res = UrlFetchApp.fetch(url, { method: req.params.method || 'get', headers: federationAuthHeadersV5_(source, req), muteHttpExceptions: true });
  const code = res.getResponseCode();
  const text = res.getContentText();
  if (code < 200 || code >= 300) throw new Error('HTTP fetch failed. HTTP ' + code + ': ' + text.slice(0, 1000));
  return parseJson ? JSON.parse(text) : { statusCode: code, text: text.slice(0, 50000) };
}

function federationWebhookPostV5_(source, req) {
  const url = source.baseUrl || req.params.url;
  if (!url) throw new Error('WEBHOOK_POST requires baseUrl or params.url.');
  const res = UrlFetchApp.fetch(url, { method: 'post', contentType: 'application/json', payload: JSON.stringify({ request: req, source: source.name }), headers: federationAuthHeadersV5_(source, req), muteHttpExceptions: true });
  const code = res.getResponseCode();
  const text = res.getContentText();
  if (code < 200 || code >= 300) throw new Error('Webhook failed. HTTP ' + code + ': ' + text.slice(0, 1000));
  return safeJsonParseWithDefault_(text, { text: text });
}

function federationConnectorProxyV5_(source, req) {
  const url = source.baseUrl || req.params.proxyUrl;
  if (!url) throw new Error('CONNECTOR_PROXY requires baseUrl or params.proxyUrl.');
  const payload = { connector: req.params.connector, operation: req.params.operation, args: req.params.args || {}, requestId: req.requestId };
  const res = UrlFetchApp.fetch(url, { method: 'post', contentType: 'application/json', payload: JSON.stringify(payload), headers: federationAuthHeadersV5_(source, req), muteHttpExceptions: true });
  const code = res.getResponseCode();
  const text = res.getContentText();
  if (code < 200 || code >= 300) throw new Error('Connector proxy failed. HTTP ' + code + ': ' + text.slice(0, 1000));
  return safeJsonParseWithDefault_(text, { text: text });
}

function federationDriveDropzoneV5_(req) {
  const folderName = req.params.folderName || 'ARCHITRON_SOURCE_DROPZONE';
  const query = String(req.params.query || '').toLowerCase();
  const folders = DriveApp.getFoldersByName(folderName);
  if (!folders.hasNext()) throw new Error('Dropzone folder not found: ' + folderName);
  const folder = folders.next();
  const files = folder.getFiles();
  const out = [];
  while (files.hasNext() && out.length < Number(req.params.max || 50)) {
    const f = files.next();
    if (!query || f.getName().toLowerCase().includes(query)) {
      out.push({ id: f.getId(), name: f.getName(), mimeType: f.getMimeType(), url: f.getUrl(), updated: f.getLastUpdated().toISOString() });
    }
  }
  return { folderName: folderName, count: out.length, files: out };
}

function registerFederationKernelWithMetaExecutorV5_() {
  const ss = SpreadsheetApp.openById(FED_KERNEL_V5.queueSpreadsheetId);
  const capabilities = getOrCreateSheet_(ss, META_V2.sheets.capabilities);
  const names = ['installFederationConnectorKernelV5', 'runFederationConnectorKernelV5', 'listFederationSourcesV5', 'registerFederationSourceV5'];
  names.forEach(name => upsertCapabilityRow_(capabilities, name, 'FUNCTION', true, META_V2.risk.HIGH, '[]', 'KIOAS: nested connector/payload authority requires action-specific executor; generic invocation held.'));
}

function ensureFederationKernelSheetsV5_() {
  const ss = SpreadsheetApp.openById(FED_KERNEL_V5.queueSpreadsheetId);
  ensureHeader_(getOrCreateSheet_(ss, FED_KERNEL_V5.sheets.sources), federationSourceHeadersV5_());
  ensureHeader_(getOrCreateSheet_(ss, FED_KERNEL_V5.sheets.sourceRuns), federationRunHeadersV5_());
  ensureHeader_(getOrCreateSheet_(ss, FED_KERNEL_V5.sheets.sourceResults), federationResultHeadersV5_());
  ensureHeader_(getOrCreateSheet_(ss, FED_KERNEL_V5.sheets.sourceFailures), federationFailureHeadersV5_());
  ensureHeader_(getOrCreateSheet_(ss, FED_KERNEL_V5.sheets.connectors), federationConnectorHeadersV5_());
  ensureHeader_(getOrCreateSheet_(ss, FED_KERNEL_V5.sheets.webhooks), federationWebhookHeadersV5_());
  ensureHeader_(getOrCreateSheet_(ss, FED_KERNEL_V5.sheets.dropzones), federationDropzoneHeadersV5_());
  ensureHeader_(getOrCreateSheet_(ss, FED_KERNEL_V5.sheets.sourceMap), federationSourceMapHeadersV5_());
}

function seedFederationKernelDefaultsV5_() {
  const sheet = SpreadsheetApp.openById(FED_KERNEL_V5.queueSpreadsheetId).getSheetByName(FED_KERNEL_V5.sheets.sources);
  const defaults = [
    ['drive.search', 'GOOGLE_DRIVE_SEARCH', true, '', 'GOOGLE_NATIVE', {}, 'LOW', 'Search Drive files'],
    ['drive.fileText', 'GOOGLE_DRIVE_FILE_TEXT', true, '', 'GOOGLE_NATIVE', {}, 'MEDIUM', 'Read Drive text file'],
    ['docs.text', 'GOOGLE_DOC_TEXT', true, '', 'GOOGLE_NATIVE', {}, 'MEDIUM', 'Read Google Doc text'],
    ['sheets.range', 'GOOGLE_SHEET_RANGE', true, '', 'GOOGLE_NATIVE', {}, 'MEDIUM', 'Read Sheet range'],
    ['gmail.search', 'GMAIL_SEARCH', true, '', 'GOOGLE_NATIVE', {}, 'MEDIUM', 'Search Gmail'],
    ['gmail.thread', 'GMAIL_THREAD', true, '', 'GOOGLE_NATIVE', {}, 'HIGH', 'Read Gmail thread'],
    ['calendar.search', 'GOOGLE_CALENDAR_SEARCH', true, '', 'GOOGLE_NATIVE', {}, 'MEDIUM', 'Search Google Calendar'],
    ['http.json', 'HTTP_JSON', true, '', 'NONE_OR_BEARER', {}, 'MEDIUM', 'Fetch JSON'],
    ['http.text', 'HTTP_TEXT', true, '', 'NONE_OR_BEARER', {}, 'MEDIUM', 'Fetch text'],
    ['webhook.generic', 'WEBHOOK_POST', true, '', 'BEARER_OR_SECRET', {}, 'HIGH', 'Call webhook'],
    ['connector.proxy', 'CONNECTOR_PROXY', true, '', 'BEARER_OR_SECRET', {}, 'HIGH', 'Route external connector through proxy'],
    ['dropzone.drive', 'DRIVE_DROPZONE', true, '', 'GOOGLE_NATIVE', {}, 'LOW', 'Read Drive dropzone']
  ];
  defaults.forEach(r => upsertFederationRowV5_(sheet, federationSourceHeadersV5_(), r[0], [r[0], r[1], String(r[2]).toUpperCase(), r[3], r[4], JSON.stringify(r[5]), r[6], r[7], new Date().toISOString()]));
}

function normalizeFederationRequestV5_(payload) {
  return {
    requestId: payload.requestId || ('FED-' + new Date().toISOString().replace(/[:.]/g, '-') + '-' + Utilities.getUuid()),
    sourceName: payload.sourceName || '',
    sourceType: payload.sourceType || '',
    params: payload.params || {},
    approvalKey: payload.approvalKey || ''
  };
}

function getFederationSourceV5_(sourceName, sourceType) {
  const rows = getFederationSheetObjectsV5_(FED_KERNEL_V5.sheets.sources, federationSourceHeadersV5_());
  const row = rows.find(r => String(r.name).trim() === sourceName) || rows.find(r => String(r.type).trim() === sourceType);
  if (!row) throw new Error('Federation source not registered: ' + (sourceName || sourceType));
  return {
    name: String(row.name || ''),
    type: String(row.type || ''),
    enabled: String(row.enabled).toUpperCase() === 'TRUE',
    baseUrl: String(row.baseUrl || ''),
    authMode: String(row.authMode || 'NONE'),
    config: safeJsonParseWithDefault_(String(row.configJson || '{}'), {}),
    risk: String(row.risk || 'MEDIUM'),
    notes: String(row.notes || '')
  };
}

function federationAuthHeadersV5_(source, req) {
  const headers = { Accept: 'application/json,text/plain,*/*' };
  const token = req.params.bearerToken || source.config.bearerToken || '';
  const secret = req.params.sharedSecret || source.config.sharedSecret || '';
  if (token) headers.Authorization = 'Bearer ' + token;
  if (secret) headers['X-ARCHITRON-SECRET'] = secret;
  return headers;
}

function buildFederationUrlV5_(base, queryParams) {
  if (!base) return '';
  const qs = Object.keys(queryParams || {}).map(k => encodeURIComponent(k) + '=' + encodeURIComponent(queryParams[k])).join('&');
  return qs ? base + (base.indexOf('?') >= 0 ? '&' : '?') + qs : base;
}

function writeFederationSourceResultV5_(record) {
  const sheet = SpreadsheetApp.openById(FED_KERNEL_V5.queueSpreadsheetId).getSheetByName(FED_KERNEL_V5.sheets.sourceResults);
  ensureHeader_(sheet, federationResultHeadersV5_());
  sheet.appendRow([record.requestId, record.finishedAt, record.sourceName, record.sourceType, record.status, JSON.stringify(record.result).slice(0, 45000)]);
}

function writeFederationSourceFailureV5_(failure) {
  const sheet = SpreadsheetApp.openById(FED_KERNEL_V5.queueSpreadsheetId).getSheetByName(FED_KERNEL_V5.sheets.sourceFailures);
  ensureHeader_(sheet, federationFailureHeadersV5_());
  sheet.appendRow([failure.requestId, failure.failedAt, failure.sourceName, failure.sourceType, failure.error]);
}

function logFederationSourceRunV5_(event, status, details) {
  const sheet = SpreadsheetApp.openById(FED_KERNEL_V5.queueSpreadsheetId).getSheetByName(FED_KERNEL_V5.sheets.sourceRuns);
  ensureHeader_(sheet, federationRunHeadersV5_());
  sheet.appendRow([new Date().toISOString(), event, status, JSON.stringify(details).slice(0, 45000)]);
}

function getFederationSheetObjectsV5_(sheetName, headers) {
  const ss = SpreadsheetApp.openById(FED_KERNEL_V5.queueSpreadsheetId);
  const sheet = getOrCreateSheet_(ss, sheetName);
  ensureHeader_(sheet, headers);
  const values = sheet.getDataRange().getValues();
  if (values.length < 2) return [];
  const h = values[0].map(v => String(v || '').trim());
  return values.slice(1).filter(row => row.join('').trim()).map(row => {
    const obj = {};
    h.forEach((name, i) => obj[name] = row[i]);
    return obj;
  });
}

function upsertFederationRowV5_(sheet, headers, key, rowValues) {
  ensureHeader_(sheet, headers);
  const last = sheet.getLastRow();
  if (last >= 2) {
    const keys = sheet.getRange(2, 1, last - 1, 1).getValues();
    for (let i = 0; i < keys.length; i++) {
      if (String(keys[i][0]).trim() === String(key).trim()) {
        sheet.getRange(i + 2, 1, 1, rowValues.length).setValues([rowValues]);
        return;
      }
    }
  }
  sheet.appendRow(rowValues);
}

function authorizeMetaExecutorScopes() {
  SpreadsheetApp.openById('1LSVjK9YK6u2CMrvetOcXpun4VQnOh5cE6b3w6z_KTHg');
  DriveApp.getRootFolder();
  GmailApp.search('ARCHITRON', 0, 1);
  CalendarApp.getDefaultCalendar();
  UrlFetchApp.fetch('https://www.googleapis.com/discovery/v1/apis');
  return 'AUTHORIZATION_OK';
}

function federationSourceHeadersV5_() { return ['name', 'type', 'enabled', 'baseUrl', 'authMode', 'configJson', 'risk', 'notes', 'updatedAt']; }
function federationRunHeadersV5_() { return ['loggedAt', 'event', 'status', 'detailsJson']; }
function federationResultHeadersV5_() { return ['requestId', 'finishedAt', 'sourceName', 'sourceType', 'status', 'resultJson']; }
function federationFailureHeadersV5_() { return ['requestId', 'failedAt', 'sourceName', 'sourceType', 'error']; }
function federationConnectorHeadersV5_() { return ['connectorName', 'proxyUrl', 'authMode', 'enabled', 'notes']; }
function federationWebhookHeadersV5_() { return ['webhookName', 'url', 'authMode', 'enabled', 'notes']; }
function federationDropzoneHeadersV5_() { return ['folderName', 'purpose', 'enabled', 'notes']; }
function federationSourceMapHeadersV5_() { return ['sourceName', 'entityType', 'canonicalUse', 'priority', 'notes']; }

/************************************************************
 * Manifest additions for this v5 kernel:
 * - https://www.googleapis.com/auth/drive
 * - https://www.googleapis.com/auth/documents
 * - https://www.googleapis.com/auth/spreadsheets
 * - https://www.googleapis.com/auth/gmail.readonly
 * - https://www.googleapis.com/auth/calendar.readonly
 * - https://www.googleapis.com/auth/script.external_request
 ************************************************************/
