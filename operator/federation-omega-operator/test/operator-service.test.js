import assert from "node:assert/strict";
import test from "node:test";

import {
  ALLOWED_ACTIONS,
  createOperatorService,
  publicOperatorError,
} from "../src/operator-service.js";

const PROJECT = "sov-hybrid-suite";
const REGION = "africa-south1";

function fixtures() {
  const calls = [];
  const googleRequest = async ({ url, method, timeout }) => {
    calls.push({ url, method, timeout });
    if (url.includes("run.googleapis.com")) {
      return {
        data: {
          name: `projects/${PROJECT}/locations/${REGION}/services/architron9`,
          uid: "uid-1",
          uri: "https://architron9-abc.africa-south1.run.app",
          latestReadyRevision: "architron9-00042",
          template: {
            containers: [{ env: [{ name: "SECRET", value: "CLOUD_RUN_SECRET" }] }],
          },
        },
      };
    }
    if (url.includes("cloudbuild.googleapis.com")) {
      return {
        data: {
          id: "12345678-abcd",
          name: `projects/${PROJECT}/locations/${REGION}/builds/12345678-abcd`,
          projectId: PROJECT,
          status: "SUCCESS",
          substitutions: { _SECRET: "BUILD_SECRET" },
          steps: [{ secretEnv: ["BUILD_SECRET"] }],
          source: {
            storageSource: {
              bucket: "build-source-bucket",
              object: "sources/operator.zip",
            },
          },
          sourceProvenance: {
            resolvedStorageSource: {
              bucket: "build-source-bucket",
              object: "sources/operator.zip",
              generation: "7",
            },
          },
          results: {
            images: [{ name: "image.example/operator", digest: "sha256:abc" }],
          },
        },
      };
    }
    if (url.includes("/workloadIdentityPools")) {
      return { data: { workloadIdentityPools: [] } };
    }
    if (url.includes("/serviceAccounts")) {
      return { data: { accounts: [] } };
    }
    throw new Error(`unexpected URL ${url}`);
  };
  const publicFetch = async () => ({
    ok: true,
    async json() {
      return {
        ok: true,
        healthOk: true,
        staleSignal: false,
        repairQueued: false,
        decisionAction: "NONE",
        noGmail: true,
        secret: "HEALTH_SECRET",
      };
    },
  });
  return { calls, googleRequest, publicFetch };
}

test("preserves five live actions, adds WIF inventory, and sanitizes provider data", async () => {
  const { calls, googleRequest, publicFetch } = fixtures();
  const service = createOperatorService({
    projectId: PROJECT,
    region: REGION,
    googleRequest,
    publicFetch,
    now: () => "2026-08-22T00:00:00.000Z",
  });

  assert.deepEqual(service.contract().allowedActions, ALLOWED_ACTIONS);
  assert.equal(ALLOWED_ACTIONS.length, 6);
  await service.execute({ action: "STATUS", requestId: "r-status" });
  const cloudRun = await service.execute({
    action: "READ_CLOUD_RUN_SERVICE",
    payload: { project: PROJECT, region: REGION, service: "architron9" },
    requestId: "r-run",
  });
  const health = await service.execute({
    action: "VERIFY_ARCHITRON_HEALTH",
    requestId: "r-health",
  });
  const build = await service.execute({
    action: "READ_BUILD",
    payload: {
      project: PROJECT,
      region: REGION,
      buildId: "12345678-abcd",
      expectedStatus: "SUCCESS",
    },
    requestId: "r-build",
  });
  const wif = await service.execute({
    action: "READ_WIF_INVENTORY",
    payload: { project: PROJECT, location: "global" },
    requestId: "r-wif",
  });

  const serialized = JSON.stringify({ cloudRun, health, build, wif });
  for (const secret of ["CLOUD_RUN_SECRET", "BUILD_SECRET", "HEALTH_SECRET"]) {
    assert.equal(serialized.includes(secret), false);
  }
  assert.equal(build.matchesExpectedStatus, true);
  assert.equal(build.build.source.storageSource.object, "sources/operator.zip");
  assert.equal(wif.status, "WIF_INVENTORY_READ");
  assert.ok(calls.every((call) => call.method === "GET"));
});

