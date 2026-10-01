/**
 * FUSE Genesis / GNS4 Thin Signed Dispatch v1
 *
 * Google Apps Script is the scheduling authority only.
 * This module decides due/not-due, builds a minimal signed DispatchEnvelope,
 * appends it to the dispatch outbox, records a scheduler receipt, and exits.
 * It deliberately contains no task/business execution logic.
 */

var FUSE_GNS4D = Object.freeze({
  version: 'FUSE-GNS4-THIN-DISPATCH-V1',
  schedulerId: 'GOOGLE_APPS_SCRIPT',
  controlSpreadsheetId: '1LSVjK9YK6u2CMrvetOcXpun4VQnOh5cE6b3w6z_KTHg',
  tasksSheet: 'Scheduler_Task_Payloads_v4',
  outboxSheet: 'Scheduler_Signed_Dispatch_v4',
  receiptSheet: 'Scheduler_Dispatch_Receipt_v4',
  configSheet: 'Scheduler_24x7_Config_v4',
  signingKeyProperty: 'FUSE_GNS4_RSA_PRIVATE_KEY_PEM',
  signingKeyIdProperty: 'FUSE_GNS4_RSA_KEY_ID',
  sourceEpochProperty: 'FUSE_SOURCE_EPOCH_SHA256',
  maxDispatchesPerTick: 12,
  defaultTtlSeconds: 300
});

function fuseGns4RunThinDispatchV1(event) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) {
    return { ok: false, status: 'LOCK_BUSY', schedulerVersion: FUSE_GNS4D.version };
  }
  try {
    var ss = SpreadsheetApp.openById(FUSE_GNS4D.controlSpreadsheetId);
    fuseGns4AssertPlane_(ss);
    var now = new Date();
    var eventUid = fuseGns4ProviderEventUid_(event);
    var tasks = fuseGns4ReadTaskMetadata_(ss);
    var results = [];
    var dispatched = 0;
    var skipped = 0;
    var errors = 0;

    for (var i = 0; i < tasks.length; i += 1) {
      if (dispatched >= FUSE_GNS4D.maxDispatchesPerTick) break;
      var task = tasks[i];
      if (!task.enabled) { skipped += 1; continue; }
      var due = fuseGns4Due_(task, now);
      if (!due.due) { skipped += 1; continue; }

      try {
        var envelope = fuseGns4BuildSignedEnvelope_(task, due.periodKey, eventUid, now);
        var append = fuseGns4AppendDispatch_(ss, task, envelope, due.periodKey);
        if (append.created) dispatched += 1;
        else skipped += 1;
        results.push({
          taskId: task.taskId,
          periodKey: due.periodKey,
          dispatchId: envelope.dispatch_id,
          status: append.created ? 'SIGNED_DISPATCH_QUEUED' : 'IDEMPOTENT_PERIOD_ALREADY_QUEUED'
        });
      } catch (err) {
        errors += 1;
        results.push({
          taskId: task.taskId,
          periodKey: due.periodKey || '',
          status: 'DISPATCH_BUILD_FAILED',
          error: String(err && err.message ? err.message : err).slice(0, 1000)
        });
      }
    }

    var receipt = {
      ok: errors === 0,
      status: errors === 0 ? 'THIN_DISPATCH_CYCLE_COMPLETE' : 'THIN_DISPATCH_CYCLE_WITH_ERRORS',
      schedulerVersion: FUSE_GNS4D.version,
      providerEventId: eventUid,
      dispatched: dispatched,
      skipped: skipped,
      errors: errors,
      checkedAtUtc: new Date().toISOString(),
      semanticTaskExecutionPerformed: false,
      externalBusinessLogicPerformed: false
    };
    fuseGns4AppendReceipt_(ss, receipt, results);
    return receipt;
  } finally {
    lock.releaseLock();
  }
}

