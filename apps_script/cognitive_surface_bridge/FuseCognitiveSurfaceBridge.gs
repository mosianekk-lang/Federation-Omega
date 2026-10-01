/**
 * FUSE Cognitive Surface Bridge v1
 *
 * Bounded Google Apps Script receiver for internal cognitive work packets.
 * It performs no arbitrary HTTP call, no provider/model invocation, no IAM
 * mutation, no trigger installation and no external-effect authorization.
 */
var FUSE_COGNITIVE_PACKET_SCHEMA = 'FUSE_COGNITIVE_SURFACE_PACKET_V1';
var FUSE_COGNITIVE_MAX_PACKET_BYTES = 32768;
var FUSE_COGNITIVE_ALLOWED_SURFACES = Object.freeze({
  'GOOGLE-APPS-SCRIPT': true,
  'GOOGLE-AI-STUDIO-GEMINI': true,
  'CANVA': true,
  'OPENROUTER': true,
  'HYPERCUBE': true
});

function fuseCognitiveRequireString_(value, code) {
  if (typeof value !== 'string' || !value.trim()) throw new Error(code);
  return value.trim();
}

function fuseCognitiveNormalizePacket_(packet) {
  if (!packet || typeof packet !== 'object' || Array.isArray(packet)) {
    throw new Error('FUSE_COGNITIVE_PACKET_OBJECT_REQUIRED');
  }
  var missionId = fuseCognitiveRequireString_(packet.mission_id, 'FUSE_COGNITIVE_MISSION_REQUIRED');
  var objective = fuseCognitiveRequireString_(packet.objective, 'FUSE_COGNITIVE_OBJECTIVE_REQUIRED');
  var idem = fuseCognitiveRequireString_(packet.idempotency_key, 'FUSE_COGNITIVE_IDEMPOTENCY_REQUIRED');
  var authority = packet.authority_ceiling || 'A1_INTERNAL';
  if (authority !== 'A0_INTERNAL' && authority !== 'A1_INTERNAL') {
    throw new Error('FUSE_COGNITIVE_AUTHORITY_CEILING_EXCEEDED');
  }
  if (packet.external_effect_authorized === true || packet.provider_effect_authorized === true) {
    throw new Error('FUSE_COGNITIVE_EXTERNAL_EFFECT_AUTHORITY_FORBIDDEN');
  }
  var surfaces = Array.isArray(packet.surface_ids) ? packet.surface_ids.slice() : [];
  surfaces.forEach(function(surfaceId) {
    if (!FUSE_COGNITIVE_ALLOWED_SURFACES[surfaceId]) {
      throw new Error('FUSE_COGNITIVE_SURFACE_NOT_ALLOWLISTED:' + surfaceId);
    }
  });
  var normalized = {
    schema: FUSE_COGNITIVE_PACKET_SCHEMA,
    mission_id: missionId,
    objective: objective,
    idempotency_key: idem,
    authority_ceiling: authority,
    privacy_class: packet.privacy_class || 'P1_INTERNAL',
    surface_ids: surfaces,
    required_capabilities: Array.isArray(packet.required_capabilities) ? packet.required_capabilities.slice(0, 32) : [],
    acceptance_predicates: Array.isArray(packet.acceptance_predicates) ? packet.acceptance_predicates.slice(0, 32) : [],
    evidence_refs: Array.isArray(packet.evidence_refs) ? packet.evidence_refs.slice(0, 32) : [],
    proof_floor: packet.proof_floor || 'SEMANTIC_READBACK',
    deadline_seconds: Math.max(1, Math.min(Number(packet.deadline_seconds || 300), 300)),
    external_effect_authorized: false,
    provider_effect_authorized: false
  };
  var encoded = JSON.stringify(normalized);
  if (encoded.length > FUSE_COGNITIVE_MAX_PACKET_BYTES) {
    throw new Error('FUSE_COGNITIVE_PACKET_TOO_LARGE');
  }
  return normalized;
}

function fuseCognitivePacketDigest_(packet) {
  var normalized = fuseCognitiveNormalizePacket_(packet);
  var bytes = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    JSON.stringify(normalized),
    Utilities.Charset.UTF_8
  );
  return bytes.map(function(b) {
    var value = (b < 0 ? b + 256 : b).toString(16);
    return value.length === 1 ? '0' + value : value;
  }).join('');
}

function fuseCognitiveQueueInternal(packet) {
  var normalized = fuseCognitiveNormalizePacket_(packet);
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1500)) throw new Error('FUSE_COGNITIVE_QUEUE_LOCK_BUSY');
  try {
    var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    if (!spreadsheet) throw new Error('FUSE_COGNITIVE_ACTIVE_SPREADSHEET_REQUIRED');
    var sheet = spreadsheet.getSheetByName('AI_Meta_v3_Command_Router');
    if (!sheet) throw new Error('FUSE_COGNITIVE_ROUTER_SHEET_REQUIRED');

    var lastRow = sheet.getLastRow();
    if (lastRow >= 2) {
      var match = sheet.getRange(2, 1, lastRow - 1, 1)
        .createTextFinder(normalized.idempotency_key)
        .matchEntireCell(true)
        .findNext();
      if (match) {
        return {
          schema: FUSE_COGNITIVE_PACKET_SCHEMA,
          state: 'DUPLICATE_SUPPRESSED',
          idempotency_key: normalized.idempotency_key,
          provider_effect_authorized: false
        };
      }
    }

    sheet.appendRow([
      normalized.idempotency_key,
      new Date().toISOString(),
      'Cognitive Evolution',
      'COGNITIVE_PACKET',
      'P0',
      'QUEUED_INTERNAL',
      'FUSE_SOVEREIGN_FORMATION',
      'READBACK_REQUIRED',
      'PROCESS_BOUNDED_PACKET',
      JSON.stringify({
        mission_id: normalized.mission_id,
        digest: fuseCognitivePacketDigest_(normalized),
        surface_ids: normalized.surface_ids
      })
    ]);
    SpreadsheetApp.flush();
    return {
      schema: FUSE_COGNITIVE_PACKET_SCHEMA,
      state: 'QUEUED_INTERNAL',
      idempotency_key: normalized.idempotency_key,
      digest: fuseCognitivePacketDigest_(normalized),
      provider_effect_authorized: false
    };
  } finally {
    lock.releaseLock();
  }
}

function fuseCognitiveHeartbeat() {
  return {
    schema: 'FUSE_COGNITIVE_SURFACE_BRIDGE_HEARTBEAT_V1',
    state: 'READY_INTERNAL',
    checked_at: new Date().toISOString(),
    allowed_surfaces: Object.keys(FUSE_COGNITIVE_ALLOWED_SURFACES),
    external_effect_authorized: false,
    provider_effect_authorized: false
  };
}
