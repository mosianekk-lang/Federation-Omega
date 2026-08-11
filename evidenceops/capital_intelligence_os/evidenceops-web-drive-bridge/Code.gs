const EO = Object.freeze({
  VERSION: '1.0.0',
  MAX_BYTES: 25 * 1024 * 1024,
  MAX_BATCH: 10,
  PROP_API_KEY: 'EO_BRIDGE_API_KEY',
  PROP_ALLOWED_DOMAINS: 'EO_ALLOWED_DOMAINS',
  PROP_MANIFEST_SHEET_ID: 'EO_MANIFEST_SHEET_ID',
  MANIFEST_TAB: 'WEB_INGEST_MANIFEST'
});

function doGet() {
  return jsonResponse_({
    ok: true,
    service: 'EvidenceOps Web-to-Drive Bridge',
    version: EO.VERSION,
    status: 'ready'
  }, 200);
}

function doPost(e) {
  const started = new Date();
  try {
    const body = parseJsonBody_(e);
    authenticate_(body.apiKey);
    const jobs = Array.isArray(body.jobs) ? body.jobs : [body];
    if (!jobs.length || jobs.length > EO.MAX_BATCH) {
      throw new BridgeError('INVALID_BATCH', `Batch must contain 1-${EO.MAX_BATCH} jobs.`, 400);
    }

    const lock = LockService.getScriptLock();
    lock.waitLock(30000);
    try {
      const results = jobs.map((job, index) => ingestOne_(job, index));
      return jsonResponse_({
        ok: results.every(r => r.ok),
        service: 'EvidenceOps Web-to-Drive Bridge',
        version: EO.VERSION,
        startedAt: started.toISOString(),
        completedAt: new Date().toISOString(),
        results
      }, results.every(r => r.ok) ? 200 : 207);
    } finally {
      lock.releaseLock();
    }
  } catch (err) {
    const safe = normaliseError_(err);
    return jsonResponse_({ ok: false, error: safe, at: new Date().toISOString() }, safe.httpStatus || 500);
  }
}

function ingestOne_(job, index) {
  const runId = Utilities.getUuid();
  const retrievedAt = new Date();
  try {
    validateJob_(job);
    const sourceUrl = normaliseAndValidateUrl_(job.url);
    const folder = DriveApp.getFolderById(job.folderId);
    const response = fetchWithRedirectControl_(sourceUrl, 0);
    const status = response.getResponseCode();
    if (status < 200 || status >= 300) {
      throw new BridgeError('HTTP_FETCH_FAILED', `Source returned HTTP ${status}.`, 422);
    }

    const headers = lowerCaseHeaders_(response.getAllHeaders());
    const blob = response.getBlob();
    const bytes = blob.getBytes();
    if (!bytes.length) throw new BridgeError('EMPTY_FILE', 'Retrieved file is empty.', 422);
    if (bytes.length > EO.MAX_BYTES) {
      throw new BridgeError('FILE_TOO_LARGE', `File exceeds ${EO.MAX_BYTES} bytes.`, 413);
    }

    const contentType = String(headers['content-type'] || blob.getContentType() || '').split(';')[0].trim().toLowerCase();
    const allowedTypes = job.allowedMimeTypes || ['application/pdf'];
    if (!allowedTypes.includes(contentType)) {
      throw new BridgeError('MIME_REJECTED', `MIME type ${contentType || 'unknown'} is not allowed.`, 415);
    }

    const sha256 = sha256Hex_(bytes);
    if (job.expectedSha256 && sha256.toLowerCase() !== String(job.expectedSha256).toLowerCase()) {
      throw new BridgeError('HASH_MISMATCH', 'Retrieved SHA-256 does not match expected value.', 409);
    }

    const duplicate = findDuplicateByHash_(sha256, job.folderId);
    if (duplicate && job.deduplicate !== false) {
      const receipt = buildReceipt_({ runId, index, sourceUrl, job, retrievedAt, status, headers, bytes, contentType, sha256, duplicate, outcome: 'DUPLICATE_LINKED' });
      appendManifest_(receipt);
      return { ok: true, outcome: 'DUPLICATE_LINKED', runId, sha256, existingFileId: duplicate.fileId, receipt };
    }

    const filename = safeFilename_(job.filename || inferFilename_(sourceUrl, headers, contentType));
    blob.setName(filename).setContentType(contentType);
    const file = folder.createFile(blob);
    file.setDescription(`EvidenceOps source URL: ${sourceUrl}\nSHA-256: ${sha256}\nRetrieved: ${retrievedAt.toISOString()}\nBridge: ${EO.VERSION}`);

    const receipt = buildReceipt_({ runId, index, sourceUrl, job, retrievedAt, status, headers, bytes, contentType, sha256, file, outcome: 'IMPORTED' });
    const sidecar = folder.createFile(`${filename}.evidenceops.json`, JSON.stringify(receipt, null, 2), MimeType.PLAIN_TEXT);
    appendManifest_(receipt);

    return {
      ok: true,
      outcome: 'IMPORTED',
      runId,
      fileId: file.getId(),
      fileUrl: file.getUrl(),
      sidecarFileId: sidecar.getId(),
      sha256,
      sizeBytes: bytes.length,
      contentType,
      receipt
    };
  } catch (err) {
    const safe = normaliseError_(err);
    const receipt = {
      runId,
      batchIndex: index,
      outcome: 'FAILED',
      sourceUrl: job && job.url ? String(job.url) : null,
      retrievedAt: retrievedAt.toISOString(),
      error: safe
    };
    try { appendManifest_(receipt); } catch (_) {}
    return { ok: false, runId, error: safe, receipt };
  }
}