function fuseGns4BuildSignedEnvelope_(task, periodKey, providerEventId, now) {
  var props = PropertiesService.getScriptProperties();
  var privateKey = String(props.getProperty(FUSE_GNS4D.signingKeyProperty) || '').trim();
  var keyId = String(props.getProperty(FUSE_GNS4D.signingKeyIdProperty) || '').trim();
  var sourceEpoch = String(props.getProperty(FUSE_GNS4D.sourceEpochProperty) || '').toLowerCase();

  if (!privateKey) throw new Error('SIGNING_PRIVATE_KEY_UNAVAILABLE');
  if (!keyId) throw new Error('SIGNING_KEY_ID_UNAVAILABLE');
  if (!/^[0-9a-f]{64}$/.test(sourceEpoch)) throw new Error('SOURCE_EPOCH_SHA256_INVALID');
  if (!/^[0-9a-f]{64}$/.test(task.payloadSha256)) throw new Error('PAYLOAD_SHA256_INVALID');
  if (!task.payloadRef) throw new Error('PAYLOAD_REF_REQUIRED');
  if (!task.missionId) throw new Error('MISSION_ID_REQUIRED');

  var issuedAt = Math.floor(now.getTime() / 1000);
  var ttl = Number(task.ttlSeconds || FUSE_GNS4D.defaultTtlSeconds);
  if (!isFinite(ttl) || ttl < 30 || ttl > 3600) throw new Error('DISPATCH_TTL_INVALID');
  var authorityRef = 'GOOGLE_APPS_SCRIPT:TRIGGER:' + providerEventId;
  var idempotencyKey = fuseGns4Sha256Hex_([
    task.taskId, periodKey, task.payloadSha256, sourceEpoch
  ].join('|'));
  var dispatchId = 'GNS4D-' + idempotencyKey.slice(0, 40);

  var signingPayload = {
    dispatch_id: dispatchId,
    task_id: task.taskId,
    idempotency_key: idempotencyKey,
    mission_id: task.missionId,
    scheduler_id: FUSE_GNS4D.schedulerId,
    source_epoch_digest: sourceEpoch,
    payload_sha256: task.payloadSha256,
    authority_ref: authorityRef,
    provider_event_id: providerEventId,
    issued_at: issuedAt,
    expires_at: issuedAt + ttl,
    effect_class: task.effectClass
  };

  var canonical = fuseGns4Canon_(signingPayload);
  var signatureBytes = Utilities.computeRsaSha256Signature(canonical, privateKey);
  var signatureB64 = Utilities.base64Encode(signatureBytes);

  var envelope = {
    dispatch_id: signingPayload.dispatch_id,
    task_id: signingPayload.task_id,
    idempotency_key: signingPayload.idempotency_key,
    mission_id: signingPayload.mission_id,
    scheduler_id: signingPayload.scheduler_id,
    source_epoch_digest: signingPayload.source_epoch_digest,
    payload_sha256: signingPayload.payload_sha256,
    authority_ref: signingPayload.authority_ref,
    provider_event_id: signingPayload.provider_event_id,
    issued_at: signingPayload.issued_at,
    expires_at: signingPayload.expires_at,
    signature_key_id: keyId,
    signature_algorithm: 'RSA_SHA256',
    signature_b64: signatureB64,
    effect_class: signingPayload.effect_class
  };
  return envelope;
}

function fuseGns4AppendDispatch_(ss, task, envelope, periodKey) {
  var sheet = ss.getSheetByName(FUSE_GNS4D.outboxSheet);
  var values = sheet.getDataRange().getDisplayValues();
  var idx = fuseGns4HeaderIndex_(values[0] || []);
  for (var i = 1; i < values.length; i += 1) {
    if (values[i][idx.idempotency_key] === envelope.idempotency_key) {
      return { created: false, row: i + 1 };
    }
  }
  sheet.appendRow([
    envelope.dispatch_id,
    envelope.idempotency_key,
    envelope.task_id,
    envelope.mission_id,
    periodKey,
    task.payloadRef,
    envelope.payload_sha256,
    envelope.source_epoch_digest,
    envelope.authority_ref,
    envelope.provider_event_id,
    envelope.issued_at,
    envelope.expires_at,
    envelope.effect_class,
    envelope.signature_key_id,
    envelope.signature_algorithm,
    envelope.signature_b64,
    'SIGNED_DISPATCH_QUEUED',
    new Date().toISOString()
  ]);
  SpreadsheetApp.flush();
  var row = sheet.getLastRow();
  var readback = sheet.getRange(row, 1, 1, 18).getDisplayValues()[0];
  if (readback[0] !== envelope.dispatch_id ||
      readback[1] !== envelope.idempotency_key ||
      readback[5] !== task.payloadRef ||
      readback[16] !== 'SIGNED_DISPATCH_QUEUED') {
    throw new Error('DISPATCH_OUTBOX_READBACK_MISMATCH');
  }
  return { created: true, row: row };
}

