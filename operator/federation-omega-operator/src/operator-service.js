import {
  publicInventoryError,
  readWifInventory,
} from "./wif-inventory.js";

export const OPERATOR_VERSION = "fo-operator-v1-image-cloudbuild-wif-v1";
export const ALLOWED_ACTIONS = Object.freeze([
  "STATUS",
  "READ_CLOUD_RUN_SERVICE",
  "VERIFY_ARCHITRON_HEALTH",
  "DEPLOY_SOLUTION5_LOCKED",
  "READ_BUILD",
  "READ_WIF_INVENTORY",
]);

const PROJECT_PATTERN = /^(?:[a-z][a-z0-9-]{4,28}[a-z0-9]|[0-9]{6,20})$/;
const REGION_PATTERN = /^[a-z][a-z0-9-]{1,31}$/;
const SERVICE_PATTERN = /^[a-z][a-z0-9-]{0,61}[a-z0-9]$/;
const BUILD_PATTERN = /^[A-Za-z0-9-]{8,128}$/;
const DRIVE_ID_PATTERN = /^[A-Za-z0-9_-]{10,160}$/;
const SHA256_PATTERN = /^[a-f0-9]{64}$/;
const IDEMPOTENCY_PATTERN = /^[A-Za-z0-9._:-]{8,180}$/;

