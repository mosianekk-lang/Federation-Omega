"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const readiness = fs.readFileSync(path.join(root, "tools", "ChatBridge-Readiness.ps1"), "utf8");
const handoff = fs.readFileSync(path.join(root, "enterprise", "CHATBRIDGE_ENTERPRISE_HANDOFF.md"), "utf8");
const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json"), "utf8"));

test("Windows readiness assessor is read-only and never elevates or changes policy", () => {
  const forbidden = [
    /Start-Process[^\n]+-Verb\s+RunAs/i,
    /Set-ItemProperty/i,
    /New-ItemProperty/i,
    /Remove-ItemProperty/i,
    /\breg(?:\.exe)?\s+add\b/i,
    /Set-ExecutionPolicy/i,
    /-ExecutionPolicy\s+Bypass/i,
  ];
  for (const pattern of forbidden) assert.doesNotMatch(readiness, pattern);
  assert.match(readiness, /READ_ONLY_NO_ELEVATION/);
  assert.match(readiness, /externalExecutionClaimed\s*=\s*\$false/);
  assert.match(readiness, /installed\s*=\s*\$false/);
  assert.match(readiness, /browserBound\s*=\s*\$false/);
});

test("assessor checks the material Edge and Chrome enterprise policy families", () => {
  for (const policy of [
    "ExtensionDeveloperModeSettings",
    "DeveloperToolsAvailability",
    "ExtensionInstallBlocklist",
    "ExtensionInstallAllowlist",
    "ExtensionInstallTypeBlocklist",
    "ExtensionSettings",
    "BlockExternalExtensions",
  ]) assert.match(readiness, new RegExp(policy));
});

test("extension retains its narrow permission surface", () => {
  assert.deepEqual(manifest.permissions, ["storage"]);
  assert.deepEqual(manifest.host_permissions, ["https://chatgpt.com/*"]);
  assert.equal(manifest.manifest_version, 3);
});

test("enterprise handoff fails closed on identity and deployment proof", () => {
  assert.match(handoff, /NOT SUBMITTED \/ NOT APPROVED \/ NOT DEPLOYED/);
  assert.match(handoff, /final extension ID and update URL remain `UNVERIFIED`/);
  assert.match(handoff, /Do not use a wildcard allow rule/);
  assert.match(handoff, /TESTED_NOT_DEPLOYED/);
});

