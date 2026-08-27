import { createHash } from "node:crypto";

export const OPERATOR_IDENTITY = "federation-omega-operator";
export const OPERATOR_VERSION = "fo-operator-v4-cios-production";
export const DEFAULT_PROJECT = "sov-hybrid-suite";
export const DEFAULT_REGION = "africa-south1";
export const DEFAULT_TARGET_SERVICE = "architron9";
export const DEFAULT_VERTEX_LOCATION = "global";
export const DEFAULT_GEMINI_MODEL = "gemini-2.5-flash";
export const DEFAULT_TENANT = "federation-omega";
export const CFRE_PRIVATE_SERVICE = "cfre-omega-private-runtime";
export const DEFAULT_CIOS_SERVICE = "cios-capital-intelligence";
export const CFRE_REPAIR_SHA256 = "58c1e456f02642bcccdf13c8029a07dc4f497f6418c274afc6d8185365f7407b";
export const CFRE_MANIFEST_SHA256 = "c581e04c3a5f15e59451e1fc6201ad1b07032418f632994001bf2d449f6b93e7";

export const ALLOWED_ACTIONS = Object.freeze([
  "STATUS",
  "READ_CLOUD_RUN_SERVICE",
  "VERIFY_ARCHITRON_HEALTH",
  "DEPLOY_SOLUTION5_LOCKED",
  "READ_BUILD",
  "BIND_CFRE_PRIVATE_RUNTIME",
  "READ_GEMINI_VERTEX_CAPABILITY",
  "VERIFY_GEMINI_VERTEX_SEMANTIC",
  "READ_CIOS_PRODUCTION",
  "READ_CIOS_PERSISTENCE",
  "DEPLOY_CIOS_ZERO_TRAFFIC",
  "VERIFY_CIOS_CANARY",
  "ROLLBACK_CIOS_TRAFFIC",
  "PROMOTE_CIOS_TRAFFIC",
]);

export class ContractError extends Error {
  constructor(message, code = "INVALID_REQUEST") {
    super(message);
    this.name = "ContractError";
    this.code = code;
  }
}

export function sha256Hex(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

export function requireString(value, field, pattern = null) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new ContractError(`${field} is required`, "INVALID_FIELD");
  }
  const cleaned = value.trim();
  if (pattern && !pattern.test(cleaned)) {
    throw new ContractError(`${field} has an invalid format`, "INVALID_FIELD");
  }
  return cleaned;
}

function requireExact(value, expected, field) {
  if (value !== expected) {
    throw new ContractError(`${field} must equal ${expected}`, "TARGET_MISMATCH");
  }
  return value;
}

function expectedCios(env) {
  const project = env.CIOS_PROJECT_ID || env.PROJECT_ID || DEFAULT_PROJECT;
  const region = env.CIOS_REGION || env.REGION || DEFAULT_REGION;
  const service = env.CIOS_SERVICE || DEFAULT_CIOS_SERVICE;
  return {
    project,
    region,
    service,
    serviceAccount: env.CIOS_RUNTIME_SERVICE_ACCOUNT || `cios-runtime@${project}.iam.gserviceaccount.com`,
    cloudSqlInstance: env.CIOS_CLOUD_SQL_INSTANCE || `${project}:${region}:cios-postgres`,
    artifactRepository: env.CIOS_ARTIFACT_REPOSITORY || "federation-omega",
    databaseSecret: env.CIOS_DATABASE_SECRET || "cios-database-url",
    auditDatabaseSecret: env.CIOS_AUDIT_DATABASE_SECRET || "cios-audit-database-url",
    bearerSecret: env.CIOS_BEARER_SECRET || "cios-bearer-token",
    tenantId: env.CIOS_TENANT_ID || "evidenceops-capital-intelligence",
    runtimeUserId: env.CIOS_RUNTIME_USER_ID || "cios-provider-operator",
  };
}

function validateCiosTarget(payload, env) {
  requireObject(payload);
  const expected = expectedCios(env);
  for (const field of ["project", "region", "service", "serviceAccount", "cloudSqlInstance", "databaseSecret", "auditDatabaseSecret", "bearerSecret", "tenantId", "runtimeUserId"]) {
    requireExact(payload[field] || expected[field], expected[field], field);
  }
  return expected;
}