export class OperatorError extends Error {
  constructor(code, httpStatus = 400) {
    super(code);
    this.name = "OperatorError";
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

function compact(record) {
  return Object.fromEntries(
    Object.entries(record).filter(([, value]) => value !== undefined),
  );
}

function text(value, maximum = 512) {
  return typeof value === "string" ? value.slice(0, maximum) : undefined;
}

function safeHttpsUrl(value, { cloudRunOnly = false } = {}) {
  if (typeof value !== "string") return undefined;
  try {
    const parsed = new URL(value);
    if (
      parsed.protocol !== "https:" ||
      parsed.username ||
      parsed.password ||
      (cloudRunOnly && !parsed.hostname.endsWith(".run.app"))
    ) {
      return undefined;
    }
    return `${parsed.origin}${parsed.pathname}`;
  } catch {
    return undefined;
  }
}

function validateSegment(value, pattern, code) {
  if (typeof value !== "string" || !pattern.test(value)) {
    throw new OperatorError(code, 400);
  }
  return value;
}

function responseData(response) {
  return response && typeof response === "object" && "data" in response
    ? response.data
    : response;
}

function dependencyError(error) {
  if (error instanceof OperatorError) return error;
  const status = Number(error?.response?.status ?? error?.status ?? 0);
  const code =
    status === 401
      ? "DEPENDENCY_UNAUTHENTICATED"
      : status === 403
        ? "DEPENDENCY_PERMISSION_DENIED"
        : status === 404
          ? "DEPENDENCY_NOT_FOUND"
          : status === 429
            ? "DEPENDENCY_RATE_LIMITED"
            : error?.name === "AbortError" || status === 408 || status === 504
              ? "DEPENDENCY_TIMEOUT"
              : "DEPENDENCY_REQUEST_FAILED";
  const publicStatus =
    code === "DEPENDENCY_TIMEOUT"
      ? 504
      : [401, 403, 404, 429].includes(status)
        ? status
        : 502;
  return new OperatorError(code, publicStatus);
}

async function googleGet(googleRequest, url, timeout = 5_000) {
  try {
    const data = responseData(
      await googleRequest({ method: "GET", url, timeout }),
    );
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      throw new OperatorError("DEPENDENCY_SCHEMA_INVALID", 502);
    }
    return data;
  } catch (error) {
    throw dependencyError(error);
  }
}

function sanitizeTrafficStatus(item) {
  return compact({
    type: text(item?.type, 32),
    revision: text(item?.revision, 256),
    percent: Number.isFinite(item?.percent) ? item.percent : undefined,
    tag: text(item?.tag, 64),
    uri: safeHttpsUrl(item?.uri, { cloudRunOnly: true }),
  });
}

export function sanitizeCloudRunService(service) {
  return compact({
    name: text(service?.name),
    uid: text(service?.uid, 128),
    generation: text(service?.generation, 64),
    createTime: text(service?.createTime, 64),
    updateTime: text(service?.updateTime, 64),
    uri: safeHttpsUrl(service?.uri, { cloudRunOnly: true }),
    latestReadyRevision: text(service?.latestReadyRevision, 256),
    latestCreatedRevision: text(service?.latestCreatedRevision, 256),
    trafficStatuses: Array.isArray(service?.trafficStatuses)
      ? service.trafficStatuses.slice(0, 25).map(sanitizeTrafficStatus)
      : [],
  });
}

function sanitizeHealth(value) {
  return compact({
    ok: typeof value?.ok === "boolean" ? value.ok : undefined,
    healthOk: typeof value?.healthOk === "boolean" ? value.healthOk : undefined,
    staleSignal:
      typeof value?.staleSignal === "boolean" ? value.staleSignal : undefined,
    repairQueued:
      typeof value?.repairQueued === "boolean" ? value.repairQueued : undefined,
    decisionAction: text(value?.decisionAction, 64),
    noGmail: typeof value?.noGmail === "boolean" ? value.noGmail : undefined,
    status: text(value?.status, 64),
    version: text(value?.version, 128),
    checkedAt: text(value?.checkedAt, 64),
  });
}

function sanitizeBuildSource(source) {
  if (!source || typeof source !== "object") return undefined;
  const storage = source.storageSource
    ? compact({
        bucket: text(source.storageSource.bucket, 256),
        object: text(source.storageSource.object, 1024),
        generation: text(source.storageSource.generation, 64),
      })
    : undefined;
  const repo = source.repoSource
    ? compact({
        projectId: text(source.repoSource.projectId, 64),
        repoName: text(source.repoSource.repoName, 256),
        branchName: text(source.repoSource.branchName, 256),
        tagName: text(source.repoSource.tagName, 256),
        commitSha: text(source.repoSource.commitSha, 64),
        dir: text(source.repoSource.dir, 512),
      })
    : undefined;
  const git = source.gitSource
    ? compact({
        url: safeHttpsUrl(source.gitSource.url),
        revision: text(source.gitSource.revision, 256),
        dir: text(source.gitSource.dir, 512),
      })
    : undefined;
  const connected = source.connectedRepository
    ? compact({
        repository: text(source.connectedRepository.repository, 512),
        revision: text(source.connectedRepository.revision, 256),
        dir: text(source.connectedRepository.dir, 512),
      })
    : undefined;
  return compact({
    storageSource: storage,
    repoSource: repo,
    gitSource: git,
    connectedRepository: connected,
  });
}

function sanitizeBuild(build) {
  const sourceProvenance = build?.sourceProvenance
    ? compact({
        resolvedStorageSource: sanitizeBuildSource({
          storageSource: build.sourceProvenance.resolvedStorageSource,
        })?.storageSource,
        resolvedRepoSource: sanitizeBuildSource({
          repoSource: build.sourceProvenance.resolvedRepoSource,
        })?.repoSource,
        resolvedGitSource: sanitizeBuildSource({
          gitSource: build.sourceProvenance.resolvedGitSource,
        })?.gitSource,
      })
    : undefined;
  return compact({
    id: text(build?.id, 128),
    name: text(build?.name),
    projectId: text(build?.projectId, 64),
    status: text(build?.status, 32),
    statusDetail: text(build?.statusDetail, 512),
    createTime: text(build?.createTime, 64),
    startTime: text(build?.startTime, 64),
    finishTime: text(build?.finishTime, 64),
    timeout: text(build?.timeout, 64),
    logUrl: safeHttpsUrl(build?.logUrl),
    serviceAccount: text(build?.serviceAccount, 512),
    source: sanitizeBuildSource(build?.source),
    sourceProvenance,
    images: Array.isArray(build?.results?.images)
      ? build.results.images.slice(0, 50).map((image) =>
          compact({
            name: text(image?.name, 1024),
            digest: text(image?.digest, 256),
          }),
        )
      : [],
  });
}

function sanitizeDeployment(result) {
  return compact({
    ok: typeof result?.ok === "boolean" ? result.ok : undefined,
    status: text(result?.status, 64),
    buildId: text(result?.buildId, 128),
    buildName: text(result?.buildName),
    project: text(result?.project, 64),
    region: text(result?.region, 64),
    service: text(result?.service, 64),
    serviceUrl: safeHttpsUrl(result?.serviceUrl, { cloudRunOnly: true }),
    image: text(result?.image, 1024),
    rollbackRef: text(result?.rollbackRef, 512),
    idempotencyKey: text(result?.idempotencyKey, 180),
    asynchronous:
      typeof result?.asynchronous === "boolean" ? result.asynchronous : undefined,
  });
}

function fixedProject(payload, projectId) {
  const requested = payload?.project;
  if (requested !== undefined && requested !== projectId) {
    throw new OperatorError("PROJECT_NOT_ALLOWED", 403);
  }
  return projectId;
}

function fixedRegion(payload, region, allowedRegions) {
  const requested = payload?.region ?? region;
  validateSegment(requested, REGION_PATTERN, "REGION_INVALID");
  if (!allowedRegions.has(requested)) {
    throw new OperatorError("REGION_NOT_ALLOWED", 403);
  }
  return requested;
}

function validateDeployment(payload, projectId, region, allowedRegions) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new OperatorError("DEPLOYMENT_PAYLOAD_REQUIRED");
  }
  if (payload.approvalKey !== "APPROVED") {
    throw new OperatorError("DEPLOYMENT_APPROVAL_REQUIRED", 403);
  }
  return {
    project: fixedProject(payload, projectId),
    region: fixedRegion(payload, region, allowedRegions),
    service: validateSegment(payload.service, SERVICE_PATTERN, "SERVICE_INVALID"),
    artifactDriveId: validateSegment(
      payload.artifactDriveId,
      DRIVE_ID_PATTERN,
      "ARTIFACT_DRIVE_ID_INVALID",
    ),
    artifactName: text(payload.artifactName, 256),
    artifactSha256: validateSegment(
      payload.artifactSha256,
      SHA256_PATTERN,
      "ARTIFACT_SHA256_INVALID",
    ),
    serviceAccount: text(payload.serviceAccount, 512),
    deploymentMode: text(payload.deploymentMode, 64),
    activationMode: text(payload.activationMode, 64),
    idempotencyKey: validateSegment(
      payload.idempotencyKey,
      IDEMPOTENCY_PATTERN,
      "IDEMPOTENCY_KEY_INVALID",
    ),
  };
}

