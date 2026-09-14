/**
 * Exact Google project-lineage and effect-permit admission — v2.
 *
 * The admin project does not trust same-project Script Properties as an
 * independent provider or owner authority anchor. Before a mutation, it sends
 * only hashes and stable evidence references to a fixed HTTPS verifier and
 * requires an exact challenge-bound verification response.
 */
const SOVARA_ADMIN_LINEAGE = Object.freeze({
  VERSION: '2.0.0',
  CANONICAL_PROJECT_ID: 'sov-hybrid-suite',
  CANONICAL_PROJECT_NUMBER: '257649435135',
  LEGACY_TRANSPORT_PROJECT_NUMBER: '516699068552',
  CLOUDOPS_OAUTH_CONSUMER_PROJECT_NUMBER: '516690968552',
  FOGAS_OAUTH_CONSUMER_PROJECT_NUMBER: '979287460558',
  VERIFIER_URL_PROPERTY: 'SOVARA_ADMISSION_VERIFIER_URL',
  VERIFIER_HOST_PROPERTY: 'SOVARA_ADMISSION_VERIFIER_HOST',
  VERIFIER_IDENTITY_PROPERTY: 'SOVARA_ADMISSION_VERIFIER_IDENTITY',
  MAX_PROOF_AGE_MS: 10 * 60 * 1000,
  MAX_FUTURE_SKEW_MS: 30 * 1000
});

function SOVARA_ADMIN_assertProviderMutationPermit_(request, requiredAction) {
  if (!request || typeof request !== 'object' || Array.isArray(request)) {
    throw new Error('PROVIDER_MUTATION_REQUEST_REQUIRED');
  }
  const provider = request.providerReceipt;
  const permit = request.effectPermit;
  const transactionId = String(request.transactionId || '');
  const requestSha256 = SOVARA_ADMIN_mutationIntentSha256_(request);

  SOVARA_ADMIN_validateProviderReceipt_(
    provider,
    requiredAction,
    transactionId,
    requestSha256
  );
  SOVARA_ADMIN_validateEffectPermit_(
    permit,
    provider,
    requiredAction,
    transactionId,
    requestSha256
  );
  const external = SOVARA_ADMIN_verifyExternalAdmission_(
    provider,
    permit,
    requiredAction,
    transactionId,
    requestSha256
  );

  return Object.freeze({
    transactionId: transactionId,
    requestSha256: requestSha256,
    providerReceiptSha256: provider.receiptSha256,
    effectPermitSha256: permit.permitSha256,
    expectedBeforeHash: permit.expectedBeforeHash,
    expectedAfterHash: permit.expectedAfterHash,
    targetProjectId: provider.targetProjectId,
    targetProjectNumber: provider.targetProjectNumber,
    oauthConsumerProjectNumber: provider.oauthConsumerProjectNumber,
    activePrincipalFingerprint: provider.activePrincipalFingerprint,
    externalVerificationId: external.verificationId,
    externalVerifierIdentity: external.verifierIdentity,
    providerAuthorityInheritedFromTransport: false,
    admission: 'EXTERNAL_VERIFIER_AND_EXACT_PERMIT_ACCEPTED'
  });
}

