import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.join(here, '..', 'NexusCodexDeployer.gs');
const source = fs.readFileSync(sourcePath, 'utf8');

function load(overrides = {}) {
  const context = {
    module: {exports: {}},
    exports: {},
    console,
    Date,
    JSON,
    Object,
    String,
    Number,
    Boolean,
    Array,
    RegExp,
    Error,
    encodeURIComponent,
    ...overrides
  };
  vm.createContext(context);
  vm.runInContext(source, context, {filename: sourcePath});
  return context.module.exports;
}

function signedBytesFromHex(hex) {
  return [...Buffer.from(hex, 'hex')].map((value) =>
    value > 127 ? value - 256 : value);
}

function exactDigestUtilities() {
  return {
    DigestAlgorithm: {SHA_256: 'SHA_256'},
    computeDigest() {
      return signedBytesFromHex(
          'fabbdf9ec89c1ea4468515ba1659cc0019719c5bc5747084795148a354dc1518');
    }
  };
}

function blob(bytes = new Array(28998).fill(1)) {
  return {
    getBytes: () => bytes,
    getContentType: () => 'application/zip'
  };
}

function response(code, body = {}, rawBlob = blob()) {
  return {
    getResponseCode: () => code,
    getContentText: () =>
      typeof body === 'string' ? body : JSON.stringify(body),
    getBlob: () => rawBlob
  };
}

test('plan is locked to the NEXUS target and requires no scheduler', () => {
  const api = load();
  const plan = api.nexusCodexPlanV1();
  assert.equal(plan.target.service, 'nexus-codex-runtime');
  assert.equal(plan.target.region, 'africa-south1');
  assert.equal(plan.releasePolicy.initialTrafficPercent, 0);
  assert.equal(plan.releasePolicy.recurringTriggerRequired, false);
  assert.equal(plan.manualUserTasks.length, 0);
  assert.equal(plan.ownerActionRequired, false);
});

test('wrong Drive hash fails before any external request', () => {
  let fetchCount = 0;
  const api = load({
    DriveApp: {
      getFileById: () => ({
        getName: () => 'nexus-codex-runtime-v3.1.1.zip',
        getBlob: () => blob()
      })
    },
    Utilities: {
      DigestAlgorithm: {SHA_256: 'SHA_256'},
      computeDigest: () => new Array(32).fill(0)
    },
    UrlFetchApp: {fetch: () => { fetchCount += 1; }},
    ScriptApp: {getOAuthToken: () => 'redacted-test-token'},
    PropertiesService: {
      getScriptProperties: () => ({
        getProperty: () => null,
        setProperty: () => {}
      })
    },
    LockService: {
      getScriptLock: () => ({waitLock() {}, releaseLock() {}})
    }
  });
  assert.throws(
      () => api.nexusCodexStageAndSubmitV1(),
      /nexus_artifact_sha256_mismatch/);
  assert.equal(fetchCount, 0);
});

test('recorded matching build is reused and no build is created', () => {
  const cfgSha =
      'fabbdf9ec89c1ea4468515ba1659cc0019719c5bc5747084795148a354dc1518';
  const prior = {
    contract: 'NEXUS_CODEX_HASH_LOCKED_DEPLOYER_V1',
    release: 'v3.1.1',
    artifactSha256: cfgSha,
    artifactDriveFileId: '1_r1qlRHeEcF7Xl-BSJpfWUWIRYs4C_Pm',
    projectId: 'sov-hybrid-suite',
    region: 'africa-south1',
    service: 'nexus-codex-runtime',
    runtimeServiceAccount:
      'fo-automation-agent@sov-hybrid-suite.iam.gserviceaccount.com',
    buildId: 'build-123',
    stagedObject: {bucket: 'b', objectName: 'o'},
    rollback: {previousTraffic: []},
    submittedAt: '2026-07-30T00:00:00Z'
  };
  const calls = [];
  const api = load({
    DriveApp: {
      getFileById: () => ({
        getName: () => 'nexus-codex-runtime-v3.1.1.zip',
        getBlob: () => blob()
      })
    },
    Utilities: exactDigestUtilities(),
    ScriptApp: {getOAuthToken: () => 'redacted-test-token'},
    UrlFetchApp: {
      fetch(url, options) {
        calls.push({url, method: options.method});
        return response(200, {id: 'build-123', status: 'WORKING'});
      }
    },
    PropertiesService: {
      getScriptProperties: () => ({
        getProperty: () => JSON.stringify(prior),
        setProperty: () => {
          throw new Error('unexpected state mutation');
        }
      })
    },
    LockService: {
      getScriptLock: () => ({waitLock() {}, releaseLock() {}})
    }
  });
  const receipt = api.nexusCodexStageAndSubmitV1();
  assert.equal(receipt.status, 'REUSED_RECORDED_BUILD');
  assert.equal(receipt.buildId, 'build-123');
  assert.equal(calls.length, 1);
  assert.equal(calls.some((call) => call.method === 'post'), false);
});

