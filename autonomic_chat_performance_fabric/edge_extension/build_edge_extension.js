"use strict";
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const sourceRoot = __dirname;
const fabricRoot = path.dirname(sourceRoot);
const packageFiles = {
  "manifest.json": path.join(sourceRoot, "manifest.json"),
  "managed_schema.json": path.join(sourceRoot, "managed_schema.json"),
  "background.js": path.join(sourceRoot, "background.js"),
  "content_hook.js": path.join(sourceRoot, "content_hook.js"),
  "aggregate_browser_probe.js": path.join(fabricRoot, "aggregate_browser_probe.js"),
  "native_edge_chatgpt_diagnostic.js": path.join(fabricRoot, "native_edge_chatgpt_diagnostic.js")
};

function sha256(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

function build(destination) {
  if (!destination) throw new TypeError("destination required");
  fs.mkdirSync(destination, {recursive: true});
  const files = [];
  for (const [name, source] of Object.entries(packageFiles)) {
    const bytes = fs.readFileSync(source);
    fs.writeFileSync(path.join(destination, name), bytes);
    files.push({name, sha256: sha256(bytes), bytes: bytes.length});
  }
  const receipt = {
    schema: "FACPF-EDGE-PACKAGE-BUILD-1",
    evidenceClass: "LOCAL_UNSIGNED_UNPACKED_NOT_INSTALLED",
    files,
    installed: false,
    activated: false,
    policyApplied: false
  };
  fs.writeFileSync(path.join(destination, "BUILD_RECEIPT.json"), JSON.stringify(receipt, null, 2) + "\n");
  return receipt;
}

if (require.main === module) {
  const destination = process.argv[2];
  console.log(JSON.stringify(build(destination), null, 2));
}
module.exports = {build, packageFiles, sha256};