function fuseGns4AppendReceipt_(ss, receipt, results) {
  var sheet = ss.getSheetByName(FUSE_GNS4D.receiptSheet);
  sheet.appendRow([
    new Date().toISOString(),
    receipt.providerEventId,
    receipt.status,
    receipt.dispatched,
    receipt.skipped,
    receipt.errors,
    JSON.stringify(results),
    'SCHEDULER_ONLY_NO_TASK_EXECUTION'
  ]);
}

function fuseGns4ReadTaskMetadata_(ss) {
  var values = ss.getSheetByName(FUSE_GNS4D.tasksSheet).getDataRange().getValues();
  if (values.length < 2) return [];
  var idx = fuseGns4HeaderIndex_(values[0]);
  return values.slice(1).filter(function(row) {
    return String(row[idx.task_id] || '').trim() !== '';
  }).map(function(row) {
    var effectClass = String(row[idx.effect_class] || 'A1_INTERNAL').trim();
    if (['A0_READ_ONLY','A1_INTERNAL','A2_EXACT_PREAUTHORIZED'].indexOf(effectClass) < 0) {
      throw new Error('EFFECT_CLASS_INVALID');
    }
    return {
      taskId: String(row[idx.task_id]).trim(),
      missionId: String(row[idx.mission_id]).trim(),
      schedule: String(row[idx.schedule]).trim(),
      timezone: String(row[idx.timezone] || 'Africa/Johannesburg').trim(),
      enabled: row[idx.enabled] === true || String(row[idx.enabled]).toUpperCase() === 'TRUE',
      payloadRef: String(row[idx.payload_ref]).trim(),
      payloadSha256: String(row[idx.payload_sha256]).toLowerCase().trim(),
      effectClass: effectClass,
      ttlSeconds: Number(row[idx.ttl_seconds] || FUSE_GNS4D.defaultTtlSeconds)
    };
  });
}

function fuseGns4Due_(task, now) {
  if (!task.schedule) return { due: false, periodKey: '', reason: 'NO_SCHEDULE' };
  var minute = Utilities.formatDate(now, task.timezone, 'yyyyMMddHHmm');
  // F328 is intentionally scheduler-thin. The schedule compiler must materialize
  // exact due-period keys into the task metadata/control plane before this tick.
  // A task is due only when schedule exactly equals the current period key or '*'.
  var due = task.schedule === '*' || task.schedule === minute;
  return { due: due, periodKey: minute, reason: due ? 'PERIOD_MATCH' : 'PERIOD_NOT_DUE' };
}

function fuseGns4ProviderEventUid_(event) {
  var uid = String(event && event.triggerUid ? event.triggerUid : '').trim();
  if (!uid) throw new Error('PROVIDER_TRIGGER_UID_REQUIRED');
  return uid;
}

function fuseGns4AssertPlane_(ss) {
  [
    FUSE_GNS4D.tasksSheet,
    FUSE_GNS4D.outboxSheet,
    FUSE_GNS4D.receiptSheet,
    FUSE_GNS4D.configSheet
  ].forEach(function(name) {
    if (!ss.getSheetByName(name)) throw new Error('MISSING_REQUIRED_SHEET:' + name);
  });
}

function fuseGns4HeaderIndex_(header) {
  var idx = {};
  header.forEach(function(name, i) { idx[String(name).trim()] = i; });
  return idx;
}

function fuseGns4Canon_(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) {
    return '[' + value.map(fuseGns4Canon_).join(',') + ']';
  }
  if (typeof value === 'object') {
    return '{' + Object.keys(value).sort().map(function(key) {
      return JSON.stringify(key) + ':' + fuseGns4Canon_(value[key]);
    }).join(',') + '}';
  }
  return JSON.stringify(value);
}

function fuseGns4Sha256Hex_(value) {
  return Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    String(value),
    Utilities.Charset.UTF_8
  ).map(function(byte) {
    var n = byte < 0 ? byte + 256 : byte;
    return ('0' + n.toString(16)).slice(-2);
  }).join('');
}