function validateJob_(job) {
  if (!job || typeof job !== 'object') throw new BridgeError('INVALID_JOB', 'Job must be an object.', 400);
  if (!job.url) throw new BridgeError('MISSING_URL', 'url is required.', 400);
  if (!job.folderId) throw new BridgeError('MISSING_FOLDER', 'folderId is required.', 400);
}

function authenticate_(provided) {
  const expected = PropertiesService.getScriptProperties().getProperty(EO.PROP_API_KEY);
  if (!expected) throw new BridgeError('NOT_CONFIGURED', 'Bridge API key is not configured.', 503);
  if (!provided || !constantTimeEqual_(String(provided), expected)) {
    throw new BridgeError('UNAUTHORISED', 'Invalid API key.', 401);
  }
}

function normaliseAndValidateUrl_(raw) {
  const url = new URL(String(raw));
  if (url.protocol !== 'https:') throw new BridgeError('HTTPS_REQUIRED', 'Only HTTPS URLs are allowed.', 400);
  if (url.username || url.password) throw new BridgeError('CREDENTIALS_REJECTED', 'Credentials in URLs are not allowed.', 400);
  const host = url.hostname.toLowerCase();
  if (isPrivateHost_(host)) throw new BridgeError('PRIVATE_HOST_REJECTED', 'Private or loopback hosts are not allowed.', 403);
  const allowed = getAllowedDomains_();
  if (!allowed.some(domain => host === domain || host.endsWith(`.${domain}`))) {
    throw new BridgeError('DOMAIN_NOT_ALLOWED', `Domain ${host} is not allowlisted.`, 403);
  }
  return url.toString();
}

