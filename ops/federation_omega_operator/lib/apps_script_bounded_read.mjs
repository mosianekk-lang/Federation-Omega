import { createHash } from 'node:crypto';

export const READ_APPS_SCRIPT_PROJECT_BOUNDED = 'READ_APPS_SCRIPT_PROJECT_BOUNDED';
export const STRATEGIC_TARGET_SCRIPT_ID = '1z4wkTnk3TF3NG6T-1f5PsSl08-3SFUQw4STcYwsiPptdGSVrfSE-4r_R';
export const REQUIRED_STRATEGIC_FUNCTIONS = Object.freeze([
  'processMetaExecutorQueueV2',
  'runMetaExecutorV2Now',
  'gasSchedulerRunV3',
  'gasSchedulerInstallV3',
  'fcosBoundedFunctionDiscoveryV1',
  'cfbePr618MonitorV1',
  'gns3QueueTask_',
  'gns3ProcessQueue_',
  'STRATEGIC_FUSE_SECONDARY_BRAIN',
]);

const sha256 = (value) => createHash('sha256').update(value).digest('hex');
const FN_RE = /\bfunction\s+([A-Za-z_$][\w$]*)\s*\(/g;
const noEffect = Object.freeze({
  rawSourcePersisted: false,
  sourceReturned: false,
  providerEffect: false,
  mutationAttempted: false,
  secretValuesRecorded: false,
});

export function validateExactStrategicScriptId(value) {
  if (value !== STRATEGIC_TARGET_SCRIPT_ID) {
    const err = new Error(`scriptId must equal ${STRATEGIC_TARGET_SCRIPT_ID}`);
    err.code = 'TARGET_MISMATCH';
    throw err;
  }
  return value;
}

export function boundedManifestFromContent(content, { scriptId = STRATEGIC_TARGET_SCRIPT_ID } = {}) {
  validateExactStrategicScriptId(scriptId);
  if (!content || !Array.isArray(content.files)) {
    const err = new Error('Apps Script content.files is required');
    err.code = 'INVALID_PROVIDER_SHAPE';
    throw err;
  }
  const foundFunctions = new Set();
  const files = content.files.map((file) => {
    const name = String(file.name || '');
    const type = String(file.type || '');
    const source = typeof file.source === 'string' ? file.source : '';
    const functions = [];
    for (const match of source.matchAll(FN_RE)) {
      functions.push(match[1]);
      foundFunctions.add(match[1]);
    }
    return {
      name,
      type,
      sourceSha256: sha256(Buffer.from(source, 'utf8')),
      functionCount: functions.length,
    };
  }).sort((a, b) => Buffer.compare(
    Buffer.from(`${a.name}\u0000${a.type}`, 'utf8'),
    Buffer.from(`${b.name}\u0000${b.type}`, 'utf8'),
  ));
  const functionCount = files.reduce((sum, file) => sum + file.functionCount, 0);
  const requiredFunctionsPresent = Object.fromEntries(
    REQUIRED_STRATEGIC_FUNCTIONS.map((name) => [name, foundFunctions.has(name)]),
  );
  const projectDigest = sha256(Buffer.from(JSON.stringify({ scriptId, files }), 'utf8'));
  return Object.freeze({
    ok: true,
    status: 'APPS_SCRIPT_PROJECT_BOUNDED_READ_VERIFIED',
    scriptId,
    fileCount: files.length,
    functionCount,
    files,
    projectDigest,
    requiredFunctionsPresent,
    ...noEffect,
  });
}

export async function readAppsScriptProjectBounded(api, { scriptId = STRATEGIC_TARGET_SCRIPT_ID } = {}) {
  validateExactStrategicScriptId(scriptId);
  if (typeof api !== 'function') {
    const err = new Error('provider api function is required');
    err.code = 'ADAPTER_UNAVAILABLE';
    throw err;
  }
  const encoded = encodeURIComponent(scriptId);
  const response = await api(`https://script.googleapis.com/v1/projects/${encoded}/content`, {}, [200]);
  const body = response?.body ?? response;
  return boundedManifestFromContent(body, { scriptId });
}

function providerHttpStatus(error) {
  const direct = Number(error?.providerHttpStatus || error?.status || 0);
  if (direct >= 100 && direct <= 599) return direct;
  const match = String(error?.message || '').match(/^provider\s+(\d{3})(?::|\b)/i);
  return match ? Number(match[1]) : null;
}

export async function executeAppsScriptBoundedReadAction(adapter, payload = {}) {
  const scriptId = payload?.scriptId || STRATEGIC_TARGET_SCRIPT_ID;
  try {
    validateExactStrategicScriptId(scriptId);
  } catch (error) {
    return {
      httpStatus: 400,
      body: {
        ok: false,
        status: 'APPS_SCRIPT_PROJECT_BOUNDED_READ_REJECTED',
        reason: error?.code || 'TARGET_MISMATCH',
        scriptId: null,
        ...noEffect,
      },
    };
  }

  if (!adapter || typeof adapter.api !== 'function') {
    return {
      httpStatus: 503,
      body: {
        ok: false,
        status: 'APPS_SCRIPT_PROJECT_BOUNDED_READ_UNAVAILABLE',
        reason: 'ADAPTER_UNAVAILABLE',
        scriptId,
        providerHttpStatus: null,
        ...noEffect,
      },
    };
  }

  try {
    const body = await readAppsScriptProjectBounded(adapter.api.bind(adapter), { scriptId });
    return { httpStatus: 200, body };
  } catch (error) {
    const status = providerHttpStatus(error);
    return {
      httpStatus: status && status >= 400 && status < 500 ? 502 : 503,
      body: {
        ok: false,
        status: 'APPS_SCRIPT_PROJECT_BOUNDED_READ_FAILED',
        reason: status ? `PROVIDER_HTTP_${status}` : (error?.code || 'PROVIDER_READ_FAILED'),
        scriptId,
        providerHttpStatus: status,
        ...noEffect,
      },
    };
  }
}
