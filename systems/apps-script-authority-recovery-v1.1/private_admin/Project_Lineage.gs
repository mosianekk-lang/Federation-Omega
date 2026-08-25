/**
 * Exact Google project-lineage and effect-permit admission.
 *
 * These checks do not create provider authority. They require a fresh,
 * externally anchored provider receipt and a transaction-bound one-use effect
 * permit before the retained source mutator can run. Only fingerprints and
 * bounded replay state are persisted in Script Properties.
 */
const SOVARA_ADMIN_LINEAGE = Object.freeze({
  VERSION: '1.1.0',
  CANONICAL_PROJECT_ID: 'sov-hybrid-suite',
  CANONICAL_PROJECT_NUMBER: '257649435135',
  LEGACY_TRANSPORT_PROJECT_NUMBER: '516699068552',
  CLOUDOPS_OAUTH_CONSUMER_PROJECT_NUMBER: '516690968552',
  FOGAS_OAUTH_CONSUMER_PROJECT_NUMBER: '979287460558',
  PROVIDER_RECEIPT_ANCHOR_PROPERTY: 'SOVARA_PROVIDER_RECEIPT_ANCHOR_SHA256',
  EFFECT_PERMIT_ANCHOR_PROPERTY: 'SOVARA_EFFECT_PERMIT_ANCHOR_SHA256',
  EXPECTED_CONSUMER_PROJECT_PROPERTY: 'SOVARA_EXPECTED_OAUTH_CONSUMER_PROJECT_NUMBER',
  EXPECTED_PRINCIPAL_FINGERPRINT_PROPERTY: 'SOVARA_EXPECTED_ACTIVE_PRINCIPAL_SHA256',
  EFFECT_PERMIT_LEDGER_PREFIX: 'SOVARA_EFFECT_PERMIT_LEDGER_V1_',
  EFFECT_PERMIT_SHARDS: 16,
  MAX_PERMITS_PER_SHARD: 32,
  MAX_PROPERTY_CHARS: 7500,
  MAX_PROOF_AGE_MS: 10 * 60 * 1000
});

function SOVARA_ADMIN_assertProviderMutationPermit_(request, requiredAction) {
  if (!request || typeof request !== 'object' || Array.isArray(request)) {
    throw new Error('PROVIDER_MUTATION_REQUEST_REQUIRED');
  }
  const provider = request.providerReceipt;
  const permit = request.effectPermit;
  SOVARA_ADMIN_validateProviderReceipt_(provider, requiredAction);
  SOVARA_ADMIN_validateEffectPermit_(permit, requiredAction, request);
  return {
    providerReceiptSha256: provider.receiptSha256,
    effectPermitSha256: permit.permitSha256,
    transactionIdSha256: SOVARA_ADMIN_sha256_(String(request.transactionId || '')),
    mutationBindingSha256: SOVARA_ADMIN_mutationBindingSha256_(request, requiredAction),
    targetProjectId: provider.targetProjectId,
    targetProjectNumber: provider.targetProjectNumber,
    consumerProjectNumber: provider.consumerProjectNumber,
    activePrincipalSha256: provider.activePrincipalSha256,
    providerAuthorityInheritedFromTransport: false,
    effectPermitOneUseBound: true,
    admission: 'EXTERNALLY_ANCHORED_PROVIDER_AND_TRANSACTION_BOUND_EFFECT_PROOF_ACCEPTED'
  };
}