function fetchWithRedirectControl_(url, depth) {
  if (depth > 5) throw new BridgeError('TOO_MANY_REDIRECTS', 'Redirect limit exceeded.', 422);
  const response = UrlFetchApp.fetch(url, {
    method: 'get',
    followRedirects: false,
    muteHttpExceptions: true,
    validateHttpsCertificates: true,
    headers: { 'User-Agent': `EvidenceOpsBridge/${EO.VERSION}` }
  });
  const code = response.getResponseCode();
  if ([301, 302, 303, 307, 308].includes(code)) {
    const location = lowerCaseHeaders_(response.getAllHeaders())['location'];
    if (!location) throw new BridgeError('REDIRECT_WITHOUT_LOCATION', 'Redirect response had no Location header.', 422);
    const next = new URL(String(location), url).toString();
    return fetchWithRedirectControl_(normaliseAndValidateUrl_(next), depth + 1);
  }
  return response;
}

function buildReceipt_(ctx) {
  return {
    receiptVersion: '1.0',
    bridgeVersion: EO.VERSION,
    runId: ctx.runId,
    batchIndex: ctx.index,
    outcome: ctx.outcome,
    sourceUrl: ctx.sourceUrl,
    sourceDomain: new URL(ctx.sourceUrl).hostname,
    requestedFilename: ctx.job.filename || null,
    destinationFolderId: ctx.job.folderId,
    destinationFileId: ctx.file ? ctx.file.getId() : (ctx.duplicate ? ctx.duplicate.fileId : null),
    destinationFileUrl: ctx.file ? ctx.file.getUrl() : null,
    retrievedAt: ctx.retrievedAt.toISOString(),
    httpStatus: ctx.status,
    contentType: ctx.contentType,
    sizeBytes: ctx.bytes.length,
    sha256: ctx.sha256,
    expectedSha256: ctx.job.expectedSha256 || null,
    hashStatus: ctx.job.expectedSha256 ? 'HASH_MATCH_VERIFIED' : 'HASH_RECOMPUTED',
    etag: ctx.headers['etag'] || null,
    lastModified: ctx.headers['last-modified'] || null,
    sourceLabel: ctx.job.sourceLabel || null,
    evidenceLane: ctx.job.evidenceLane || null,
    notes: ctx.job.notes || null
  };
}

function appendManifest_(receipt) {
  const sheetId = PropertiesService.getScriptProperties().getProperty(EO.PROP_MANIFEST_SHEET_ID);
  if (!sheetId) return;
  const ss = SpreadsheetApp.openById(sheetId);
  let sh = ss.getSheetByName(EO.MANIFEST_TAB);
  if (!sh) {
    sh = ss.insertSheet(EO.MANIFEST_TAB);
    sh.appendRow(['Run ID','Outcome','Source URL','Domain','Retrieved At','HTTP','MIME','Bytes','SHA-256','Hash Status','Folder ID','File ID','Lane','Label','Error Code','Error Message']);
    sh.setFrozenRows(1);
  }
  sh.appendRow([
    receipt.runId || '', receipt.outcome || '', receipt.sourceUrl || '', receipt.sourceDomain || '',
    receipt.retrievedAt || '', receipt.httpStatus || '', receipt.contentType || '', receipt.sizeBytes || '',
    receipt.sha256 || '', receipt.hashStatus || '', receipt.destinationFolderId || '', receipt.destinationFileId || '',
    receipt.evidenceLane || '', receipt.sourceLabel || '', receipt.error && receipt.error.code || '', receipt.error && receipt.error.message || ''
  ]);
}

function findDuplicateByHash_(sha256, folderId) {
  const sheetId = PropertiesService.getScriptProperties().getProperty(EO.PROP_MANIFEST_SHEET_ID);
  if (!sheetId) return null;
  const sh = SpreadsheetApp.openById(sheetId).getSheetByName(EO.MANIFEST_TAB);
  if (!sh || sh.getLastRow() < 2) return null;
  const values = sh.getRange(2, 1, sh.getLastRow() - 1, 16).getValues();
  for (let i = values.length - 1; i >= 0; i--) {
    if (String(values[i][8]).toLowerCase() === sha256.toLowerCase() && String(values[i][10]) === String(folderId) && values[i][11]) {
      return { fileId: String(values[i][11]) };
    }
  }
  return null;
}