export function validateCiosReadPayload(payload = {}, env = process.env) {
  const target = validateCiosTarget(payload, env);
  return Object.freeze({ project: target.project, region: target.region, service: target.service });
}

export function validateCiosPersistencePayload(payload = {}, env = process.env) {
  return Object.freeze(validateCiosTarget(payload, env));
}

export function validateCiosDeployPayload(payload = {}, env = process.env) {
  const target = validateCiosTarget(payload, env);
  requireExact(payload.approvalKey, "APPROVED_CIOS_ZERO_TRAFFIC", "approvalKey");
  const sourceSha = requireString(payload.sourceSha, "sourceSha", /^[a-f0-9]{40}$/);
  const image = requireString(payload.image, "image", /^[a-z0-9.-]+\/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$/);
  const expectedPrefix = `${target.region}-docker.pkg.dev/${target.project}/${target.artifactRepository}/`;
  if (!image.startsWith(expectedPrefix)) {
    throw new ContractError("image must use the allowlisted Artifact Registry repository", "IMAGE_TARGET_MISMATCH");
  }
  const tag = requireString(payload.tag, "tag", /^[a-z][a-z0-9-]{2,30}$/);
  const idempotencyKey = requireString(payload.idempotencyKey, "idempotencyKey", /^[A-Za-z0-9._:-]{16,180}$/);
  return Object.freeze({
    ...target,
    approvalKey: "APPROVED_CIOS_ZERO_TRAFFIC",
    sourceSha,
    image,
    tag,
    idempotencyKey,
  });
}

function validateCiosReceiptPayload(payload, env, approvalKey) {
  const target = validateCiosTarget(payload, env);
  requireExact(payload.approvalKey, approvalKey, "approvalKey");
  return Object.freeze({
    ...target,
    approvalKey,
    sourceSha: requireString(payload.sourceSha, "sourceSha", /^[a-f0-9]{40}$/),
    revision: requireString(payload.revision, "revision", /^[a-z][a-z0-9-]{2,62}$/),
    deploymentKey: requireString(payload.deploymentKey, "deploymentKey", /^[A-Za-z0-9._:-]{16,180}$/),
    canaryKey: payload.canaryKey
      ? requireString(payload.canaryKey, "canaryKey", /^[A-Za-z0-9._:-]{16,180}$/)
      : null,
  });
}

export function validateCiosCanaryPayload(payload = {}, env = process.env) {
  const binding = validateCiosReceiptPayload(payload, env, "APPROVED_CIOS_SEMANTIC_CANARY");
  const occurredAt = requireString(payload.occurredAt, "occurredAt", /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/);
  const canaryKey = requireString(payload.canaryKey, "canaryKey", /^[A-Za-z0-9._:-]{16,180}$/);
  return Object.freeze({ ...binding, canaryKey, occurredAt });
}

export function validateCiosRollbackPayload(payload = {}, env = process.env) {
  return validateCiosReceiptPayload(payload, env, "APPROVED_CIOS_BASELINE_ROLLBACK");
}

export function validateCiosPromotePayload(payload = {}, env = process.env) {
  if (env.CIOS_PROMOTION_ENABLED !== "true") {
    throw new ContractError("CIOS promotion is disabled", "CIOS_PROMOTION_DISABLED");
  }
  const binding = validateCiosReceiptPayload(payload, env, "APPROVED_CIOS_PRODUCTION_PROMOTION");
  if (!binding.canaryKey) {
    throw new ContractError("canaryKey is required", "INVALID_FIELD");
  }
  return binding;
}

function requireObject(payload) {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    throw new ContractError("payload must be an object", "INVALID_PAYLOAD");
  }
  return payload;
}

function allowedGeminiModels(env) {
  return new Set(
    String(env.GEMINI_ALLOWED_MODELS || DEFAULT_GEMINI_MODEL)
      .split(",")
      .map((model) => model.trim())
      .filter(Boolean),
  );
}