function SOVARA_ADMIN_validateProviderReceipt_(
  receipt,
  requiredAction,
  transactionId,
  requestSha256
) {
  if (!receipt || typeof receipt !== 'object' || Array.isArray(receipt)) {
    throw new Error('PROVIDER_RECEIPT_REQUIRED');
  }
  const checks = [
    receipt.schema === 'SOVARA_GOOGLE_PROVIDER_RECEIPT_V2',
    receipt.targetProjectId === SOVARA_ADMIN_LINEAGE.CANONICAL_PROJECT_ID,
    String(receipt.targetProjectNumber || '') ===
      SOVARA_ADMIN_LINEAGE.CANONICAL_PROJECT_NUMBER,
    String(receipt.oauthConsumerProjectNumber || '') ===
      SOVARA_ADMIN_LINEAGE.CANONICAL_PROJECT_NUMBER,
    receipt.routeClass === 'APPS_SCRIPT_ADMIN_COMPOSITE',
    receipt.consumerIdentityVerified === true,
    receipt.consumerApiEnabled === true,
    receipt.appsScriptApiAccessGranted === true,
    receipt.standardCloudProjectShared === true,
    receipt.scriptsRunApiEnabled === true,
    receipt.scriptsRunDeploymentVerified === true,
    receipt.projectContentInventoryVerified === true,
    receipt.deploymentInventoryVerified === true,
    receipt.tokenIssued === true,
    receipt.providerAuthenticated === true,
    receipt.targetAuthorityVerified === true,
    Boolean(receipt.activePrincipalFingerprint),
    String(receipt.action || '') === String(requiredAction || ''),
    String(receipt.transactionId || '') === String(transactionId || ''),
    String(receipt.requestSha256 || '') === String(requestSha256 || ''),
    receipt.transportAuthorityInherited === false,
    receipt.providerMutationPerformed === false,
    Boolean(receipt.externalEvidenceRef)
  ];
  if (!checks.every(function (value) { return value === true; })) {
    throw new Error('PROVIDER_RECEIPT_INCOMPLETE_OR_MISMATCHED');
  }
  SOVARA_ADMIN_assertFreshWindow_(
    receipt.verifiedAt,
    receipt.expiresAt,
    'PROVIDER_RECEIPT_STALE'
  );
  const expected = SOVARA_ADMIN_hashRecord_(receipt, 'receiptSha256');
  if (
    !/^[a-f0-9]{64}$/.test(String(receipt.receiptSha256 || '')) ||
    expected !== String(receipt.receiptSha256)
  ) {
    throw new Error('PROVIDER_RECEIPT_HASH_INVALID');
  }
}

function SOVARA_ADMIN_validateEffectPermit_(
  permit,
  provider,
  requiredAction,
  transactionId,
  requestSha256
) {
  if (!permit || typeof permit !== 'object' || Array.isArray(permit)) {
    throw new Error('EFFECT_PERMIT_REQUIRED');
  }
  const checks = [
    permit.schema === 'SOVARA_EFFECT_PERMIT_V2',
    permit.authorized === true,
    permit.oneUse === true,
    String(permit.action || '') === String(requiredAction || ''),
    String(permit.transactionId || '') === String(transactionId || ''),
    String(permit.targetProjectNumber || '') ===
      SOVARA_ADMIN_LINEAGE.CANONICAL_PROJECT_NUMBER,
    String(permit.requestSha256 || '') === String(requestSha256 || ''),
    String(permit.providerReceiptSha256 || '') ===
      String(provider.receiptSha256 || ''),
    /^[a-f0-9]{64}$/.test(String(permit.expectedBeforeHash || '')),
    /^[a-f0-9]{64}$/.test(String(permit.expectedAfterHash || '')),
    Boolean(permit.permitId),
    Boolean(permit.rollbackRef),
    Boolean(permit.semanticReadbackPlan),
    Boolean(permit.externalEvidenceRef)
  ];
  if (!checks.every(function (value) { return value === true; })) {
    throw new Error('EFFECT_PERMIT_INCOMPLETE_OR_MISMATCHED');
  }
  SOVARA_ADMIN_assertFreshWindow_(
    permit.issuedAt,
    permit.expiresAt,
    'EFFECT_PERMIT_STALE_OR_EXPIRED'
  );
  const expected = SOVARA_ADMIN_hashRecord_(permit, 'permitSha256');
  if (
    !/^[a-f0-9]{64}$/.test(String(permit.permitSha256 || '')) ||
    expected !== String(permit.permitSha256)
  ) {
    throw new Error('EFFECT_PERMIT_HASH_INVALID');
  }
}