test('Cloud Build non-success is reduced to a safe status error', () => {
  const calls = [];
  let propertyValue = null;
  const api = load({
    DriveApp: {
      getFileById: () => ({
        getName: () => 'nexus-codex-runtime-v3.1.1.zip',
        getBlob: () => blob()
      })
    },
    Utilities: exactDigestUtilities(),
    ScriptApp: {getOAuthToken: () => 'redacted-test-token'},
    UrlFetchApp: {
      fetch(url, options) {
        calls.push({url, options});
        if (url.includes('run.googleapis.com')) return response(404, {});
        if (url.includes('/storage/v1/') && !url.includes('/download/')) {
          return response(200, {generation: '7', size: '28998'});
        }
        if (url.includes('/download/storage/')) return response(200, {}, blob());
        if (url.includes('/builds?') && options.method === 'get') {
          return response(200, {builds: []});
        }
        if (url.includes('/builds?') && options.method === 'post') {
          return response(403, {error: {message: 'must not escape'}});
        }
        throw new Error(`unexpected request: ${url}`);
      }
    },
    PropertiesService: {
      getScriptProperties: () => ({
        getProperty: () => propertyValue,
        setProperty: (_key, value) => { propertyValue = value; }
      })
    },
    LockService: {
      getScriptLock: () => ({waitLock() {}, releaseLock() {}})
    }
  });
  assert.throws(
      () => api.nexusCodexStageAndSubmitV1(),
      /^Error: google_api_http_403$/);
  assert.equal(propertyValue, null);
  assert.equal(
      calls.filter((call) =>
        call.url.includes('/builds?') && call.options.method === 'post').length,
      1);
});

test('target confusion fails closed', () => {
  const api = load();
  const confused = {
    ...api.NEXUS_CODEX_DEPLOYER_V1,
    service: 'architron9'
  };
  assert.throws(
      () => api.nexusAssertTargetV1_(confused),
      /nexus_target_confusion_service/);
});

test('rollback spec preserves exact revision percentages', () => {
  const api = load();
  const spec = api.nexusRollbackTrafficSpecV1_([
    {revision: 'nexus-codex-runtime-00001-aaa', percent: 90},
    {revision: 'nexus-codex-runtime-00002-bbb', percent: 10}
  ]);
  assert.equal(
      spec,
      'nexus-codex-runtime-00001-aaa=90,' +
      'nexus-codex-runtime-00002-bbb=10');
  assert.equal(
      api.nexusRollbackTrafficSpecV1_([
        {revision: 'nexus-codex-runtime-00001-aaa', percent: 99}
      ]),
      '');
});

test('build request is regional, no-traffic, canary-gated, and exact-target', () => {
  const api = load();
  const request = api.nexusBuildRequestV1_(
      api.NEXUS_CODEX_DEPLOYER_V1,
      {
        bucket: api.NEXUS_CODEX_DEPLOYER_V1.bucket,
        objectName: api.NEXUS_CODEX_DEPLOYER_V1.objectName,
        generation: '9'
      },
      {
        traffic: [{
          revision: 'nexus-codex-runtime-00001-aaa',
          percent: 100
        }]
      });
  const shell = request.steps[0].args[1];
  assert.equal(request.substitutions._SERVICE, 'nexus-codex-runtime');
  assert.equal(
      request.substitutions._RUNTIME_SERVICE_ACCOUNT,
      'fo-automation-agent@sov-hybrid-suite.iam.gserviceaccount.com');
  assert.match(shell, /--no-traffic/);
  assert.match(shell, /canary "\$\$TAG_URL"/);
  assert.ok(
      shell.indexOf('canary "$$TAG_URL"') <
      shell.indexOf('--to-tags="$${TAG}=100"'));
  assert.match(shell, /rollback_on_error/);
  assert.equal(shell.includes('--allow-unauthenticated'), false);
  const withoutValidSubstitutions = shell
      .replace(/\$\$/g, '')
      .replace(/\$\{_[A-Z0-9_]+\}/g, '');
  assert.equal(/\$[A-Za-z0-9({]/.test(withoutValidSubstitutions), false);

  const rendered = Object.entries(request.substitutions).reduce(
      (text, [key, value]) =>
        text.replaceAll(`\${${key}}`, String(value)),
      shell).replaceAll('$$', '$');
  const syntax = spawnSync('bash', ['-n'], {
    input: rendered,
    encoding: 'utf8'
  });
  assert.equal(syntax.status, 0, syntax.stderr);
});

test('source contains no secret material or token logging', () => {
  assert.equal(/OPENAI_API_KEY|sk-proj-|private[_ -]?key/i.test(source), false);
  assert.equal(/Logger\.log|console\.log/.test(source), false);
  assert.equal(
      /getOAuthToken\(\)[\s\S]{0,80}(Logger|console)/.test(source),
      false);
  assert.equal(source.includes('redacted-test-token'), false);
});
