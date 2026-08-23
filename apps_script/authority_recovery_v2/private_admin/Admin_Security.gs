/**
 * Durable replay and one-use permit controls for the private admin plane.
 * Script Properties store only hashes and bounded state, never secret values.
 */
const SOVARA_ADMIN_SECURITY = Object.freeze({
  NONCE_LEDGER_PROPERTY: 'SOVARA_ADMIN_NONCE_LEDGER_V2',
  PERMIT_LEDGER_PROPERTY: 'SOVARA_ADMIN_PERMIT_LEDGER_V2',
  MAX_NONCES: 1024,
  MAX_PERMITS: 512,
  MAX_AGE_MS: 10 * 60 * 1000,
  MAX_FUTURE_SKEW_MS: 30 * 1000
});

function SOVARA_ADMIN_claimNonce_(nonce, timestamp) {
  const value = String(nonce || '');
  if (!/^[A-Za-z0-9_.:-]{16,160}$/.test(value)) {
    throw new Error('ADMIN_NONCE_INVALID');
  }
  const issuedAt = timestamp instanceof Date ? timestamp : new Date(timestamp);
  if (isNaN(issuedAt.getTime())) {
    throw new Error('ADMIN_NONCE_TIMESTAMP_INVALID');
  }
  const age = Date.now() - issuedAt.getTime();
  if (
    age > SOVARA_ADMIN_SECURITY.MAX_AGE_MS ||
    age < -SOVARA_ADMIN_SECURITY.MAX_FUTURE_SKEW_MS
  ) {
    throw new Error('ADMIN_NONCE_TIMESTAMP_STALE');
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const properties = PropertiesService.getScriptProperties();
    const now = Date.now();
    const nonceHash = SOVARA_ADMIN_sha256_(value);
    const ledger = SOVARA_ADMIN_readLedger_(
      properties,
      SOVARA_ADMIN_SECURITY.NONCE_LEDGER_PROPERTY
    );
    SOVARA_ADMIN_pruneLedger_(ledger, now);
    if (Object.prototype.hasOwnProperty.call(ledger, nonceHash)) {
      throw new Error('ADMIN_NONCE_REPLAY_REJECTED');
    }

    ledger[nonceHash] = {
      expiresAt: Math.max(now, issuedAt.getTime()) +
        SOVARA_ADMIN_SECURITY.MAX_AGE_MS,
      state: 'USED'
    };
    SOVARA_ADMIN_boundLedger_(ledger, SOVARA_ADMIN_SECURITY.MAX_NONCES);
    properties.setProperty(
      SOVARA_ADMIN_SECURITY.NONCE_LEDGER_PROPERTY,
      JSON.stringify(ledger)
    );
  } finally {
    lock.releaseLock();
  }
}

function SOVARA_ADMIN_claimEffectPermit_(permit, transactionId) {
  if (!permit || typeof permit !== 'object' || Array.isArray(permit)) {
    throw new Error('EFFECT_PERMIT_REQUIRED');
  }
  const permitId = String(permit.permitId || '');
  const permitSha256 = String(permit.permitSha256 || '');
  if (!/^[A-Za-z0-9_.:-]{12,160}$/.test(permitId)) {
    throw new Error('EFFECT_PERMIT_ID_INVALID');
  }
  if (!/^[a-f0-9]{64}$/.test(permitSha256)) {
    throw new Error('EFFECT_PERMIT_HASH_INVALID');
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const properties = PropertiesService.getScriptProperties();
    const now = Date.now();
    const key = SOVARA_ADMIN_sha256_(permitId);
    const ledger = SOVARA_ADMIN_readLedger_(
      properties,
      SOVARA_ADMIN_SECURITY.PERMIT_LEDGER_PROPERTY
    );
    SOVARA_ADMIN_pruneLedger_(ledger, now);
    if (Object.prototype.hasOwnProperty.call(ledger, key)) {
      throw new Error('EFFECT_PERMIT_REPLAY_REJECTED');
    }
    const expiresAt = new Date(permit.expiresAt).getTime();
    ledger[key] = {
      expiresAt: isNaN(expiresAt) ?
        now + SOVARA_ADMIN_SECURITY.MAX_AGE_MS : expiresAt,
      state: 'CONSUMED',
      transactionSha256: SOVARA_ADMIN_sha256_(String(transactionId || '')),
      permitSha256: permitSha256
    };
    SOVARA_ADMIN_boundLedger_(ledger, SOVARA_ADMIN_SECURITY.MAX_PERMITS);
    properties.setProperty(
      SOVARA_ADMIN_SECURITY.PERMIT_LEDGER_PROPERTY,
      JSON.stringify(ledger)
    );
  } finally {
    lock.releaseLock();
  }
}

