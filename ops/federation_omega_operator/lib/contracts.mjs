import { createHash } from "node:crypto";

export const OPERATOR_IDENTITY = "federation-omega-operator";
export const OPERATOR_VERSION = "fo-operator-v3-gemini-vertex1";
export const DEFAULT_PROJECT = "sov-hybrid-suite";
export const DEFAULT_REGION = "africa-south1";
export const DEFAULT_TARGET_SERVICE = "architron9";
export const DEFAULT_VERTEX_LOCATION = "global";
export const DEFAULT_GEMINI_MODEL = "gemini-2.5-flash";
export const DEFAULT_TENANT = "federation-omega";
export const CFRE_PRIVATE_SERVICE = "cfre-omega-private-runtime";
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
