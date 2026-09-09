import test from 'node:test';
import assert from 'node:assert/strict';
import {
  READ_APPS_SCRIPT_PROJECT_BOUNDED,
  STRATEGIC_TARGET_SCRIPT_ID,
  boundedManifestFromContent,
  executeAppsScriptBoundedReadAction,
  readAppsScriptProjectBounded,
} from '../lib/apps_script_bounded_read.mjs';

const contentA = {
  files: [
    { name: 'B', type: 'SERVER_JS', source: 'function gasSchedulerInstallV3(){}\nfunction gns3ProcessQueue_(){}' },
    { name: 'A', type: 'SERVER_JS', source: 'function gasSchedulerRunV3(){}\nfunction gns3QueueTask_(){}' },
    { name: 'appsscript', type: 'JSON', source: '{"timeZone":"Etc/GMT"}' },
  ],
};

test('action identifier is exact and stable', () => {
  assert.equal(READ_APPS_SCRIPT_PROJECT_BOUNDED, 'READ_APPS_SCRIPT_PROJECT_BOUNDED');
});

test('bounded manifest never returns raw source and is no-effect', () => {
  const out = boundedManifestFromContent(contentA);
  assert.equal(out.ok, true);
  assert.equal(out.fileCount, 3);
  assert.equal(out.functionCount, 4);
  assert.equal(out.rawSourcePersisted, false);
  assert.equal(out.sourceReturned, false);
  assert.equal(out.providerEffect, false);
  assert.equal(out.mutationAttempted, false);
  assert.equal(out.secretValuesRecorded, false);
  assert.equal(JSON.stringify(out).includes('function gasScheduler'), false);
  assert.deepEqual(out.files.map((x) => x.name), ['A', 'B', 'appsscript']);
});

test('project digest is deterministic across provider file order', () => {
  const first = boundedManifestFromContent(contentA);
  const second = boundedManifestFromContent({ files: [...contentA.files].reverse() });
  assert.equal(first.projectDigest, second.projectDigest);
});

test('required function presence is explicit and missing Strategic handler stays false', () => {
  const out = boundedManifestFromContent(contentA);
  assert.equal(out.requiredFunctionsPresent.gasSchedulerRunV3, true);
  assert.equal(out.requiredFunctionsPresent.gasSchedulerInstallV3, true);
  assert.equal(out.requiredFunctionsPresent.STRATEGIC_FUSE_SECONDARY_BRAIN, false);
});

test('wrong target fails closed before provider call', async () => {
  let calls = 0;
  const out = await executeAppsScriptBoundedReadAction({
    async api() { calls += 1; return { body: contentA }; },
  }, { scriptId: 'wrong' });
  assert.equal(out.httpStatus, 400);
  assert.equal(out.body.reason, 'TARGET_MISMATCH');
  assert.equal(calls, 0);
});

test('provider route performs exactly one GET-shaped api call', async () => {
  const calls = [];
  const out = await readAppsScriptProjectBounded(async (...args) => {
    calls.push(args);
    return { status: 200, body: contentA };
  });
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], `https://script.googleapis.com/v1/projects/${STRATEGIC_TARGET_SCRIPT_ID}/content`);
  assert.deepEqual(calls[0][1], {});
  assert.deepEqual(calls[0][2], [200]);
  assert.equal(out.status, 'APPS_SCRIPT_PROJECT_BOUNDED_READ_VERIFIED');
});

test('action wrapper returns semantic success with exact no-effect flags', async () => {
  const result = await executeAppsScriptBoundedReadAction({
    async api() { return { status: 200, body: contentA }; },
  }, { scriptId: STRATEGIC_TARGET_SCRIPT_ID });
  assert.equal(result.httpStatus, 200);
  assert.equal(result.body.status, 'APPS_SCRIPT_PROJECT_BOUNDED_READ_VERIFIED');
  assert.equal(result.body.providerEffect, false);
});

test('provider rejection is normalized without leaking provider response body', async () => {
  const secretMarker = 'DO_NOT_LEAK_PROVIDER_BODY';
  const result = await executeAppsScriptBoundedReadAction({
    async api() { throw new Error(`provider 403: {"error":"${secretMarker}"}`); },
  });
  assert.equal(result.httpStatus, 502);
  assert.equal(result.body.status, 'APPS_SCRIPT_PROJECT_BOUNDED_READ_FAILED');
  assert.equal(result.body.reason, 'PROVIDER_HTTP_403');
  assert.equal(result.body.providerHttpStatus, 403);
  assert.equal(JSON.stringify(result).includes(secretMarker), false);
  assert.equal(result.body.rawSourcePersisted, false);
  assert.equal(result.body.providerEffect, false);
});

test('missing adapter is explicit and no-effect', async () => {
  const result = await executeAppsScriptBoundedReadAction({});
  assert.equal(result.httpStatus, 503);
  assert.equal(result.body.reason, 'ADAPTER_UNAVAILABLE');
  assert.equal(result.body.providerEffect, false);
});