test("deployment action fails closed without adapter and validates approval first", async () => {
  const { googleRequest, publicFetch } = fixtures();
  const service = createOperatorService({
    projectId: PROJECT,
    region: REGION,
    googleRequest,
    publicFetch,
  });
  const payload = {
    approvalKey: "APPROVED",
    project: PROJECT,
    region: REGION,
    service: "pfrd-omega-gateway-canary",
    artifactDriveId: "11IQSUWThWuZwwCwevSffqP1gsgs2nvr9",
    artifactName: "artifact.zip",
    artifactSha256: "a".repeat(64),
    idempotencyKey: "PFRD-OMEGA-2.1.0-aaaaaaaa",
  };
  await assert.rejects(
    service.execute({ action: "DEPLOY_SOLUTION5_LOCKED", payload }),
    (error) => publicOperatorError(error).code === "DEPLOYMENT_ADAPTER_REQUIRED",
  );
  await assert.rejects(
    service.execute({
      action: "DEPLOY_SOLUTION5_LOCKED",
      payload: { ...payload, approvalKey: "NO" },
    }),
    (error) => publicOperatorError(error).code === "DEPLOYMENT_APPROVAL_REQUIRED",
  );
});

test("deployment adapter output is allowlisted and raw secrets are dropped", async () => {
  const { googleRequest, publicFetch } = fixtures();
  let received;
  const service = createOperatorService({
    projectId: PROJECT,
    region: REGION,
    googleRequest,
    publicFetch,
    deploymentAdapter: {
      async execute(payload) {
        received = payload;
        return {
          ok: true,
          status: "BUILD_QUEUED",
          buildId: "12345678-abcd",
          project: PROJECT,
          region: REGION,
          service: payload.service,
          idempotencyKey: payload.idempotencyKey,
          asynchronous: true,
          accessToken: "ADAPTER_SECRET",
          rawProviderResponse: { secret: "ADAPTER_SECRET" },
        };
      },
    },
  });
  const result = await service.execute({
    action: "DEPLOY_SOLUTION5_LOCKED",
    payload: {
      approvalKey: "APPROVED",
      project: PROJECT,
      region: REGION,
      service: "pfrd-omega-gateway-canary",
      artifactDriveId: "11IQSUWThWuZwwCwevSffqP1gsgs2nvr9",
      artifactName: "artifact.zip",
      artifactSha256: "a".repeat(64),
      idempotencyKey: "PFRD-OMEGA-2.1.0-aaaaaaaa",
    },
  });
  assert.equal(received.project, PROJECT);
  assert.equal(JSON.stringify(result).includes("ADAPTER_SECRET"), false);
  assert.equal(result.status, "BUILD_QUEUED");
});

test("project, region, action, and build identifiers are fail-closed", async () => {
  const { googleRequest, publicFetch } = fixtures();
  const service = createOperatorService({
    projectId: PROJECT,
    region: REGION,
    googleRequest,
    publicFetch,
  });
  for (const [request, expected] of [
    [{ action: "READ_CLOUD_RUN_SERVICE", payload: { project: "other-project" } }, "PROJECT_NOT_ALLOWED"],
    [{ action: "READ_BUILD", payload: { buildId: "../secret" } }, "BUILD_ID_INVALID"],
    [{ action: "UNKNOWN" }, "ACTION_NOT_ALLOWED"],
  ]) {
    await assert.rejects(
      service.execute(request),
      (error) => publicOperatorError(error).code === expected,
    );
  }
});

test("target health timeouts are classified without leaking dependency errors", async () => {
  const { googleRequest } = fixtures();
  const publicFetch = async () => {
    const error = new Error("PRIVATE_TIMEOUT_DETAIL");
    error.name = "AbortError";
    throw error;
  };
  const service = createOperatorService({
    projectId: PROJECT,
    region: REGION,
    googleRequest,
    publicFetch,
  });
  await assert.rejects(
    service.execute({ action: "VERIFY_ARCHITRON_HEALTH" }),
    (error) => {
      assert.deepEqual(publicOperatorError(error), {
        code: "DEPENDENCY_TIMEOUT",
        httpStatus: 504,
      });
      assert.equal(error.message.includes("PRIVATE_TIMEOUT_DETAIL"), false);
      return true;
    },
  );
});