export function publicOperatorError(error) {
  const inventory = publicInventoryError(error);
  if (inventory.code !== "INTERNAL_ERROR") return inventory;
  if (error instanceof OperatorError) {
    return { code: error.code, httpStatus: error.httpStatus };
  }
  return { code: "INTERNAL_ERROR", httpStatus: 500 };
}

export function createOperatorService({
  projectId,
  region,
  targetService = "architron9",
  googleRequest,
  publicFetch = globalThis.fetch,
  deploymentAdapter,
  allowedRegions = [region],
  now = () => new Date().toISOString(),
}) {
  validateSegment(projectId, PROJECT_PATTERN, "PROJECT_ID_INVALID");
  validateSegment(region, REGION_PATTERN, "REGION_INVALID");
  validateSegment(targetService, SERVICE_PATTERN, "TARGET_SERVICE_INVALID");
  if (typeof googleRequest !== "function") {
    throw new OperatorError("GOOGLE_REQUEST_REQUIRED", 500);
  }
  if (typeof publicFetch !== "function") {
    throw new OperatorError("PUBLIC_FETCH_REQUIRED", 500);
  }
  const regionSet = new Set(allowedRegions);
  regionSet.add(region);

  async function readCloudRun(payload = {}) {
    const project = fixedProject(payload, projectId);
    const selectedRegion = fixedRegion(payload, region, regionSet);
    const service = validateSegment(
      payload.service ?? targetService,
      SERVICE_PATTERN,
      "SERVICE_INVALID",
    );
    const url =
      `https://run.googleapis.com/v2/projects/${encodeURIComponent(project)}` +
      `/locations/${encodeURIComponent(selectedRegion)}/services/${encodeURIComponent(service)}`;
    return sanitizeCloudRunService(await googleGet(googleRequest, url));
  }

  async function verifyTarget() {
    const service = await readCloudRun({ service: targetService, region });
    if (!service.uri) throw new OperatorError("TARGET_URI_UNSAFE", 502);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5_000);
    let raw;
    try {
      const response = await publicFetch(`${service.uri}/health`, {
        method: "GET",
        signal: controller.signal,
        headers: { accept: "application/json" },
      });
      if (!response.ok) throw new OperatorError("TARGET_HEALTH_HTTP_FAILED", 502);
      raw = await response.json();
    } catch (error) {
      throw dependencyError(error);
    } finally {
      clearTimeout(timer);
    }
    const health = sanitizeHealth(raw);
    const ok =
      health.ok === true &&
      health.healthOk === true &&
      health.staleSignal === false &&
      health.repairQueued === false &&
      health.decisionAction === "NONE" &&
      health.noGmail === true;
    return {
      ok,
      status: ok ? "TARGET_HEALTH_VERIFIED" : "TARGET_HEALTH_FAILED",
      targetService,
      service,
      health,
      checkedAt: now(),
    };
  }

  async function readBuild(payload = {}) {
    const project = fixedProject(payload, projectId);
    const selectedRegion = fixedRegion(payload, region, regionSet);
    const buildId = validateSegment(payload.buildId, BUILD_PATTERN, "BUILD_ID_INVALID");
    const url =
      `https://cloudbuild.googleapis.com/v1/projects/${encodeURIComponent(project)}` +
      `/locations/${encodeURIComponent(selectedRegion)}/builds/${encodeURIComponent(buildId)}`;
    const build = sanitizeBuild(await googleGet(googleRequest, url, 10_000));
    const expected = payload.expectedStatus;
    return compact({
      ok: expected === undefined ? true : build.status === expected,
      status: "BUILD_READ",
      expectedStatus: text(expected, 32),
      matchesExpectedStatus:
        expected === undefined ? undefined : build.status === expected,
      build,
      checkedAt: now(),
    });
  }

  function health() {
    return {
      ok: true,
      status: "OPERATOR_READY",
      service: "federation-omega-operator",
      version: OPERATOR_VERSION,
      targetService,
      noGmail: true,
      checkedAt: now(),
    };
  }

  function contract() {
    return {
      ok: true,
      service: "federation-omega-operator",
      version: OPERATOR_VERSION,
      targetService,
      allowedActions: [...ALLOWED_ACTIONS],
      checkedAt: now(),
    };
  }

  async function execute({ action = "STATUS", payload = {}, requestId } = {}) {
    if (!ALLOWED_ACTIONS.includes(action)) {
      throw new OperatorError("ACTION_NOT_ALLOWED", 400);
    }
    if (action === "STATUS") {
      return {
        ok: true,
        status: "OPERATOR_EXECUTE_READY",
        requestId,
        projectId,
        region,
        targetService,
        deploymentAdapterConfigured: Boolean(deploymentAdapter?.execute),
        allowedActions: [...ALLOWED_ACTIONS],
        checkedAt: now(),
      };
    }
    if (action === "READ_CLOUD_RUN_SERVICE") {
      return {
        ok: true,
        status: "SERVICE_READ",
        requestId,
        service: await readCloudRun(payload),
        checkedAt: now(),
      };
    }
    if (action === "VERIFY_ARCHITRON_HEALTH") {
      return { requestId, ...(await verifyTarget()) };
    }
    if (action === "READ_BUILD") {
      return { requestId, ...(await readBuild(payload)) };
    }
    if (action === "READ_WIF_INVENTORY") {
      fixedProject(payload, projectId);
      return readWifInventory({
        projectId,
        location: payload.location ?? "global",
        request: googleRequest,
        limits: payload.limits,
        requestId,
        now,
      });
    }
    const validated = validateDeployment(payload, projectId, region, regionSet);
    if (!deploymentAdapter?.execute) {
      throw new OperatorError("DEPLOYMENT_ADAPTER_REQUIRED", 503);
    }
    try {
      return {
        requestId,
        ...sanitizeDeployment(await deploymentAdapter.execute(validated)),
        checkedAt: now(),
      };
    } catch (error) {
      throw dependencyError(error);
    }
  }

  return { health, contract, execute };
}
