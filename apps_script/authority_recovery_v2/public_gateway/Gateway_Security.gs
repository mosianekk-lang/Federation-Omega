/**
 * SOVARA signed minimum-scope ingress — v2.
 *
 * Required Script Property:
 *   SOVARA_GATEWAY_HMAC_SECRET — random, rotatable key material (32+ chars).
 *
 * The secret is never accepted in a request field, response, log, Sheet or
 * durable receipt. This project exposes read-only actions only.
 */
const SOVARA_GATEWAY_SECURITY = Object.freeze({
  VERSION: '2.0.0',
  SECRET_PROPERTY: 'SOVARA_GATEWAY_HMAC_SECRET',
  NONCE_LEDGER_PROPERTY: 'SOVARA_GATEWAY_NONCE_LEDGER_V2',
  CANONICAL_TARGET_PROJECT_NUMBER: '257649435135',
  MAX_AGE_MS: 5 * 60 * 1000,
  MAX_FUTURE_SKEW_MS: 30 * 1000,
  MAX_NONCES: 512,
  MAX_BODY_CHARACTERS: 32768,
  MAX_CANONICAL_PAYLOAD_CHARACTERS: 16384,
  MAX_PAYLOAD_DEPTH: 8,
  ALLOWED_ACTIONS: Object.freeze(['STATUS', 'CHALLENGE'])
});

function SOVARA_GATEWAY_verifySignedEnvelope_(request) {
  if (!request || typeof request !== 'object' || Array.isArray(request)) {
    throw new Error('SIGNED_ENVELOPE_REQUIRED');
  }

  const version = String(request.version || '');
  const requestId = String(request.requestId || '');
  const timestamp = String(request.timestamp || '');
  const nonce = String(request.nonce || '');
  const signature = String(request.signature || '').toLowerCase();
  const action = String(request.action || '').trim().toUpperCase();
  const targetProjectNumber = String(request.targetProjectNumber || '');

  if (
    version !== '2' ||
    !requestId ||
    !timestamp ||
    !nonce ||
    !signature ||
    !action ||
    !targetProjectNumber
  ) {
    throw new Error('SIGNED_ENVELOPE_FIELDS_REQUIRED');
  }
  if (!/^[A-Za-z0-9_.:-]{12,160}$/.test(requestId)) {
    throw new Error('SIGNED_ENVELOPE_REQUEST_ID_INVALID');
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
  if (
    targetProjectNumber !==
    SOVARA_GATEWAY_SECURITY.CANONICAL_TARGET_PROJECT_NUMBER
  ) {
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

  SOVARA_GATEWAY_assertPublicSafePayload_(request.payload, 'payload', 0);

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
  if (
    canonical.length >
    SOVARA_GATEWAY_SECURITY.MAX_CANONICAL_PAYLOAD_CHARACTERS
  ) {
    throw new Error('SIGNED_ENVELOPE_TOO_LARGE');
  }
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
    requestId: requestId,
    action: action,
    targetProjectNumber: targetProjectNumber,
    issuedAt: issuedAt.toISOString(),
    requestSha256: SOVARA_GATEWAY_sha256_(canonical),
    authentication: 'HMAC_SHA256_TIMESTAMP_NONCE_VERIFIED',
    providerAuthorityGranted: false,
    providerMutationAuthorized: false
  });
}

function SOVARA_GATEWAY_claimNonce_(nonce, issuedAtMs) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const properties = PropertiesService.getScriptProperties();
    const now = Date.now();
    const nonceHash = SOVARA_GATEWAY_sha256_(nonce);
    let ledger = {};
    const stored = properties.getProperty(
      SOVARA_GATEWAY_SECURITY.NONCE_LEDGER_PROPERTY
    );
    if (stored) {
      try {
        ledger = JSON.parse(stored);
      } catch (error) {
        ledger = {};
      }
    }

    Object.keys(ledger).forEach(function (key) {
      if (Number(ledger[key]) <= now) {
        delete ledger[key];
      }
    });
    if (Object.prototype.hasOwnProperty.call(ledger, nonceHash)) {
      throw new Error('SIGNED_ENVELOPE_REPLAY_REJECTED');
    }

    ledger[nonceHash] = Math.max(now, Number(issuedAtMs || now)) +
      SOVARA_GATEWAY_SECURITY.MAX_AGE_MS;

    const entries = Object.keys(ledger)
      .map(function (key) { return [key, Number(ledger[key])]; })
      .sort(function (left, right) { return left[1] - right[1]; });
    while (entries.length > SOVARA_GATEWAY_SECURITY.MAX_NONCES) {
      const removed = entries.shift();
      delete ledger[removed[0]];
    }
    properties.setProperty(
      SOVARA_GATEWAY_SECURITY.NONCE_LEDGER_PROPERTY,
      JSON.stringify(ledger)
    );
  } finally {
    lock.releaseLock();
  }
}

function SOVARA_GATEWAY_assertPublicSafePayload_(value, path, depth) {
  if (depth > SOVARA_GATEWAY_SECURITY.MAX_PAYLOAD_DEPTH) {
    throw new Error('PAYLOAD_DEPTH_EXCEEDED');
  }
  if (value === null || typeof value === 'undefined') {
    return;
  }
  if (Array.isArray(value)) {
    value.forEach(function (item, index) {
      SOVARA_GATEWAY_assertPublicSafePayload_(
        item,
        path + '[' + index + ']',
        depth + 1
      );
    });
    return;
  }
  if (typeof value === 'object') {
    Object.keys(value).forEach(function (key) {
      const normalized = String(key).replace(/[_-]/g, '').toLowerCase();
      if (
        /^(secret|password|passwd|token|accesstoken|refreshtoken|idtoken|apikey|privatekey|authorization|cookie|credential|clientsecret)$/.test(normalized)
      ) {
        throw new Error('SECRET_BEARING_PAYLOAD_FIELD_REJECTED');
      }
      SOVARA_GATEWAY_assertPublicSafePayload_(
        value[key],
        path + '.' + key,
        depth + 1
      );
    });
    return;
  }
  if (typeof value === 'string') {
    if (
      /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/.test(value) ||
      /\bBearer\s+[A-Za-z0-9._~+\/-]{16,}/i.test(value) ||
      /\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b/.test(value) ||
      /\bgh[pousr]_[A-Za-z0-9]{20,}\b/.test(value)
    ) {
      throw new Error('SECRET_SHAPED_PAYLOAD_VALUE_REJECTED');
    }
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
