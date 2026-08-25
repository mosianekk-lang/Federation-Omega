/**
 * SOVARA signed minimum-scope ingress.
 *
 * Required Script Property:
 *   SOVARA_GATEWAY_HMAC_SECRET — random, rotatable key material.
 *
 * The secret is never accepted as a request field and never written to logs.
 * Replay state is sharded so no single Script Property approaches the
 * provider's per-value size ceiling. Corrupt replay state fails closed.
 */
const SOVARA_GATEWAY_SECURITY = Object.freeze({
  VERSION: '1.1.0',
  SECRET_PROPERTY: 'SOVARA_GATEWAY_HMAC_SECRET',
  NONCE_LEDGER_PREFIX: 'SOVARA_GATEWAY_NONCE_LEDGER_V2_',
  NONCE_SHARDS: 16,
  MAX_NONCES_PER_SHARD: 32,
  MAX_PROPERTY_CHARS: 7500,
  CANONICAL_TARGET_PROJECT_NUMBER: '257649435135',
  MAX_AGE_MS: 5 * 60 * 1000,
  MAX_FUTURE_SKEW_MS: 30 * 1000,
  ALLOWED_ACTIONS: Object.freeze(['STATUS', 'CHALLENGE'])
});

function SOVARA_GATEWAY_verifySignedEnvelope_(request) {
  if (!request || typeof request !== 'object' || Array.isArray(request)) {
    throw new Error('SIGNED_ENVELOPE_REQUIRED');
  }
  SOVARA_GATEWAY_assertRequestShape_(request);

  const timestamp = String(request.timestamp || '');
  const nonce = String(request.nonce || '');
  const signature = String(request.signature || '').toLowerCase();
  const action = String(request.action || '').trim().toUpperCase();
  const targetProjectNumber = String(request.targetProjectNumber || '');

  if (!timestamp || !nonce || !signature || !action || !targetProjectNumber) {
    throw new Error('SIGNED_ENVELOPE_FIELDS_REQUIRED');
  }
  if (!/^[a-f0-9]{64}$/.test(signature)) {
    throw new Error('SIGNED_ENVELOPE_SIGNATURE_INVALID');
  }
  if (!/^[A-Za-z0-9_.:-]{16,160}$/.test(nonce)) {
    throw new Error('SIGNED_ENVELOPE_NONCE_INVALID');
  }
  if (SOVARA_GATEWAY_SECURITY.ALLOWED_ACTIONS.indexOf(action) < 0) {
    throw new Error('ACTION_NOT_ALLOWLISTED');
  }
  if (targetProjectNumber !== SOVARA_GATEWAY_SECURITY.CANONICAL_TARGET_PROJECT_NUMBER) {
    throw new Error('CANONICAL_TARGET_MISMATCH');
  }

  const issuedAt = new Date(timestamp);
  if (isNaN(issuedAt.getTime())) {
    throw new Error('SIGNED_ENVELOPE_TIMESTAMP_INVALID');
  }
  const ageMs = Date.now() - issuedAt.getTime();
  if (
    ageMs > SOVARA_GATEWAY_SECURITY.MAX_AGE_MS ||
    ageMs < -SOVARA_GATEWAY_SECURITY.MAX_FUTURE_SKEW_MS
  ) {
    throw new Error('SIGNED_ENVELOPE_EXPIRED');
  }

  const secret = String(
    PropertiesService.getScriptProperties()
      .getProperty(SOVARA_GATEWAY_SECURITY.SECRET_PROPERTY) || ''
  );
  if (secret.length < 32) {
    throw new Error('GATEWAY_HMAC_SECRET_NOT_CONFIGURED');
  }

  const unsigned = JSON.parse(JSON.stringify(request));
  delete unsigned.signature;
  const canonical = SOVARA_GATEWAY_canonicalJson_(unsigned);
  const expected = SOVARA_GATEWAY_hex_(
    Utilities.computeHmacSha256Signature(
      canonical,
      secret,
      Utilities.Charset.UTF_8
    )
  );
  if (!SOVARA_GATEWAY_constantTimeEqual_(expected, signature)) {
    throw new Error('SIGNED_ENVELOPE_AUTHENTICATION_FAILED');
  }

  SOVARA_GATEWAY_claimNonce_(nonce, issuedAt.getTime());

  return Object.freeze({
    action: action,
    targetProjectNumber: targetProjectNumber,
    issuedAt: issuedAt.toISOString(),
    requestSha256: SOVARA_GATEWAY_sha256_(canonical),
    authentication: 'HMAC_SHA256_TIMESTAMP_NONCE_VERIFIED',
    replayLedger: 'SHARDED_DURABLE_HASH_ONLY_V2',
    providerAuthorityGranted: false,
    providerMutationAuthorized: false
  });
}

