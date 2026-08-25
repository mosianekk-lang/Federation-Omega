/**
 * Durable, bounded replay protection for the private signed admin plane.
 * State is sharded by nonce-hash prefix so no single Script Property grows
 * near its provider limit. Corrupt state fails closed instead of resetting.
 */
const SOVARA_ADMIN_SECURITY = Object.freeze({
  VERSION: '1.1.0',
  NONCE_LEDGER_PREFIX: 'SOVARA_ADMIN_NONCE_LEDGER_V2_',
  NONCE_SHARDS: 16,
  MAX_NONCES_PER_SHARD: 32,
  MAX_PROPERTY_CHARS: 7500,
  MAX_AGE_MS: 10 * 60 * 1000
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
  if (age > SOVARA_ADMIN_SECURITY.MAX_AGE_MS || age < -30000) {
    throw new Error('ADMIN_NONCE_TIMESTAMP_EXPIRED');
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const properties = PropertiesService.getScriptProperties();
    const now = Date.now();
    const nonceHash = SOVARA_ADMIN_sha256_(value);
    const shardId = nonceHash.charAt(0);
    const propertyName = SOVARA_ADMIN_SECURITY.NONCE_LEDGER_PREFIX + shardId;
    const stored = properties.getProperty(propertyName);
    let entries = [];

    if (stored) {
      try {
        entries = JSON.parse(stored);
      } catch (error) {
        throw new Error('ADMIN_NONCE_LEDGER_CORRUPT');
      }
      if (!Array.isArray(entries) || entries.some(function (entry) {
        return !Array.isArray(entry) || entry.length !== 2 ||
          !/^[a-f0-9]{64}$/.test(String(entry[0] || '')) ||
          !isFinite(Number(entry[1]));
      })) {
        throw new Error('ADMIN_NONCE_LEDGER_CORRUPT');
      }
    }

    entries = entries.filter(function (entry) {
      return Number(entry[1]) > now;
    });
    if (entries.some(function (entry) { return entry[0] === nonceHash; })) {
      throw new Error('ADMIN_NONCE_REPLAY_REJECTED');
    }

    entries.push([
      nonceHash,
      Math.max(now, issuedAt.getTime()) + SOVARA_ADMIN_SECURITY.MAX_AGE_MS
    ]);
    entries.sort(function (left, right) { return Number(left[1]) - Number(right[1]); });
    while (entries.length > SOVARA_ADMIN_SECURITY.MAX_NONCES_PER_SHARD) {
      entries.shift();
    }

    let serialized = JSON.stringify(entries);
    while (
      serialized.length > SOVARA_ADMIN_SECURITY.MAX_PROPERTY_CHARS &&
      entries.length > 1
    ) {
      entries.shift();
      serialized = JSON.stringify(entries);
    }
    if (serialized.length > SOVARA_ADMIN_SECURITY.MAX_PROPERTY_CHARS) {
      throw new Error('ADMIN_NONCE_LEDGER_CAPACITY_EXCEEDED');
    }
    properties.setProperty(propertyName, serialized);
  } finally {
    lock.releaseLock();
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