function getAllowedDomains_() {
  const raw = PropertiesService.getScriptProperties().getProperty(EO.PROP_ALLOWED_DOMAINS) || '';
  const domains = raw.split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
  if (!domains.length) throw new BridgeError('NO_ALLOWLIST', 'No allowed domains are configured.', 503);
  return domains;
}

function inferFilename_(url, headers, contentType) {
  const cd = String(headers['content-disposition'] || '');
  const m = cd.match(/filename\*?=(?:UTF-8''|["']?)([^"';]+)/i);
  if (m) return decodeURIComponent(m[1].trim());
  const pathName = new URL(url).pathname.split('/').filter(Boolean).pop();
  if (pathName && pathName.includes('.')) return decodeURIComponent(pathName);
  return `source-${Utilities.formatDate(new Date(), 'UTC', 'yyyyMMdd-HHmmss')}${contentType === 'application/pdf' ? '.pdf' : ''}`;
}

function safeFilename_(name) {
  const cleaned = String(name).replace(/[\\/:*?"<>|\u0000-\u001F]/g, '_').replace(/\s+/g, ' ').trim();
  if (!cleaned) throw new BridgeError('INVALID_FILENAME', 'Filename is empty after sanitisation.', 400);
  return cleaned.slice(0, 180);
}

function sha256Hex_(bytes) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes)
    .map(b => (b < 0 ? b + 256 : b).toString(16).padStart(2, '0')).join('');
}

function parseJsonBody_(e) {
  if (!e || !e.postData || !e.postData.contents) throw new BridgeError('EMPTY_BODY', 'JSON request body is required.', 400);
  try { return JSON.parse(e.postData.contents); }
  catch (_) { throw new BridgeError('INVALID_JSON', 'Request body must be valid JSON.', 400); }
}

function jsonResponse_(obj, status) {
  return ContentService.createTextOutput(JSON.stringify({ ...obj, httpStatus: status }))
    .setMimeType(ContentService.MimeType.JSON);
}

function lowerCaseHeaders_(headers) {
  const out = {};
  Object.keys(headers || {}).forEach(k => out[String(k).toLowerCase()] = Array.isArray(headers[k]) ? headers[k].join(', ') : String(headers[k]));
  return out;
}

function isPrivateHost_(host) {
  return host === 'localhost' || host.endsWith('.local') || /^127\./.test(host) || /^10\./.test(host) || /^192\.168\./.test(host) || /^169\.254\./.test(host) || /^172\.(1[6-9]|2\d|3[0-1])\./.test(host) || host === '::1';
}

function constantTimeEqual_(a, b) {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return result === 0;
}

function normaliseError_(err) {
  if (err instanceof BridgeError) return { code: err.code, message: err.message, httpStatus: err.httpStatus };
  return { code: 'INTERNAL_ERROR', message: err && err.message ? err.message : String(err), httpStatus: 500 };
}

class BridgeError extends Error {
  constructor(code, message, httpStatus) {
    super(message);
    this.code = code;
    this.httpStatus = httpStatus || 400;
  }
}

function configureBridge(apiKey, allowedDomainsCsv, manifestSpreadsheetId) {
  if (!apiKey || String(apiKey).length < 24) throw new Error('API key must be at least 24 characters.');
  const props = PropertiesService.getScriptProperties();
  props.setProperty(EO.PROP_API_KEY, String(apiKey));
  props.setProperty(EO.PROP_ALLOWED_DOMAINS, String(allowedDomainsCsv || 'gov.za,dhet.gov.za,che.ac.za,justice.gov.za,saflii.org'));
  if (manifestSpreadsheetId) props.setProperty(EO.PROP_MANIFEST_SHEET_ID, String(manifestSpreadsheetId));
  return { configured: true, allowedDomains: getAllowedDomains_(), manifestSpreadsheetId: manifestSpreadsheetId || null };
}