function SOVARA_ADMIN_verifyExternalAdmission_(
  provider,
  permit,
  requiredAction,
  transactionId,
  requestSha256
) {
  const properties = PropertiesService.getScriptProperties();
  const url = String(
    properties.getProperty(SOVARA_ADMIN_LINEAGE.VERIFIER_URL_PROPERTY) || ''
  );
  const expectedHost = String(
    properties.getProperty(SOVARA_ADMIN_LINEAGE.VERIFIER_HOST_PROPERTY) || ''
  ).toLowerCase();
  const expectedIdentity = String(
    properties.getProperty(SOVARA_ADMIN_LINEAGE.VERIFIER_IDENTITY_PROPERTY) || ''
  );
  SOVARA_ADMIN_assertPinnedHttpsEndpoint_(url, expectedHost);
  if (!expectedIdentity) {
    throw new Error('EXTERNAL_VERIFIER_IDENTITY_NOT_CONFIGURED');
  }

  const challenge = Utilities.getUuid() + '-' + Date.now();
  const body = {
    schema: 'SOVARA_EXTERNAL_ADMISSION_CHALLENGE_V2',
    challenge: challenge,
    action: String(requiredAction || ''),
    transactionId: String(transactionId || ''),
    targetProjectNumber: SOVARA_ADMIN_LINEAGE.CANONICAL_PROJECT_NUMBER,
    requestSha256: requestSha256,
    providerReceiptSha256: provider.receiptSha256,
    providerEvidenceRef: provider.externalEvidenceRef,
    effectPermitSha256: permit.permitSha256,
    effectPermitRef: permit.externalEvidenceRef,
    expectedBeforeHash: permit.expectedBeforeHash,
    expectedAfterHash: permit.expectedAfterHash
  };
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(body),
    followRedirects: false,
    muteHttpExceptions: true
  });
  const status = response.getResponseCode();
  let result = {};
  try {
    result = JSON.parse(response.getContentText() || '{}');
  } catch (error) {
    throw new Error('EXTERNAL_VERIFIER_RESPONSE_INVALID');
  }
  const checks = [
    status >= 200 && status < 300,
    result.schema === 'SOVARA_EXTERNAL_ADMISSION_RESULT_V2',
    result.verified === true,
    result.providerReceiptVerified === true,
    result.effectPermitVerified === true,
    result.providerMutationPerformed === false,
    String(result.challenge || '') === challenge,
    String(result.action || '') === String(requiredAction || ''),
    String(result.transactionId || '') === String(transactionId || ''),
    String(result.requestSha256 || '') === requestSha256,
    String(result.providerReceiptSha256 || '') === provider.receiptSha256,
    String(result.effectPermitSha256 || '') === permit.permitSha256,
    String(result.expectedBeforeHash || '') === permit.expectedBeforeHash,
    String(result.expectedAfterHash || '') === permit.expectedAfterHash,
    Boolean(result.verificationId),
    String(result.verifierIdentity || '') === expectedIdentity
  ];
  if (!checks.every(function (value) { return value === true; })) {
    throw new Error('EXTERNAL_ADMISSION_VERIFICATION_FAILED');
  }
  SOVARA_ADMIN_assertFreshWindow_(
    result.verifiedAt,
    result.expiresAt,
    'EXTERNAL_VERIFIER_RESULT_STALE'
  );
  return result;
}

