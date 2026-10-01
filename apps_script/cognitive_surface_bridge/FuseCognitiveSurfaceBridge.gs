/**
 * FUSE Cognitive Surface Bridge v1: pure packet preparation only.
 * The existing canonical writer remains responsible for target/schema/fence
 * verification, idempotent commit and effect readback. This source binds none.
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
  return value;
}

function fuseCognitiveArray_(packet, key, required) {
  var value = packet[key];
  if (value === undefined && !required) return Object.freeze([]);
  if (required && (value === undefined || (Array.isArray(value) && !value.length))) {
    throw new Error('FUSE_COGNITIVE_ACCEPTANCE_REQUIRED');
  }
  if (!Array.isArray(value)) throw new Error('FUSE_COGNITIVE_ARRAY_REQUIRED:' + key);
  if (value.length > 32) throw new Error('FUSE_COGNITIVE_ARRAY_TOO_LARGE:' + key);
  return Object.freeze(value.map(function(item) {
    return fuseCognitiveRequireString_(item, 'FUSE_COGNITIVE_STRING_REQUIRED:' + key);
  }));
}

function fuseCognitiveBoolean_(packet, key) {
  if (packet[key] === undefined) return false;
  if (typeof packet[key] !== 'boolean') throw new Error('FUSE_COGNITIVE_BOOLEAN_REQUIRED:' + key);
  return packet[key];
}

function fuseCognitiveNormalizePacket_(packet) {
  if (!packet || typeof packet !== 'object' || Array.isArray(packet)) {
    throw new Error('FUSE_COGNITIVE_PACKET_OBJECT_REQUIRED');
  }
  var fields = ['schema', 'mission_id', 'objective', 'idempotency_key', 'authority_ceiling',
    'privacy_class', 'maximum_effect', 'cost_ceiling', 'surface_ids', 'required_capabilities',
    'acceptance_predicates', 'evidence_refs', 'uncertainty', 'falsifiers', 'proof_floor',
    'deadline_seconds', 'automation_required', 'research_required', 'creative_required',
    'challenger_required', 'external_effect_authorized', 'provider_effect_authorized'];
  Object.keys(packet).forEach(function(key) {
    if (fields.indexOf(key) === -1) throw new Error('FUSE_COGNITIVE_UNKNOWN_PACKET_FIELD:' + key);
  });
  if (packet.schema !== undefined && packet.schema !== FUSE_COGNITIVE_PACKET_SCHEMA) {
    throw new Error('FUSE_COGNITIVE_PACKET_SCHEMA_INVALID');
  }
  var authority = packet.authority_ceiling === undefined ? 'A1_INTERNAL' : packet.authority_ceiling;
  if (authority !== 'A0_INTERNAL' && authority !== 'A1_INTERNAL') {
    throw new Error('FUSE_COGNITIVE_AUTHORITY_CEILING_EXCEEDED');
  }
  ['external_effect_authorized', 'provider_effect_authorized'].forEach(function(key) {
    if (packet[key] !== undefined && packet[key] !== false) {
      throw new Error('FUSE_COGNITIVE_EXTERNAL_EFFECT_AUTHORITY_FORBIDDEN');
    }
  });
  var maximumEffect = packet.maximum_effect === undefined ? 'INTERNAL' : packet.maximum_effect;
  if (maximumEffect !== 'OBSERVE' && maximumEffect !== 'INTERNAL') {
    throw new Error('FUSE_COGNITIVE_EFFECT_CEILING_EXCEEDED');
  }
  var cost = packet.cost_ceiling === undefined ? 0 : packet.cost_ceiling;
  if (typeof cost !== 'number' || !Number.isFinite(cost) || cost < 0) {
    throw new Error('FUSE_COGNITIVE_COST_CEILING_INVALID');
  }
  var deadline = packet.deadline_seconds === undefined ? 300 : packet.deadline_seconds;
  if (typeof deadline !== 'number' || !Number.isSafeInteger(deadline) || deadline < 1) {
    throw new Error('FUSE_COGNITIVE_DEADLINE_INVALID');
  }
  var surfaces = fuseCognitiveArray_(packet, 'surface_ids', false);
  surfaces.forEach(function(surfaceId) {
    if (!Object.prototype.hasOwnProperty.call(FUSE_COGNITIVE_ALLOWED_SURFACES, surfaceId)) {
      throw new Error('FUSE_COGNITIVE_SURFACE_NOT_ALLOWLISTED:' + surfaceId);
    }
  });
  var normalized = {
    schema: FUSE_COGNITIVE_PACKET_SCHEMA,
    mission_id: fuseCognitiveRequireString_(packet.mission_id, 'FUSE_COGNITIVE_MISSION_REQUIRED'),
    objective: fuseCognitiveRequireString_(packet.objective, 'FUSE_COGNITIVE_OBJECTIVE_REQUIRED'),
    idempotency_key: fuseCognitiveRequireString_(packet.idempotency_key, 'FUSE_COGNITIVE_IDEMPOTENCY_REQUIRED'),
    authority_ceiling: authority,
    privacy_class: fuseCognitiveRequireString_(packet.privacy_class === undefined ? 'P1_INTERNAL' : packet.privacy_class,
      'FUSE_COGNITIVE_PRIVACY_REQUIRED'),
    maximum_effect: maximumEffect,
    cost_ceiling: cost,
    surface_ids: surfaces,
    required_capabilities: fuseCognitiveArray_(packet, 'required_capabilities', false),
    acceptance_predicates: fuseCognitiveArray_(packet, 'acceptance_predicates', true),
    evidence_refs: fuseCognitiveArray_(packet, 'evidence_refs', false),
    uncertainty: fuseCognitiveArray_(packet, 'uncertainty', false),
    falsifiers: fuseCognitiveArray_(packet, 'falsifiers', false),
    proof_floor: fuseCognitiveRequireString_(packet.proof_floor === undefined ? 'SEMANTIC_READBACK' : packet.proof_floor,
      'FUSE_COGNITIVE_PROOF_FLOOR_REQUIRED'),
    deadline_seconds: deadline,
    automation_required: fuseCognitiveBoolean_(packet, 'automation_required'),
    research_required: fuseCognitiveBoolean_(packet, 'research_required'),
    creative_required: fuseCognitiveBoolean_(packet, 'creative_required'),
    challenger_required: fuseCognitiveBoolean_(packet, 'challenger_required'),
    external_effect_authorized: false,
    provider_effect_authorized: false
  };
  if (Utilities.newBlob(JSON.stringify(normalized)).getBytes().length > FUSE_COGNITIVE_MAX_PACKET_BYTES) {
    throw new Error('FUSE_COGNITIVE_PACKET_TOO_LARGE');
  }
  return Object.freeze(normalized);
}

function fuseCognitivePacketDigest_(packet) {
  var normalized = fuseCognitiveNormalizePacket_(packet);
  var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, JSON.stringify(normalized), Utilities.Charset.UTF_8);
  return bytes.map(function(b) {
    var value = (b < 0 ? b + 256 : b).toString(16);
    return value.length === 1 ? '0' + value : value;
  }).join('');
}

function fuseCognitivePrepareInternal(packet) {
  var normalized = fuseCognitiveNormalizePacket_(packet);
  return Object.freeze({
    schema: FUSE_COGNITIVE_PACKET_SCHEMA,
    state: 'PREPARED_NOT_QUEUED',
    packet: normalized,
    idempotency_key: normalized.idempotency_key,
    digest: fuseCognitivePacketDigest_(normalized),
    canonical_writer_binding: 'UNASSESSED',
    requires_existing_writer_checks: Object.freeze(['TARGET', 'SCHEMA', 'REVISION', 'AUTHORITY', 'FENCE', 'IDEMPOTENCY', 'EFFECT_READBACK']),
    write_performed: false,
    external_effect_authorized: false,
    provider_effect_authorized: false,
    provider_execution_proven: false
  });
}

// Compatibility entry point: preparation is deliberately not a queue commit.
function fuseCognitiveQueueInternal(packet) {
  return fuseCognitivePrepareInternal(packet);
}

function fuseCognitiveHeartbeat() {
  return {
    schema: 'FUSE_COGNITIVE_SURFACE_BRIDGE_HEARTBEAT_V1',
    state: 'SOURCE_AVAILABLE',
    runtime_readiness: 'UNASSESSED',
    canonical_writer_binding: 'UNASSESSED',
    checked_at: new Date().toISOString(),
    allowed_surfaces: Object.keys(FUSE_COGNITIVE_ALLOWED_SURFACES),
    write_performed: false,
    external_effect_authorized: false,
    provider_effect_authorized: false,
    provider_execution_proven: false
  };
}
