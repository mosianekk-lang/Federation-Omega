import assert from "node:assert/strict";
import crypto from "node:crypto";
import path from "node:path";
import {mock, test} from "node:test";
import {pathToFileURL} from "node:url";

process.env.ALLOWED_PROJECTS = "sov-hybrid-suite";
process.env.ALLOWED_SERVICES = "script.googleapis.com";
process.env.ALLOWED_SCRIPT_IDS = "script-1";
process.env.FEDERATION_APPROVAL_TOKEN = "approved-test-token";

const compiledDir = process.env.SECURITY_TEST_DIST ?? new URL("../dist", import.meta.url).pathname;
const moduleUrl = name => pathToFileURL(path.resolve(compiledDir, `${name}.js`)).href;
mock.module(moduleUrl("google"), {
  namedExports: {googleJson: async () => ({status: 200, body: {}})},
});

const {audit, auditRecordForPersistence} = await import(moduleUrl("audit"));
const {
  assertTerminalOperationSucceeded,
  enableService,
  scriptApply,
  scriptRollback,
  sourceSha256,
} = await import(moduleUrl("operations"));

const fullHash = value => crypto.createHash("sha256")
  .update(JSON.stringify(value)).digest("hex");

test("audit persistence excludes source, secrets and raw provider payloads", async () => {
  const secret = "SENTINEL_SECRET_VALUE";
  const rawResult = {
    scriptId: "script-1",
    content: {files: [{name: "Code", source: secret}]},
    raw: `provider:${secret}`,
    accessToken: secret,
  };
  const returned = await audit("security_test", {scriptId: "script-1"}, async () => rawResult);
  const persisted = auditRecordForPersistence(returned);
  const serialized = JSON.stringify(persisted);
  assert.equal(returned.result, rawResult, "authorized caller result remains available");
  assert.doesNotMatch(serialized, new RegExp(secret));
  assert.doesNotMatch(serialized, /provider:/);
  assert.equal(persisted.result.redacted, true);
  assert.match(persisted.result.resultHash, /^[a-f0-9]{64}$/);
  assert.equal(persisted.result.summary.fileCount, 1);
});

test("terminal provider operation errors fail without persisting the provider message", () => {
  assert.throws(
    () => assertTerminalOperationSucceeded({done: true, error: {code: 7, message: "private detail"}}),
    error => error.message === "OPERATION_FAILED:7"
  );
});

test("API enablement uses mutation identity and rejects terminal operation errors", async () => {
  const calls = [];
  const call = async (url, init = {}) => {
    calls.push({url, init});
    if (url.endsWith(":enable")) return {status: 200, body: {name: "operations/1"}};
    return {status: 200, body: {done: true, error: {code: "PERMISSION_DENIED", message: "private"}}};
  };
  await assert.rejects(
    () => enableService("sov-hybrid-suite", "script.googleapis.com", "approved-test-token", call),
    /OPERATION_FAILED:PERMISSION_DENIED/
  );
  assert.equal(calls.length, 2);
  assert.ok(calls.every(item => item.init.googleAuthMode === "mutation"));
});

test("Apps Script apply requires exact post-write source equality", async () => {
  const current = {scriptId: "script-1", files: [{name: "Code", source: "old"}]};
  const proposed = {files: [{name: "Code", source: "new"}]};
  let reads = 0;
  const call = async (_url, init = {}) => {
    if (init.method === "PUT") {
      assert.equal(init.googleAuthMode, "mutation");
      return {status: 200, body: {}};
    }
    reads += 1;
    return {status: 200, body: reads === 1 ? current : {
      scriptId: "script-1", files: [{name: "Code", source: "unexpected"}]
    }};
  };
  await assert.rejects(
    () => scriptApply("script-1", fullHash(current), proposed, "approved-test-token", call),
    /POST_WRITE_VERIFICATION_FAILED/
  );
});

test("Apps Script rollback rejects stale current state before mutation", async () => {
  const current = {scriptId: "script-1", files: [{name: "Code", source: "current"}]};
  const desired = {files: [{name: "Code", source: "restore"}]};
  let writes = 0;
  const call = async (_url, init = {}) => {
    if (init.method === "PUT") writes += 1;
    return {status: 200, body: current};
  };
  await assert.rejects(
    () => scriptRollback(
      "script-1", "0".repeat(64), desired, sourceSha256(desired),
      "approved-test-token", call
    ),
    /OPTIMISTIC_LOCK_FAILED/
  );
  assert.equal(writes, 0);
});

test("Apps Script rollback validates desired backup and proves restored source", async () => {
  const current = {scriptId: "script-1", files: [{name: "Code", source: "current"}]};
  const desired = {files: [{name: "Code", source: "restore"}]};
  let reads = 0;
  const calls = [];
  const call = async (_url, init = {}) => {
    calls.push(init);
    if (init.method === "PUT") return {status: 200, body: {}};
    reads += 1;
    return {status: 200, body: reads === 1 ? current : {scriptId: "script-1", ...desired}};
  };
  const expectedBackupSha256 = sourceSha256(desired);
  const result = await scriptRollback(
    "script-1", fullHash(current), desired, expectedBackupSha256,
    "approved-test-token", call
  );
  assert.equal(result.after.sourceSha256, expectedBackupSha256);
  assert.equal(calls.find(item => item.method === "PUT").googleAuthMode, "mutation");
});
