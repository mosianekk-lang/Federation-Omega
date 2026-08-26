import {
  ALLOWED_ACTIONS,
  OPERATOR_IDENTITY,
  OPERATOR_VERSION,
  validateBindPayload,
  validateCloudReadPayload,
  validateGeminiCapabilityPayload,
  validateGeminiSemanticPayload,
} from "./contracts.mjs";

export async function executeAction({ action, payload = {}, principal, adapter, env = process.env }) {
  if (!ALLOWED_ACTIONS.includes(action)) {
    return { httpStatus: 400, body: { ok: false, status: "ACTION_NOT_ALLOWED", action } };
  }
  if (action === "STATUS") {
    return { httpStatus: 200, body: { ok: true, status: "OPERATOR_EXECUTE_READY", service: OPERATOR_IDENTITY, version: OPERATOR_VERSION, authMode: principal.mode, principal: principal.principal } };
  }
  if (action === "READ_CLOUD_RUN_SERVICE") {
    const target = validateCloudReadPayload(payload, env);
    return { httpStatus: 200, body: { ok: true, status: "SERVICE_READ", service: await adapter.readService(target) } };
  }
  if (action === "VERIFY_ARCHITRON_HEALTH") {
    const target = validateCloudReadPayload({ ...payload, service: env.TARGET_SERVICE || "architron9" }, env);
    return { httpStatus: 200, body: await adapter.verifyServiceHealth(target) };
  }
  if (action === "READ_BUILD") {
    return { httpStatus: 200, body: { ok: true, status: "BUILD_READ", build: await adapter.readBuild(payload) } };
  }
  if (action === "DEPLOY_SOLUTION5_LOCKED") {
    if (typeof adapter.deploySolution5Locked !== "function") {
      return { httpStatus: 503, body: { ok: false, status: "LEGACY_DEPLOY_ADAPTER_UNAVAILABLE" } };
    }
    return { httpStatus: 200, body: await adapter.deploySolution5Locked(payload) };
  }
  if (action === "READ_GEMINI_VERTEX_CAPABILITY") {
    if (typeof adapter.readGeminiVertexCapability !== "function") {
      return { httpStatus: 503, body: { ok: false, status: "GEMINI_VERTEX_ADAPTER_UNAVAILABLE" } };
    }
    const target = validateGeminiCapabilityPayload(payload, env);
    return { httpStatus: 200, body: await adapter.readGeminiVertexCapability(target) };
  }
  if (action === "VERIFY_GEMINI_VERTEX_SEMANTIC") {
    if (typeof adapter.verifyGeminiVertexSemantic !== "function") {
      return { httpStatus: 503, body: { ok: false, status: "GEMINI_VERTEX_ADAPTER_UNAVAILABLE" } };
    }
    const canary = validateGeminiSemanticPayload(payload, env);
    return { httpStatus: 200, body: await adapter.verifyGeminiVertexSemantic(canary) };
  }
  const binding = validateBindPayload(payload, env);
  if (binding.dryRun) {
    return { httpStatus: 200, body: { ok: true, status: "CFRE_BIND_PLAN_VERIFIED", mutationAttempted: false, binding } };
  }
  return { httpStatus: 200, body: await adapter.bindCfrePrivateRuntime(binding) };
}