function SOVARA_ADMIN_validateProviderReceipt_(receipt, requiredAction) {
  if (!receipt || typeof receipt !== 'object' || Array.isArray(receipt)) {
    throw new Error('PROVIDER_RECEIPT_REQUIRED');
  }

  const properties = PropertiesService.getScriptProperties();
  const expectedConsumer = String(
    properties.getProperty(
      SOVARA_ADMIN_LINEAGE.EXPECTED_CONSUMER_PROJECT_PROPERTY
    ) || ''
  );
  const expectedPrincipalFingerprint = String(
    properties.getProperty(
      SOVARA_ADMIN_LINEAGE.EXPECTED_PRINCIPAL_FINGERPRINT_PROPERTY
    ) || ''
  ).toLowerCase();

  if (!/^\d{12}$/.test(expectedConsumer)) {
    throw new Error('EXPECTED_OAUTH_CONSUMER_PROJECT_NOT_CONFIGURED');
  }
  if (!/^[a-f0-9]{64}$/.test(expectedPrincipalFingerprint)) {
    throw new Error('EXPECTED_ACTIVE_PRINCIPAL_FINGERPRINT_NOT_CONFIGURED');
  }

  const checks = [
    receipt.targetProjectId === SOVARA_ADMIN_LINEAGE.CANONICAL_PROJECT_ID,
    String(receipt.targetProjectNumber || '') ===
      SOVARA_ADMIN_LINEAGE.CANONICAL_PROJECT_NUMBER,
    receipt.routeClass === 'APPS_SCRIPT_PROJECT_MANAGEMENT',
    String(receipt.consumerProjectNumber || '') === expectedConsumer,
    String(receipt.activePrincipalSha256 || '').toLowerCase() ===
      expectedPrincipalFingerprint,
    receipt.consumerIdentityVerified === true,
    receipt.consumerApiEnabled === true,
    receipt.appsScriptApiAccessGranted === true,
    receipt.tokenIssued === true,
    receipt.providerAuthenticated === true,
    receipt.targetAuthorityVerified === true,
    receipt.deploymentInventoryVerified === true,
    /^[a-f0-9]{64}$/.test(String(receipt.deploymentInventorySha256 || '')),
    Boolean(receipt.providerReadbackRef),
    String(receipt.action || '') === String(requiredAction || ''),
    receipt.transportAuthorityInherited === false
  ];
  if (!checks.every(function (value) { return value === true; })) {
    throw new Error('PROVIDER_RECEIPT_INCOMPLETE_OR_MISMATCHED');
  }
  SOVARA_ADMIN_assertFresh_(receipt.verifiedAt, 'PROVIDER_RECEIPT_STALE');

  const expected = SOVARA_ADMIN_hashRecord_(receipt, 'receiptSha256');
  if (!/^[a-f0-9]{64}$/.test(String(receipt.receiptSha256 || '')) ||
      expected !== String(receipt.receiptSha256)) {
    throw new Error('PROVIDER_RECEIPT_HASH_INVALID');
  }
  const anchor = String(
    properties.getProperty(
      SOVARA_ADMIN_LINEAGE.PROVIDER_RECEIPT_ANCHOR_PROPERTY
    ) || ''
  );
  if (!anchor || anchor !== receipt.receiptSha256) {
    throw new Error('PROVIDER_RECEIPT_EXTERNAL_ANCHOR_MISSING');
  }
  if (
    String(receipt.transportProjectNumber || '') ===
      SOVARA_ADMIN_LINEAGE.LEGACY_TRANSPORT_PROJECT_NUMBER &&
    receipt.transportAuthorityInherited !== false
  ) {
    throw new Error('LEGACY_TRANSPORT_AUTHORITY_INHERITANCE_REJECTED');
  }
}

function SOVARA_ADMIN_validateEffectPermit_(permit, requiredAction, request) {
  if (!permit || typeof permit !== 'object' || Array.isArray(permit)) {
    throw new Error('EFFECT_PERMIT_REQUIRED');
  }
  const requestTransactionId = String(request && request.transactionId || '');
  const checks = [
    permit.authorized === true,
    permit.oneUse === true,
    permit.rollbackRequired === true,
    permit.semanticReadbackRequired === true,
    String(permit.action || '') === String(requiredAction || ''),
    String(permit.targetProjectNumber || '') ===
      SOVARA_ADMIN_LINEAGE.CANONICAL_PROJECT_NUMBER,
    Boolean(permit.permitId),
    Boolean(permit.idempotencyKey),
    Boolean(permit.rollbackRef),
    Boolean(permit.semanticReadbackPlan),
    requestTransactionId.length > 0,
    String(permit.transactionId || '') === requestTransactionId,
    String(permit.idempotencyKey || '') === requestTransactionId,
    String(permit.mutationBindingSha256 || '') ===
      SOVARA_ADMIN_mutationBindingSha256_(request, requiredAction)
  ];
  if (!checks.every(function (value) { return value === true; })) {
    throw new Error('EFFECT_PERMIT_INCOMPLETE_OR_MISMATCHED');
  }
  SOVARA_ADMIN_assertFresh_(permit.issuedAt, 'EFFECT_PERMIT_STALE');
  const expiresAt = new Date(permit.expiresAt);
  if (isNaN(expiresAt.getTime()) || expiresAt.getTime() <= Date.now()) {
    throw new Error('EFFECT_PERMIT_EXPIRED');
  }

  const expected = SOVARA_ADMIN_hashRecord_(permit, 'permitSha256');
  if (!/^[a-f0-9]{64}$/.test(String(permit.permitSha256 || '')) ||
      expected !== String(permit.permitSha256)) {
    throw new Error('EFFECT_PERMIT_HASH_INVALID');
  }
  const anchor = String(
    PropertiesService.getScriptProperties().getProperty(
      SOVARA_ADMIN_LINEAGE.EFFECT_PERMIT_ANCHOR_PROPERTY
    ) || ''
  );
  if (!anchor || anchor !== permit.permitSha256) {
    throw new Error('EFFECT_PERMIT_EXTERNAL_ANCHOR_MISSING');
  }

}

function SOVARA_ADMIN_consumeEffectPermit_(permit, transactionId, options) {
  const expiresAt = new Date(permit && permit.expiresAt);
  if (isNaN(expiresAt.getTime()) || expiresAt.getTime() <= Date.now()) {
    throw new Error('EFFECT_PERMIT_EXPIRED');
  }
  const lockAlreadyHeld = Boolean(options && options.lockAlreadyHeld === true);
  SOVARA_ADMIN_claimEffectPermit_(
    permit,
    transactionId,
    expiresAt,
    lockAlreadyHeld
  );
  return {
    permitSha256: String(permit.permitSha256 || ''),
    transactionIdSha256: SOVARA_ADMIN_sha256_(String(transactionId || '')),
    consumedOrIdempotentlyReused: true,
    lockAlreadyHeld: lockAlreadyHeld
  };
}

