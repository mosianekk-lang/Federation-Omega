"use strict";
const fs = require("node:fs");
const path = require("node:path");

const FORBIDDEN_PERMISSIONS = new Set(["tabs", "debugger", "nativeMessaging", "webRequest", "webRequestBlocking", "cookies", "history"]);

function audit(manifest, deployment, sources = []) {
  const mandatory = new Set(manifest.permissions || []);
  const optional = new Set(manifest.optional_permissions || []);
  const optionalHosts = manifest.optional_host_permissions || [];
  const findings = [];
  if (manifest.manifest_version !== 3) findings.push("MANIFEST_VERSION_NOT_3");
  if ((manifest.content_scripts || []).length) findings.push("AUTOMATIC_CONTENT_SCRIPT_PRESENT");
  if ((manifest.host_permissions || []).length) findings.push("MANDATORY_HOST_PERMISSION_PRESENT");
  for (const permission of mandatory) if (FORBIDDEN_PERMISSIONS.has(permission)) findings.push("FORBIDDEN_PERMISSION:" + permission);
  if ([...mandatory].sort().join(",") !== "storage") findings.push("MANDATORY_PERMISSION_SET_DRIFT");
  if ([...optional].sort().join(",") !== "scripting") findings.push("OPTIONAL_PERMISSION_SET_DRIFT");
  if (optionalHosts.length !== 1 || optionalHosts[0] !== "https://chatgpt.com/*") findings.push("OPTIONAL_HOST_SCOPE_DRIFT");
  if (!manifest.storage || manifest.storage.managed_schema !== "managed_schema.json") findings.push("MANAGED_SCHEMA_MISSING");
  const csp = manifest.content_security_policy && manifest.content_security_policy.extension_pages;
  if (csp !== "script-src 'self'; object-src 'self'") findings.push("CSP_DRIFT");
  if (deployment.enabled !== false || deployment.applyAllowed !== false) findings.push("DEPLOYMENT_NOT_INACTIVE");
  if (deployment.policyMutationIncluded !== false || deployment.installationMode !== "NOT_CONFIGURED") findings.push("POLICY_MUTATION_PRESENT");
  if (deployment.extensionId !== null || deployment.updateUrl !== null) findings.push("UNVERIFIED_IDENTITY_PRESENT");
  const forbiddenSourcePatterns = [
    ["PERMISSION_REQUEST_PRESENT", /permissions\.request\s*\(/],
    ["REMOTE_FETCH_PRESENT", /\bfetch\s*\(/],
    ["XMLHTTPREQUEST_PRESENT", /\bXMLHttpRequest\b/],
    ["WEBSOCKET_PRESENT", /\bWebSocket\b/],
    ["DYNAMIC_EVAL_PRESENT", /\beval\s*\(|\bnew\s+Function\s*\(/],
    ["REMOTE_IMPORT_PRESENT", /\bimportScripts\s*\(/]
  ];
  for (const source of sources) {
    for (const [code, pattern] of forbiddenSourcePatterns) if (pattern.test(source)) findings.push(code);
  }
  return {
    schema: "FACPF-EDGE-PERMISSION-AUDIT-1",
    decision: findings.length ? "BLOCK_PACKAGE" : "ALLOW_INACTIVE_PACKAGE",
    findings,
    mandatoryPermissions: [...mandatory].sort(),
    optionalPermissions: [...optional].sort(),
    optionalHosts,
    automaticContentScripts: (manifest.content_scripts || []).length,
    deploymentEnabled: deployment.enabled,
    installed: false,
    activated: false
  };
}

function auditFiles(root = __dirname) {
  return audit(
    JSON.parse(fs.readFileSync(path.join(root, "manifest.json"), "utf8")),
    JSON.parse(fs.readFileSync(path.join(root, "enterprise_deployment_contract.json"), "utf8")),
    ["background.js", "content_hook.js"].map((name) => fs.readFileSync(path.join(root, name), "utf8"))
  );
}

if (require.main === module) {
  const result = auditFiles();
  console.log(JSON.stringify(result, null, 2));
  if (result.decision !== "ALLOW_INACTIVE_PACKAGE") process.exitCode = 1;
}
module.exports = {audit, auditFiles, FORBIDDEN_PERMISSIONS};