export function validateBindPayload(payload = {}, env = process.env) {
  requireObject(payload);
  const expectedProject = env.PROJECT_ID || DEFAULT_PROJECT;
  const expectedRegion = env.REGION || DEFAULT_REGION;
  const expectedService = env.CFRE_PRIVATE_SERVICE || CFRE_PRIVATE_SERVICE;
  const expectedServiceAccount = env.CFRE_RUNTIME_SERVICE_ACCOUNT ||
    `fo-operator-sa@${expectedProject}.iam.gserviceaccount.com`;
  const sourceDriveId = requireString(payload.sourceDriveId, "sourceDriveId", /^[A-Za-z0-9_-]{20,}$/);
  const sourceSha256 = requireString(payload.sourceSha256, "sourceSha256", /^[a-f0-9]{64}$/);
  const idempotencyKey = requireString(payload.idempotencyKey, "idempotencyKey", /^[A-Za-z0-9._:-]{12,180}$/);

  requireExact(payload.approvalKey, "APPROVED", "approvalKey");
  requireExact(payload.project, expectedProject, "project");
  requireExact(payload.region, expectedRegion, "region");
  requireExact(payload.service, expectedService, "service");
  requireExact(payload.serviceAccount, expectedServiceAccount, "serviceAccount");
  requireExact(payload.embeddedRepairSha256, CFRE_REPAIR_SHA256, "embeddedRepairSha256");
  requireExact(payload.manifestSha256, CFRE_MANIFEST_SHA256, "manifestSha256");

  return Object.freeze({
    approvalKey: "APPROVED",
    project: expectedProject,
    region: expectedRegion,
    service: expectedService,
    serviceAccount: expectedServiceAccount,
    sourceDriveId,
    sourceSha256,
    embeddedRepairSha256: CFRE_REPAIR_SHA256,
    manifestSha256: CFRE_MANIFEST_SHA256,
    idempotencyKey,
    dryRun: payload.dryRun === true,
  });
}

export function validateGeminiCapabilityPayload(payload = {}, env = process.env) {
  requireObject(payload);
  const project = requireExact(
    payload.project || env.PROJECT_ID || DEFAULT_PROJECT,
    env.PROJECT_ID || DEFAULT_PROJECT,
    "project",
  );
  const location = requireExact(
    payload.location || env.VERTEX_LOCATION || DEFAULT_VERTEX_LOCATION,
    env.VERTEX_LOCATION || DEFAULT_VERTEX_LOCATION,
    "location",
  );
  const tenantId = requireExact(
    payload.tenantId || env.FEDERATION_TENANT_ID || DEFAULT_TENANT,
    env.FEDERATION_TENANT_ID || DEFAULT_TENANT,
    "tenantId",
  );
  const model = requireString(
    payload.model || env.GEMINI_MODEL || DEFAULT_GEMINI_MODEL,
    "model",
    /^[a-z0-9][a-z0-9._-]{2,80}$/,
  );
  if (!allowedGeminiModels(env).has(model)) {
    throw new ContractError("model is not allowlisted", "MODEL_NOT_ALLOWED");
  }
  return Object.freeze({ project, location, model, tenantId });
}

export function validateGeminiSemanticPayload(payload = {}, env = process.env) {
  const target = validateGeminiCapabilityPayload(payload, env);
  if (env.GEMINI_SEMANTIC_CANARY_ENABLED !== "true") {
    throw new ContractError("semantic canary is disabled", "SEMANTIC_CANARY_DISABLED");
  }
  requireExact(payload.approvalKey, "APPROVED_SEMANTIC_CANARY", "approvalKey");
  const nonce = requireString(payload.nonce, "nonce", /^[A-Za-z0-9._:-]{12,128}$/);
  const idempotencyKey = requireString(
    payload.idempotencyKey,
    "idempotencyKey",
    /^[A-Za-z0-9._:-]{12,180}$/,
  );
  return Object.freeze({
    ...target,
    approvalKey: "APPROVED_SEMANTIC_CANARY",
    nonce,
    idempotencyKey,
    maxOutputTokens: 64,
  });
}

export function validateCloudReadPayload(payload = {}, env = process.env) {
  const project = requireExact(payload.project || env.PROJECT_ID || DEFAULT_PROJECT, env.PROJECT_ID || DEFAULT_PROJECT, "project");
  const region = requireExact(payload.region || env.REGION || DEFAULT_REGION, env.REGION || DEFAULT_REGION, "region");
  const service = requireString(payload.service || env.TARGET_SERVICE || DEFAULT_TARGET_SERVICE, "service", /^[a-z][a-z0-9-]{0,62}$/);
  return Object.freeze({ project, region, service });
}