function SOVARA_GATEWAY_assertRequestShape_(request) {
  const allowed = Object.freeze({
    timestamp: true,
    nonce: true,
    signature: true,
    action: true,
    targetProjectNumber: true,
    payload: true
  });
  Object.keys(request).forEach(function (key) {
    if (!allowed[key]) {
      throw new Error('SIGNED_ENVELOPE_FIELD_NOT_ALLOWED');
    }
  });

  const payload = request.payload === undefined ? {} : request.payload;
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('SIGNED_ENVELOPE_PAYLOAD_INVALID');
  }
  const action = String(request.action || '').trim().toUpperCase();
  const keys = Object.keys(payload).sort();
  if (action === 'STATUS' && keys.length !== 0) {
    throw new Error('STATUS_PAYLOAD_NOT_ALLOWED');
  }
  if (action === 'CHALLENGE') {
    if (keys.length !== 1 || keys[0] !== 'challenge') {
      throw new Error('CHALLENGE_PAYLOAD_INVALID');
    }
    const challenge = String(payload.challenge || '');
    if (!challenge || challenge.length > 4096) {
      throw new Error('CHALLENGE_PAYLOAD_INVALID');
    }
    if (
      /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/.test(challenge) ||
      /\bBearer\s+[A-Za-z0-9._~+\/-]+=*/i.test(challenge) ||
      /\b(?:sk-(?:proj-)?|gh[pousr]_)[A-Za-z0-9_-]{16,}\b/.test(challenge) ||
      /\bAIza[0-9A-Za-z_-]{20,}\b/.test(challenge)
    ) {
      throw new Error('RAW_CREDENTIAL_LIKE_CHALLENGE_REJECTED');
    }
  }
}

function SOVARA_GATEWAY_claimNonce_(nonce, issuedAtMs) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const properties = PropertiesService.getScriptProperties();
    const now = Date.now();
    const nonceHash = SOVARA_GATEWAY_sha256_(nonce);
    const shardId = nonceHash.charAt(0);
    const propertyName = SOVARA_GATEWAY_SECURITY.NONCE_LEDGER_PREFIX + shardId;
    const stored = properties.getProperty(propertyName);
    let entries = [];

    if (stored) {
      try {
        entries = JSON.parse(stored);
      } catch (error) {
        throw new Error('GATEWAY_NONCE_LEDGER_CORRUPT');
      }
      if (!Array.isArray(entries) || entries.some(function (entry) {
        return !Array.isArray(entry) || entry.length !== 2 ||
          !/^[a-f0-9]{64}$/.test(String(entry[0] || '')) ||
          !isFinite(Number(entry[1]));
      })) {
        throw new Error('GATEWAY_NONCE_LEDGER_CORRUPT');
      }
    }

    entries = entries.filter(function (entry) {
      return Number(entry[1]) > now;
    });
    if (entries.some(function (entry) { return entry[0] === nonceHash; })) {
      throw new Error('SIGNED_ENVELOPE_REPLAY_REJECTED');
    }

    entries.push([
      nonceHash,
      Math.max(now, Number(issuedAtMs || now)) + SOVARA_GATEWAY_SECURITY.MAX_AGE_MS
    ]);
    entries.sort(function (left, right) { return Number(left[1]) - Number(right[1]); });
    while (entries.length > SOVARA_GATEWAY_SECURITY.MAX_NONCES_PER_SHARD) {
      entries.shift();
    }

    let serialized = JSON.stringify(entries);
    while (
      serialized.length > SOVARA_GATEWAY_SECURITY.MAX_PROPERTY_CHARS &&
      entries.length > 1
    ) {
      entries.shift();
      serialized = JSON.stringify(entries);
    }
    if (serialized.length > SOVARA_GATEWAY_SECURITY.MAX_PROPERTY_CHARS) {
      throw new Error('GATEWAY_NONCE_LEDGER_CAPACITY_EXCEEDED');
    }
    properties.setProperty(propertyName, serialized);
  } finally {
    lock.releaseLock();
  }
}

function SOVARA_GATEWAY_canonicalJson_(value) {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return '[' + value.map(SOVARA_GATEWAY_canonicalJson_).join(',') + ']';
  }
  return '{' + Object.keys(value).sort().map(function (key) {
    return JSON.stringify(key) + ':' +
      SOVARA_GATEWAY_canonicalJson_(value[key]);
  }).join(',') + '}';
}

function SOVARA_GATEWAY_sha256_(text) {
  return SOVARA_GATEWAY_hex_(
    Utilities.computeDigest(
      Utilities.DigestAlgorithm.SHA_256,
      String(text || ''),
      Utilities.Charset.UTF_8
    )
  );
}

function SOVARA_GATEWAY_hex_(bytes) {
  return bytes.map(function (byte) {
    const value = byte < 0 ? byte + 256 : byte;
    return value.toString(16).padStart(2, '0');
  }).join('');
}

function SOVARA_GATEWAY_constantTimeEqual_(left, right) {
  const a = String(left || '');
  const b = String(right || '');
  let difference = a.length ^ b.length;
  const length = Math.max(a.length, b.length);
  for (let index = 0; index < length; index++) {
    difference |= (a.charCodeAt(index) || 0) ^ (b.charCodeAt(index) || 0);
  }
  return difference === 0;
}