function SOVARA_ADMIN_readLedger_(properties, key) {
  const stored = properties.getProperty(key);
  if (!stored) {
    return {};
  }
  try {
    const parsed = JSON.parse(stored);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch (error) {
    return {};
  }
}

function SOVARA_ADMIN_pruneLedger_(ledger, now) {
  Object.keys(ledger).forEach(function (key) {
    const item = ledger[key];
    const expiry = typeof item === 'object'
      ? Number(item.expiresAt || 0)
      : Number(item || 0);
    if (expiry <= now) {
      delete ledger[key];
    }
  });
}

function SOVARA_ADMIN_boundLedger_(ledger, maximum) {
  const ordered = Object.keys(ledger)
    .map(function (key) {
      const item = ledger[key];
      const expiry = typeof item === 'object'
        ? Number(item.expiresAt || 0)
        : Number(item || 0);
      return [key, expiry];
    })
    .sort(function (left, right) { return left[1] - right[1]; });
  while (ordered.length > maximum) {
    const removed = ordered.shift();
    delete ledger[removed[0]];
  }
}

function SOVARA_ADMIN_sha256_(text) {
  return SOVARA_ADMIN_hex_(
    Utilities.computeDigest(
      Utilities.DigestAlgorithm.SHA_256,
      String(text || ''),
      Utilities.Charset.UTF_8
    )
  );
}

function SOVARA_ADMIN_hex_(bytes) {
  return bytes.map(function (byte) {
    const value = byte < 0 ? byte + 256 : byte;
    return value.toString(16).padStart(2, '0');
  }).join('');
}

function SOVARA_ADMIN_canonicalJson_(value) {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return '[' + value.map(SOVARA_ADMIN_canonicalJson_).join(',') + ']';
  }
  return '{' + Object.keys(value).sort().map(function (key) {
    return JSON.stringify(key) + ':' +
      SOVARA_ADMIN_canonicalJson_(value[key]);
  }).join(',') + '}';
}

function SOVARA_ADMIN_hashRecord_(record, hashField) {
  const copy = JSON.parse(JSON.stringify(record || {}));
  delete copy[hashField];
  return SOVARA_ADMIN_sha256_(SOVARA_ADMIN_canonicalJson_(copy));
}

function SOVARA_ADMIN_mutationIntent_(request) {
  const action = String(request.action || '').trim().toUpperCase();
  const intent = {
    transactionId: String(request.transactionId || ''),
    action: action,
    file: request.file || null,
    fileName: request.fileName || null,
    files: request.files || null,
    backupFileId: request.backupFileId || null,
    allowProtectedMutation: request.allowProtectedMutation === true,
    promoteDeployment: request.promoteDeployment === true,
    deploymentId: String(request.deploymentId || ''),
    description: String(request.description || '')
  };
  return intent;
}

function SOVARA_ADMIN_mutationIntentSha256_(request) {
  return SOVARA_ADMIN_sha256_(
    SOVARA_ADMIN_canonicalJson_(SOVARA_ADMIN_mutationIntent_(request))
  );
}
