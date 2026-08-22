import { ControlPlaneError, fail } from './errors.js';

export const TRUTH_STATES = Object.freeze([
  'DESIGNED',
  'IMPLEMENTED',
  'TESTED',
  'REGISTERED',
  'AUTHORIZED',
  'READY',
  'DEPLOYED',
  'PROVEN',
]);

const EVIDENCE_GRADES = new Set([
  'OFFICIAL_PRIMARY',
  'OFFICIAL_RESEARCH',
  'OFFICIAL_PRODUCT',
  'PUBLIC_STANDARD_OVERVIEW',
  'UNVERIFIED_PRIVATE',
]);

function object(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    fail('INVALID_INPUT', `${label} must be an object`);
  }
  return value;
}

function text(value, label) {
  if (typeof value !== 'string' || !value.trim()) fail('INVALID_INPUT', `${label} is required`);
  return value;
}

function numberInRange(value, label, minimum, maximum) {
  if (!Number.isFinite(value) || value < minimum || value > maximum) {
    fail('INVALID_INPUT', `${label} must be between ${minimum} and ${maximum}`);
  }
  return value;
}

export function parseTimestamp(value, label) {
  text(value, label);
  const milliseconds = Date.parse(value);
  if (!Number.isFinite(milliseconds)) fail('INVALID_INPUT', `${label} must be an ISO-8601 timestamp`);
  return milliseconds;
}

export function validateRegistry(registry) {
  if (!Array.isArray(registry) || registry.length === 0) {
    fail('INVALID_INPUT', 'registry must be a non-empty array');
  }
  const ids = new Set();
  for (const [index, source] of registry.entries()) {
    object(source, `registry[${index}]`);
    const id = text(source.id, `registry[${index}].id`);
    if (ids.has(id)) fail('INVALID_INPUT', `duplicate source id: ${id}`);
    ids.add(id);
    text(source.provider, `${id}.provider`);
    text(source.title, `${id}.title`);
    text(source.publisher, `${id}.publisher`);
    text(source.sourceType, `${id}.sourceType`);
    const url = new URL(text(source.canonicalUrl, `${id}.canonicalUrl`));
    if (url.protocol !== 'https:') fail('INVALID_INPUT', `${id}.canonicalUrl must use HTTPS`);
    if (!EVIDENCE_GRADES.has(source.evidenceGrade)) {
      fail('INVALID_INPUT', `${id}.evidenceGrade is invalid`);
    }
    parseTimestamp(source.verifiedAt, `${id}.verifiedAt`);
    numberInRange(source.freshnessSlaDays, `${id}.freshnessSlaDays`, 1, 3660);
    if (typeof source.critical !== 'boolean') fail('INVALID_INPUT', `${id}.critical must be boolean`);
    if (!Array.isArray(source.dimensions) || source.dimensions.length === 0) {
      fail('INVALID_INPUT', `${id}.dimensions must be non-empty`);
    }
    if (source.scoreEligible !== false && source.evidenceGrade === 'UNVERIFIED_PRIVATE') {
      fail('INVALID_INPUT', `${id} unverified private evidence must be score-excluded`);
    }
  }
  return registry;
}

export function validateDimensions(dimensions) {
  if (!Array.isArray(dimensions) || dimensions.length === 0) {
    fail('INVALID_INPUT', 'dimensions must be a non-empty array');
  }
  const ids = new Set();
  for (const [index, dimension] of dimensions.entries()) {
    object(dimension, `dimensions[${index}]`);
    const id = text(dimension.id, `dimensions[${index}].id`);
    if (ids.has(id)) fail('INVALID_INPUT', `duplicate dimension id: ${id}`);
    ids.add(id);
    text(dimension.name, `${id}.name`);
    numberInRange(dimension.weight, `${id}.weight`, 0.01, 1000);
    numberInRange(dimension.targetScore, `${id}.targetScore`, 1, 100);
    if (typeof dimension.critical !== 'boolean') fail('INVALID_INPUT', `${id}.critical must be boolean`);
    const factors = object(dimension.opportunityFactors, `${id}.opportunityFactors`);
    for (const key of ['dependencyUnlock', 'impact', 'riskReduction', 'authorityFit', 'verifiability', 'costExposure', 'latency']) {
      numberInRange(factors[key], `${id}.opportunityFactors.${key}`, 0, 5);
    }
  }
  return dimensions;
}

export function validateState(state, dimensions) {
  object(state, 'state');
  text(state.systemId, 'state.systemId');
  text(state.asOf, 'state.asOf');
  parseTimestamp(state.asOf, 'state.asOf');
  if (!Array.isArray(state.dimensions)) fail('INVALID_INPUT', 'state.dimensions must be an array');
  const known = new Set(dimensions.map((item) => item.id));
  const seen = new Set();
  for (const entry of state.dimensions) {
    object(entry, 'state dimension');
    text(entry.id, 'state dimension id');
    if (!known.has(entry.id)) fail('INVALID_INPUT', `unknown state dimension: ${entry.id}`);
    if (seen.has(entry.id)) fail('INVALID_INPUT', `duplicate state dimension: ${entry.id}`);
    seen.add(entry.id);
    numberInRange(entry.maturity, `${entry.id}.maturity`, 0, 100);
    if (!TRUTH_STATES.includes(entry.truthState)) {
      fail('INVALID_INPUT', `${entry.id}.truthState is invalid`);
    }
    if (!Array.isArray(entry.evidenceRefs)) fail('INVALID_INPUT', `${entry.id}.evidenceRefs must be an array`);
  }
  return state;
}

export function validateObservation(observation, source) {
  object(observation, 'observation');
  text(observation.sourceId, 'observation.sourceId');
  if (observation.sourceId !== source.id) fail('INVALID_INPUT', 'observation source does not match registry source');
  if (observation.status !== 'VERIFIED') fail('INVALID_INPUT', 'observation.status must equal VERIFIED');
  if (observation.publisherMatch !== true || observation.canonicalUrlMatch !== true) {
    fail('SOURCE_IDENTITY_MISMATCH', `source identity proof failed for ${source.id}`);
  }
  if (observation.canonicalUrl !== source.canonicalUrl) {
    fail('SOURCE_IDENTITY_MISMATCH', `canonical URL changed for ${source.id}`);
  }
  parseTimestamp(observation.observedAt, 'observation.observedAt');
  text(observation.observedVersion, 'observation.observedVersion');
  if (!/^sha256:[0-9a-f]{64}$/.test(observation.contentHash || '')) {
    fail('INVALID_INPUT', 'observation.contentHash must be a SHA-256 digest');
  }
  if (observation.sourceUpdatedAt) parseTimestamp(observation.sourceUpdatedAt, 'observation.sourceUpdatedAt');
  return observation;
}

export function asControlPlaneError(error) {
  return error instanceof ControlPlaneError
    ? error
    : new ControlPlaneError('INTERNAL_ERROR', 'Unexpected control-plane failure', { status: 500 });
}
