"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const {activationState, createController, SCRIPT_FILES} = require("./background.js");
const {audit, auditFiles} = require("./permission_audit.js");
const {build} = require("./build_edge_extension.js");

function fakeApi(config = {}, permission = false) {
  const calls = {execute: [], send: []};
  const api = {
    runtime: {id: "extension-id", onMessage: {addListener() {}}},
    storage: {managed: {async get(defaults) { return {...defaults, ...config}; }}},
    permissions: {async contains() { return permission; }},
    scripting: {async executeScript(input) { calls.execute.push(input); }},
    tabs: {async sendMessage(tabId, message) { calls.send.push({tabId, message}); return {state: "OK"}; }}
  };
  return {api, calls};
}

assert.equal(activationState({enabled: false}), "DISABLED_CONFIG");
assert.equal(activationState({enabled: true, allowedOrigin: "https://example.com/*"}), "ORIGIN_POLICY_MISMATCH");
assert.equal(activationState({enabled: true, allowedOrigin: "https://chatgpt.com/*"}), "AUTHORIZED_EDGE_HOOK_REQUIRED");

(async () => {
  let fixture = fakeApi();
  let controller = createController(fixture.api);
  assert.equal((await controller.handle({type: "FACPF_ATTACH", tabId: 1}, {id: "other"})).state, "REJECTED_SENDER");
  assert.equal((await controller.handle({type: "FACPF_ATTACH", tabId: 0}, {id: "extension-id"})).state, "REJECTED_TAB_ID");
  assert.equal((await controller.handle({type: "FACPF_ATTACH", tabId: 1}, {id: "extension-id"})).reason, "DISABLED_CONFIG");
  assert.equal(fixture.calls.execute.length, 0);

  const admitted = {
    enabled: true,
    authorizedEdgeHookPresent: true,
    formationPermitValidated: true,
    operatorActivationValidated: true,
    allowedOrigin: "https://chatgpt.com/*"
  };
  fixture = fakeApi(admitted, false);
  controller = createController(fixture.api);
  assert.equal((await controller.handle({type: "FACPF_ATTACH", tabId: 7}, {id: "extension-id"})).reason, "OPTIONAL_PERMISSION_REQUIRED");
  assert.equal(fixture.calls.execute.length, 0);

  fixture = fakeApi(admitted, true);
  controller = createController(fixture.api);
  assert.deepEqual(await controller.handle({type: "FACPF_ATTACH", tabId: 7}, {id: "extension-id"}), {state: "ATTACHED", aggregateOnly: true});
  assert.deepEqual(fixture.calls.execute[0], {target: {tabId: 7}, files: SCRIPT_FILES.slice()});
  assert.deepEqual(await controller.handle({type: "FACPF_DETACH", tabId: 7}, {id: "extension-id"}), {state: "OK"});

  const packageAudit = auditFiles();
  assert.equal(packageAudit.decision, "ALLOW_INACTIVE_PACKAGE");
  assert.deepEqual(packageAudit.mandatoryPermissions, ["storage"]);
  assert.deepEqual(packageAudit.optionalPermissions, ["scripting"]);
  assert.deepEqual(packageAudit.optionalHosts, ["https://chatgpt.com/*"]);
  assert.equal(packageAudit.automaticContentScripts, 0);
  assert.equal(packageAudit.deploymentEnabled, false);

  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, "manifest.json"), "utf8"));
  const deployment = JSON.parse(fs.readFileSync(path.join(__dirname, "enterprise_deployment_contract.json"), "utf8"));
  assert.equal(audit({...manifest, permissions: ["storage", "tabs"]}, deployment).decision, "BLOCK_PACKAGE");
  assert.equal(audit({...manifest, host_permissions: ["<all_urls>"]}, deployment).decision, "BLOCK_PACKAGE");
  assert.equal(audit({...manifest, content_scripts: [{}]}, deployment).decision, "BLOCK_PACKAGE");
  assert.equal(audit(manifest, {...deployment, enabled: true}).decision, "BLOCK_PACKAGE");
  assert.equal(audit(manifest, deployment, ["chrome.permissions.request({})"]).decision, "BLOCK_PACKAGE");
  assert.equal(audit(manifest, deployment, ["fetch('https://example.com')"]).decision, "BLOCK_PACKAGE");

  const output = fs.mkdtempSync(path.join(os.tmpdir(), "facpf-edge-"));
  const receipt = build(output);
  assert.equal(receipt.evidenceClass, "LOCAL_UNSIGNED_UNPACKED_NOT_INSTALLED");
  assert.equal(receipt.files.length, 6);
  assert.equal(receipt.installed, false);
  assert.equal(receipt.activated, false);
  for (const file of receipt.files) assert.equal(fs.existsSync(path.join(output, file.name)), true);
  const serialized = JSON.stringify([packageAudit, receipt]);
  for (const forbidden of ["messageText", "rawDom", "private-url", "<all_urls>"]) assert.equal(serialized.includes(forbidden), false);
  console.log("edge extension tests passed");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