function SOVARA_ADMIN_verifyExternalPostEffect_(request, result) {
  if (request.promoteDeployment !== true) {
    return {
      status: 'NOT_REQUIRED_FOR_SOURCE_ONLY_MUTATION',
      verified: true
    };
  }
  const properties = PropertiesService.getScriptProperties();
  const url = String(
    properties.getProperty(SOVARA_ADMIN_LINEAGE.VERIFIER_URL_PROPERTY) || ''
  );
  const expectedHost = String(
    properties.getProperty(SOVARA_ADMIN_LINEAGE.VERIFIER_HOST_PROPERTY) || ''
  ).toLowerCase();
  const expectedIdentity = String(
    properties.getProperty(SOVARA_ADMIN_LINEAGE.VERIFIER_IDENTITY_PROPERTY) || ''
  );
  SOVARA_ADMIN_assertPinnedHttpsEndpoint_(url, expectedHost);
  if (!expectedIdentity) {
    throw new Error('EXTERNAL_VERIFIER_IDENTITY_NOT_CONFIGURED');
  }

  const challenge = Utilities.getUuid() + '-' + Date.now();
  const effectAction = String(
    request.effectPermit && request.effectPermit.action || ''
  );
  const payload = {
    schema: 'SOVARA_POST_EFFECT_CHALLENGE_V2',
    challenge: challenge,
    transactionId: String(request.transactionId || ''),
    targetProjectNumber: SOVARA_ADMIN_LINEAGE.CANONICAL_PROJECT_NUMBER,
    action: effectAction,
    requestSha256: SOVARA_ADMIN_mutationIntentSha256_(request),
    providerReceiptSha256: String(
      request.providerReceipt && request.providerReceipt.receiptSha256 || ''
    ),
    effectPermitSha256: String(
      request.effectPermit && request.effectPermit.permitSha256 || ''
    ),
    expectedSourceHash: String(result.afterHash || ''),
    versionNumber: result.version ? result.version.versionNumber : null,
    deploymentId: result.deployment ? result.deployment.deploymentId : null,
    semanticReadbackPlan: String(
      request.effectPermit && request.effectPermit.semanticReadbackPlan || ''
    )
  };
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    followRedirects: false,
    muteHttpExceptions: true
  });
  const status = response.getResponseCode();
  let verified = {};
  try {
    verified = JSON.parse(response.getContentText() || '{}');
  } catch (error) {
    throw new Error('POST_EFFECT_VERIFIER_RESPONSE_INVALID');
  }
  const checks = [
    status >= 200 && status < 300,
    verified.schema === 'SOVARA_POST_EFFECT_RESULT_V2',
    verified.verified === true,
    String(verified.challenge || '') === challenge,
    String(verified.transactionId || '') === String(request.transactionId || ''),
    String(verified.action || '') === effectAction,
    String(verified.requestSha256 || '') === payload.requestSha256,
    String(verified.providerReceiptSha256 || '') ===
      payload.providerReceiptSha256,
    String(verified.effectPermitSha256 || '') === payload.effectPermitSha256,
    String(verified.observedSourceHash || '') === String(result.afterHash || ''),
    String(verified.verifierIdentity || '') === expectedIdentity,
    Boolean(verified.verificationId),
    verified.providerSemanticReadbackVerified === true,
    verified.providerMutationPerformedByVerifier === false
  ];
  if (!checks.every(function (value) { return value === true; })) {
    throw new Error('POST_EFFECT_SEMANTIC_VERIFICATION_FAILED');
  }
  SOVARA_ADMIN_assertFreshWindow_(
    verified.verifiedAt,
    verified.expiresAt,
    'POST_EFFECT_VERIFIER_RESULT_STALE'
  );
  return verified;
}

function SOVARA_ADMIN_assertPinnedHttpsEndpoint_(url, expectedHost) {
  if (!url || !expectedHost || url.indexOf('@') >= 0 || url.indexOf('#') >= 0) {
    throw new Error('EXTERNAL_VERIFIER_ENDPOINT_NOT_CONFIGURED');
  }
  const match = /^https:\/\/([A-Za-z0-9.-]+)(?::[0-9]+)?(?:\/|$)/.exec(url);
  if (!match || String(match[1]).toLowerCase() !== expectedHost) {
    throw new Error('EXTERNAL_VERIFIER_HOST_MISMATCH');
  }
}

function SOVARA_ADMIN_assertFreshWindow_(issuedAt, expiresAt, code) {
  const issued = new Date(issuedAt);
  const expires = new Date(expiresAt);
  if (isNaN(issued.getTime()) || isNaN(expires.getTime())) {
    throw new Error(code);
  }
  const now = Date.now();
  const age = now - issued.getTime();
  if (
    age < -SOVARA_ADMIN_LINEAGE.MAX_FUTURE_SKEW_MS ||
    age > SOVARA_ADMIN_LINEAGE.MAX_PROOF_AGE_MS ||
    expires.getTime() <= now
  ) {
    throw new Error(code);
  }
}

function SOVARA_ADMIN_lineageStatus() {
  const properties = PropertiesService.getScriptProperties();
  return {
    status: 'SOURCE_CONFIGURED_EXTERNAL_PROVIDER_PROOF_REQUIRED',
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
    externalVerifierConfigured: Boolean(
      properties.getProperty(SOVARA_ADMIN_LINEAGE.VERIFIER_URL_PROPERTY) &&
      properties.getProperty(SOVARA_ADMIN_LINEAGE.VERIFIER_HOST_PROPERTY) &&
      properties.getProperty(SOVARA_ADMIN_LINEAGE.VERIFIER_IDENTITY_PROPERTY)
    ),
    providerAuthorityProven: false,
    providerMutationAuthorizedByStatus: false,
    sameProjectPropertyIsIndependentAuthorityAnchor: false
  };
}
