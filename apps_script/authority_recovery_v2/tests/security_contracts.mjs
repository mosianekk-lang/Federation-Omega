import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const current = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(current, '..');

function canonical(value) {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return '[' + value.map(canonical).join(',') + ']';
  }
  return '{' + Object.keys(value).sort().map(
    (key) => JSON.stringify(key) + ':' + canonical(value[key])
  ).join(',') + '}';
}

function hmac(text, secret) {
  return crypto.createHmac('sha256', secret).update(text).digest('hex');
}

function sha256(text) {
  return crypto.createHash('sha256').update(String(text || '')).digest('hex');
}

function makeUtilities() {
  return {
    Charset: {UTF_8: 'UTF_8'},
    DigestAlgorithm: {SHA_256: 'SHA_256'},
    computeHmacSha256Signature(text, secret) {
      return Array.from(crypto.createHmac('sha256', secret).update(text).digest())
        .map((value) => value > 127 ? value - 256 : value);
    },
    computeDigest(_algorithm, text) {
      return Array.from(crypto.createHash('sha256').update(String(text)).digest())
        .map((value) => value > 127 ? value - 256 : value);
    },
    getUuid() {
      return '11111111-2222-4333-8444-555555555555';
    }
  };
}

function makeProperties(initial) {
  const values = new Map(Object.entries(initial || {}));
  return {
    getProperty(key) {
      return values.has(key) ? values.get(key) : null;
    },
    setProperty(key, value) {
      values.set(key, String(value));
      return this;
    },
    deleteProperty(key) {
      values.delete(key);
      return this;
    },
    dump() {
      return Object.fromEntries(values.entries());
    }
  };
}

function makeLock() {
  return {waitLock() {}, releaseLock() {}};
}

function loadFiles(files, extra) {
  const context = {
    console,
    Utilities: makeUtilities(),
    Date,
    JSON,
    Object,
    Array,
    String,
    Number,
    Boolean,
    Math,
    RegExp,
    Error,
    ...extra
  };
  vm.createContext(context);
  for (const file of files) {
    vm.runInContext(fs.readFileSync(file, 'utf8'), context, {filename: file});
  }
  return context;
}

const gatewaySecret = 'g'.repeat(48);
const gatewayProperties = makeProperties({SOVARA_GATEWAY_HMAC_SECRET: gatewaySecret});
const gateway = loadFiles(
  [path.join(root, 'public_gateway', 'Gateway_Security.gs')],
  {
    PropertiesService: {getScriptProperties: () => gatewayProperties},
    LockService: {getScriptLock: () => makeLock()}
  }
);

function gatewayRequest(overrides = {}) {
  const request = {
    version: '2',
    requestId: 'REQ-SECURITY-000001',
    action: 'STATUS',
    targetProjectNumber: '257649435135',
    timestamp: new Date().toISOString(),
    nonce: 'nonce-security-contract-000001',
    payload: {challenge: 'public-safe'},
    ...overrides
  };
  request.signature = hmac(canonical(request), gatewaySecret);
  return request;
}

const accepted = gateway.SOVARA_GATEWAY_verifySignedEnvelope_(gatewayRequest());
assert.equal(accepted.authentication, 'HMAC_SHA256_TIMESTAMP_NONCE_VERIFIED');
assert.equal(accepted.providerAuthorityGranted, false);
assert.equal(accepted.providerMutationAuthorized, false);

assert.throws(
  () => gateway.SOVARA_GATEWAY_verifySignedEnvelope_(gatewayRequest({
    requestId: 'REQ-SECURITY-000002',
    nonce: 'nonce-security-contract-000002',
    signature: '0'.repeat(64)
  })),
  /AUTHENTICATION_FAILED/
);

const stale = gatewayRequest({
  requestId: 'REQ-SECURITY-000003',
  nonce: 'nonce-security-contract-000003',
  timestamp: new Date(Date.now() - 20 * 60 * 1000).toISOString()
});
stale.signature = hmac(canonical({...stale, signature: undefined}), gatewaySecret);
const staleUnsigned = {...stale};
delete staleUnsigned.signature;
stale.signature = hmac(canonical(staleUnsigned), gatewaySecret);
assert.throws(
  () => gateway.SOVARA_GATEWAY_verifySignedEnvelope_(stale),
  /EXPIRED/
);

const wrongTarget = gatewayRequest({
  requestId: 'REQ-SECURITY-000004',
  nonce: 'nonce-security-contract-000004',
  targetProjectNumber: '516699068552'
});
const wrongUnsigned = {...wrongTarget};
delete wrongUnsigned.signature;
wrongTarget.signature = hmac(canonical(wrongUnsigned), gatewaySecret);
assert.throws(
  () => gateway.SOVARA_GATEWAY_verifySignedEnvelope_(wrongTarget),
  /CANONICAL_TARGET_MISMATCH/
);

const replay = gatewayRequest({
  requestId: 'REQ-SECURITY-000005',
  nonce: 'nonce-security-contract-000005'
});
gateway.SOVARA_GATEWAY_verifySignedEnvelope_(replay);
assert.throws(
  () => gateway.SOVARA_GATEWAY_verifySignedEnvelope_(replay),
  /REPLAY_REJECTED/
);

