"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const background = fs.readFileSync(path.join(root, "src", "background.js"), "utf8");
const content = fs.readFileSync(path.join(root, "src", "content-script.js"), "utf8");
const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json"), "utf8"));

test("browser adapter writes local capture before optional provider upload", () => {
  const localWrite = background.indexOf("await putCapture(captureRecord)");
  const providerUpload = background.indexOf("await uploadCapture");
  assert.ok(localWrite >= 0);
  assert.ok(providerUpload > localWrite);
  assert.match(background, /PROVIDER_UPLOAD_FAILED_LOCAL_DURABLE/);
});

test("content script captures before opening a successor chat", () => {
  const capture = content.indexOf('capture("LIMIT_WARNING_CLICK"');
  const open = content.indexOf('type: "CHATBRIDGE_OPEN"');
  assert.ok(capture >= 0);
  assert.ok(open > capture);
  assert.match(content, /terminalObserved: true/);
});

test("manifest loads the capture core before the content script", () => {
  const scripts = manifest.content_scripts[0].js;
  assert.deepEqual(scripts, ["src/bridge-core.js", "src/content-script.js"]);
  assert.equal(manifest.version, "0.3.0");
});
