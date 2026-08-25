/**
 * One public router, minimum scope, read-only actions only.
 * No Cloud IAM/API/source/deployment mutation exists in this project.
 */
function doGet() {
  return SOVARA_GATEWAY_json_({
    ok: true,
    service: 'SOVARA Signed Minimum-Scope Gateway',
    version: SOVARA_GATEWAY_SECURITY.VERSION,
    status: 'LIVE_MINIMAL_INGRESS',
    providerAuthorityGranted: false,
    providerMutationAuthorized: false,
    checkedAt: new Date().toISOString()
  });
}

function doPost(event) {
  try {
    const request = SOVARA_GATEWAY_parseRequest_(event);
    if (!request.timestamp || !request.nonce || !request.signature) {
      throw new Error('SIGNED_ENVELOPE_FIELDS_REQUIRED');
    }
    const authentication = SOVARA_GATEWAY_verifySignedEnvelope_(request);
    const result = SOVARA_GATEWAY_dispatchReadOnly_(authentication, request);
    return SOVARA_GATEWAY_json_({
      ok: true,
      authentication: authentication,
      result: result,
      completedAt: new Date().toISOString()
    });
  } catch (error) {
    return SOVARA_GATEWAY_json_({
      ok: false,
      code: 'GATEWAY_REQUEST_REJECTED',
      error: String(error && error.message ? error.message : error),
      providerAuthorityGranted: false,
      providerMutationAuthorized: false,
      completedAt: new Date().toISOString()
    });
  }
}

function SOVARA_GATEWAY_dispatchReadOnly_(authentication, request) {
  switch (authentication.action) {
    case 'STATUS':
      return {
        status: 'DONE',
        targetProjectNumber: authentication.targetProjectNumber,
        truthBoundary: 'SIGNED_GATEWAY_LIVENESS_ONLY',
        providerAuthorityGranted: false,
        providerMutationAuthorized: false
      };
    case 'CHALLENGE':
      return {
        status: 'DONE',
        challengeSha256: SOVARA_GATEWAY_sha256_(
          String(request.payload && request.payload.challenge || '')
        ),
        providerAuthorityGranted: false,
        providerMutationAuthorized: false
      };
    default:
      throw new Error('ACTION_NOT_ALLOWLISTED');
  }
}

function SOVARA_GATEWAY_parseRequest_(event) {
  const raw = event && event.postData && event.postData.contents
    ? event.postData.contents
    : '';
  if (!raw || raw.length > 100000) {
    throw new Error('REQUEST_BODY_INVALID');
  }
  const parsed = JSON.parse(raw);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('REQUEST_BODY_INVALID');
  }
  return parsed;
}

function SOVARA_GATEWAY_json_(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