const secretPayload = gatewayRequest({
  requestId: 'REQ-SECURITY-000006',
  nonce: 'nonce-security-contract-000006',
  payload: {access_token: 'not-a-real-value'}
});
const secretUnsigned = {...secretPayload};
delete secretUnsigned.signature;
secretPayload.signature = hmac(canonical(secretUnsigned), gatewaySecret);
assert.throws(
  () => gateway.SOVARA_GATEWAY_verifySignedEnvelope_(secretPayload),
  /SECRET_BEARING_PAYLOAD_FIELD_REJECTED/
);

const adminProperties = makeProperties({});
const admin = loadFiles(
  [
    path.join(root, 'private_admin', 'Admin_Security.gs'),
    path.join(root, 'private_admin', 'Project_Lineage.gs')
  ],
  {
    PropertiesService: {getScriptProperties: () => adminProperties},
    LockService: {getScriptLock: () => makeLock()},
    UrlFetchApp: {fetch() { throw new Error('not expected'); }}
  }
);

function hashRecord(record, field) {
  const copy = JSON.parse(JSON.stringify(record));
  delete copy[field];
  return sha256(canonical(copy));
}

function providerReceipt(overrides = {}) {
  const now = Date.now();
  const value = {
    schema: 'SOVARA_GOOGLE_PROVIDER_RECEIPT_V2',
    targetProjectId: 'sov-hybrid-suite',
    targetProjectNumber: '257649435135',
    oauthConsumerProjectNumber: '257649435135',
    routeClass: 'APPS_SCRIPT_ADMIN_COMPOSITE',
    consumerIdentityVerified: true,
    consumerApiEnabled: true,
    appsScriptApiAccessGranted: true,
    standardCloudProjectShared: true,
    scriptsRunApiEnabled: true,
    scriptsRunDeploymentVerified: true,
    projectContentInventoryVerified: true,
    deploymentInventoryVerified: true,
    tokenIssued: true,
    providerAuthenticated: true,
    targetAuthorityVerified: true,
    activePrincipalFingerprint: 'principal-sha256-reference',
    action: 'CODE_APPLY',
    transactionId: 'TXN-SECURITY-0001',
    requestSha256: 'a'.repeat(64),
    transportAuthorityInherited: false,
    providerMutationPerformed: false,
    externalEvidenceRef: 'evidence://provider/receipt-1',
    verifiedAt: new Date(now - 1000).toISOString(),
    expiresAt: new Date(now + 5 * 60 * 1000).toISOString(),
    ...overrides
  };
  value.receiptSha256 = hashRecord(value, 'receiptSha256');
  return value;
}

function effectPermit(provider, overrides = {}) {
  const now = Date.now();
  const value = {
    schema: 'SOVARA_EFFECT_PERMIT_V2',
    permitId: 'PERMIT-SECURITY-0001',
    authorized: true,
    oneUse: true,
    action: 'CODE_APPLY',
    transactionId: 'TXN-SECURITY-0001',
    targetProjectNumber: '257649435135',
    requestSha256: provider.requestSha256,
    providerReceiptSha256: provider.receiptSha256,
    expectedBeforeHash: 'b'.repeat(64),
    expectedAfterHash: 'c'.repeat(64),
    rollbackRef: 'backup://pre-update',
    semanticReadbackPlan: 'verify source hash and deployment state',
    externalEvidenceRef: 'evidence://permit/1',
    issuedAt: new Date(now - 1000).toISOString(),
    expiresAt: new Date(now + 5 * 60 * 1000).toISOString(),
    ...overrides
  };
  value.permitSha256 = hashRecord(value, 'permitSha256');
  return value;
}

const provider = providerReceipt();
admin.SOVARA_ADMIN_validateProviderReceipt_(
  provider,
  'CODE_APPLY',
  'TXN-SECURITY-0001',
  'a'.repeat(64)
);
const permit = effectPermit(provider);
admin.SOVARA_ADMIN_validateEffectPermit_(
  permit,
  provider,
  'CODE_APPLY',
  'TXN-SECURITY-0001',
  'a'.repeat(64)
);
const consumed = admin.SOVARA_ADMIN_claimEffectPermit_(permit, 'TXN-SECURITY-0001');
assert.equal(consumed.state, 'CONSUMED');
assert.throws(
  () => admin.SOVARA_ADMIN_claimEffectPermit_(permit, 'TXN-SECURITY-0001'),
  /PERMIT_REPLAY_REJECTED/
);

const tamperedPermit = effectPermit(provider, {expectedAfterHash: 'd'.repeat(64)});
tamperedPermit.expectedAfterHash = 'e'.repeat(64);
assert.throws(
  () => admin.SOVARA_ADMIN_validateEffectPermit_(
    tamperedPermit,
    provider,
    'CODE_APPLY',
    'TXN-SECURITY-0001',
    'a'.repeat(64)
  ),
  /PERMIT_HASH_INVALID/
);

console.log('APPS_SCRIPT_AUTHORITY_RECOVERY_V2_SECURITY_CONTRACTS_PASS');