function SOVARA_ADMIN_mutationBindingSha256_(request, requiredAction) {
  const binding = JSON.parse(JSON.stringify(request || {}));
  delete binding.signature;
  delete binding.providerReceipt;
  delete binding.effectPermit;
  delete binding.timestamp;
  delete binding.nonce;
  return SOVARA_ADMIN_sha256_(SOVARA_ADMIN_canonicalJson_({
    requiredAction: String(requiredAction || ''),
    mutation: binding
  }));
}

function SOVARA_ADMIN_claimEffectPermit_(
  permit,
  transactionId,
  expiresAt,
  lockAlreadyHeld
) {
  const lock = lockAlreadyHeld ? null : LockService.getScriptLock();
  if (lock) {
    lock.waitLock(30000);
  }
  try {
    const properties = PropertiesService.getScriptProperties();
    const permitSha = String(permit.permitSha256 || '');
    const transactionSha = SOVARA_ADMIN_sha256_(String(transactionId || ''));
    const shardId = permitSha.charAt(0);
    const propertyName = SOVARA_ADMIN_LINEAGE.EFFECT_PERMIT_LEDGER_PREFIX + shardId;
    const now = Date.now();
    const stored = properties.getProperty(propertyName);
    let entries = [];

    if (stored) {
      try {
        entries = JSON.parse(stored);
      } catch (error) {
        throw new Error('EFFECT_PERMIT_LEDGER_CORRUPT');
      }
      if (!Array.isArray(entries) || entries.some(function (entry) {
        return !Array.isArray(entry) || entry.length !== 3 ||
          !/^[a-f0-9]{64}$/.test(String(entry[0] || '')) ||
          !/^[a-f0-9]{64}$/.test(String(entry[1] || '')) ||
          !isFinite(Number(entry[2]));
      })) {
        throw new Error('EFFECT_PERMIT_LEDGER_CORRUPT');
      }
    }

    entries = entries.filter(function (entry) {
      return Number(entry[2]) > now;
    });
    const prior = entries.find(function (entry) {
      return entry[0] === permitSha;
    });
    if (prior) {
      if (prior[1] === transactionSha) {
        return; // Exact transaction retry is idempotent.
      }
      throw new Error('EFFECT_PERMIT_REPLAY_REJECTED');
    }

    entries.push([permitSha, transactionSha, expiresAt.getTime()]);
    entries.sort(function (left, right) { return Number(left[2]) - Number(right[2]); });
    while (entries.length > SOVARA_ADMIN_LINEAGE.MAX_PERMITS_PER_SHARD) {
      entries.shift();
    }

    let serialized = JSON.stringify(entries);
    while (
      serialized.length > SOVARA_ADMIN_LINEAGE.MAX_PROPERTY_CHARS &&
      entries.length > 1
    ) {
      entries.shift();
      serialized = JSON.stringify(entries);
    }
    if (serialized.length > SOVARA_ADMIN_LINEAGE.MAX_PROPERTY_CHARS) {
      throw new Error('EFFECT_PERMIT_LEDGER_CAPACITY_EXCEEDED');
    }
    properties.setProperty(propertyName, serialized);
  } finally {
    if (lock) {
      lock.releaseLock();
    }
  }
}

function SOVARA_ADMIN_assertFresh_(timestamp, code) {
  const value = new Date(timestamp);
  if (isNaN(value.getTime())) {
    throw new Error(code);
  }
  const age = Date.now() - value.getTime();
  if (age < -30000 || age > SOVARA_ADMIN_LINEAGE.MAX_PROOF_AGE_MS) {
    throw new Error(code);
  }
}

function SOVARA_ADMIN_lineageStatus() {
  return {
    status: 'SOURCE_CONFIGURED_PROVIDER_PROOF_REQUIRED',
    version: SOVARA_ADMIN_LINEAGE.VERSION,
    canonicalTarget: {
      projectId: SOVARA_ADMIN_LINEAGE.CANONICAL_PROJECT_ID,
      projectNumber: SOVARA_ADMIN_LINEAGE.CANONICAL_PROJECT_NUMBER
    },
    nonAuthorityLineages: [
      {
        projectNumber: SOVARA_ADMIN_LINEAGE.LEGACY_TRANSPORT_PROJECT_NUMBER,
        role: 'LEGACY_TRANSPORT_ONLY'
      },
      {
        projectNumber: SOVARA_ADMIN_LINEAGE.CLOUDOPS_OAUTH_CONSUMER_PROJECT_NUMBER,
        role: 'OAUTH_CONSUMER_ONLY'
      },
      {
        projectNumber: SOVARA_ADMIN_LINEAGE.FOGAS_OAUTH_CONSUMER_PROJECT_NUMBER,
        role: 'OAUTH_CONSUMER_ONLY'
      }
    ],
    providerAuthorityProven: false,
    providerMutationAuthorizedByStatus: false,
    truthBoundary: 'SOURCE_CONFIGURATION_IS_NOT_PROVIDER_PROOF'
  };
}
